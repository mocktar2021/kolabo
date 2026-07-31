"""Auth business logic: registration with OTP, verification, login, and reset.

Design notes tied to the Jira acceptance criteria:
- KOL-12: a user row is created at registration but stays unverified and cannot
  log in until the OTP is confirmed. The OTP is delivered immediately through
  the Sender interface (synchronous logging sender for now), which satisfies the
  "sent within 30 seconds" criterion by design. A phone that already belongs to
  a verified account is blocked as a duplicate.
- KOL-13: the country selected at signup must be enabled in country_config, and
  the value drives all later country specific behavior.
- KOL-14: reset tokens expire after 30 minutes and each phone is limited to 3
  reset requests per hour.
"""
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.country_config import get_enabled_countries
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth import otp
from app.modules.auth.models import (
    OtpChallenge,
    PasswordResetToken,
    User,
    utcnow,
)
from app.modules.auth.schemas import (
    DeleteAccountRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    VerifyOtpRequest,
)
from app.modules.auth.schemas import ROLES

OTP_TTL_MINUTES = 10
RESET_TTL_MINUTES = 30
RESET_MAX_PER_HOUR = 3

_sender = otp.default_sender


def _issue_otp(db: Session, user: User) -> None:
    code = otp.generate_code()
    challenge = OtpChallenge(
        user_id=user.id,
        code=code,
        expires_at=utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(challenge)
    db.commit()
    _sender.send(user.phone, f"Your Kolabo verification code is {code}")


def register(db: Session, payload: RegisterRequest) -> dict:
    if payload.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of {sorted(ROLES)}",
        )
    if payload.country_code not in get_enabled_countries():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Country is not available yet",
        )

    existing = db.query(User).filter(User.phone == payload.phone).first()
    if existing is not None and existing.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number is already registered",
        )

    if existing is not None:
        # Unverified registration for this phone. Refresh credentials and resend.
        existing.password_hash = hash_password(payload.password)
        existing.country_code = payload.country_code
        existing.role = payload.role
        db.commit()
        user = existing
    else:
        user = User(
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            country_code=payload.country_code,
            role=payload.role,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    _issue_otp(db, user)
    return {"user_id": user.id, "message": "Verification code sent"}


def verify_otp(db: Session, payload: VerifyOtpRequest) -> dict:
    user = db.query(User).filter(User.phone == payload.phone).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification for this phone",
        )

    challenge = (
        db.query(OtpChallenge)
        .filter(OtpChallenge.user_id == user.id, OtpChallenge.consumed.is_(False))
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if challenge is None or challenge.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired, request a new one",
        )
    if challenge.code != payload.code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    challenge.consumed = True
    user.is_verified = True
    db.commit()
    # The role travels with the token: the frontend decides which home
    # experience to mount from it, and deriving it from anything else is how
    # agencies ended up treated as creators after a re-login.
    return {"access_token": create_access_token(user.id), "role": user.role}


def login(db: Session, payload: LoginRequest) -> dict:
    user = db.query(User).filter(User.phone == payload.phone).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified yet",
        )
    # Same contract as verify_otp: every token grant says which role the
    # account has, so a fresh login can restore the right experience.
    return {"access_token": create_access_token(user.id), "role": user.role}


def delete_account(db: Session, user_id: str, payload: DeleteAccountRequest) -> None:
    """Hard-delete an account and everything that is only theirs.

    POLICY — hard delete is allowed only while the account has NO contracts
    and NO escrows, in either role. The moment a signed agreement or money is
    involved, self-service deletion stops (409): counterparties keep their
    contract and review history, and money trails are never erased. Closing
    such an account is a support workflow, not an endpoint.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # The bearer token proves possession of a session; the password proves
    # possession of the account. Destruction requires the stronger proof, so
    # a stolen token alone cannot erase someone's livelihood.
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password is incorrect")

    # Imported here rather than at module level, like the trust_safety import
    # in the profiles service: auth is imported by every module, so top-level
    # imports of their models would invert the dependency direction.
    from app.modules.campaigns.models import Campaign, CampaignInvitation, Proposal
    from app.modules.contracts.models import Contract
    from app.modules.discovery.models import Favorite
    from app.modules.messaging.models import Message
    from app.modules.notifications.models import Notification, NotificationPreference
    from app.modules.payments.models import Escrow
    from app.modules.profiles.models import (
        BusinessProfile,
        InfluencerProfile,
        MediaAsset,
        Package,
        PortfolioItem,
        SocialAccount,
        VerificationDocument,
    )
    from app.modules.trust_safety.models import Report, Review

    has_contract = (
        db.query(Contract)
        .filter((Contract.business_user_id == user_id) | (Contract.influencer_user_id == user_id))
        .first()
        is not None
    )
    has_escrow = (
        db.query(Escrow)
        .filter((Escrow.business_user_id == user_id) | (Escrow.influencer_user_id == user_id))
        .first()
        is not None
    )
    if has_contract or has_escrow:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account has transaction history; contact support to close it.",
        )

    # Children first, then the user row, and one commit at the very end: the
    # whole account disappears or none of it does.
    # portfolio_items reference media_assets, so they go before the assets.
    db.query(PortfolioItem).filter(PortfolioItem.user_id == user_id).delete(synchronize_session=False)
    db.query(MediaAsset).filter(MediaAsset.owner_user_id == user_id).delete(synchronize_session=False)
    db.query(SocialAccount).filter(SocialAccount.user_id == user_id).delete(synchronize_session=False)
    db.query(VerificationDocument).filter(VerificationDocument.user_id == user_id).delete(synchronize_session=False)
    db.query(Package).filter(Package.user_id == user_id).delete(synchronize_session=False)
    db.query(InfluencerProfile).filter(InfluencerProfile.user_id == user_id).delete(synchronize_session=False)
    db.query(BusinessProfile).filter(BusinessProfile.user_id == user_id).delete(synchronize_session=False)
    # Favorites in both directions: shortlists they made and shortlists they
    # appear on.
    db.query(Favorite).filter(
        (Favorite.business_user_id == user_id) | (Favorite.influencer_user_id == user_id)
    ).delete(synchronize_session=False)
    db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
    db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).delete(synchronize_session=False)
    db.query(Message).filter(
        (Message.sender_user_id == user_id) | (Message.recipient_user_id == user_id)
    ).delete(synchronize_session=False)
    db.query(CampaignInvitation).filter(CampaignInvitation.influencer_user_id == user_id).delete(synchronize_session=False)
    db.query(Proposal).filter(Proposal.influencer_user_id == user_id).delete(synchronize_session=False)
    # Campaigns they own are only reachable here while no contract exists
    # (checked above), but other users' invitations, proposals and messages
    # may still point at them and must go first.
    owned_campaign_ids = [row.id for row in db.query(Campaign.id).filter(Campaign.business_user_id == user_id).all()]
    if owned_campaign_ids:
        db.query(CampaignInvitation).filter(CampaignInvitation.campaign_id.in_(owned_campaign_ids)).delete(synchronize_session=False)
        db.query(Proposal).filter(Proposal.campaign_id.in_(owned_campaign_ids)).delete(synchronize_session=False)
        db.query(Message).filter(Message.campaign_id.in_(owned_campaign_ids)).delete(synchronize_session=False)
        db.query(Campaign).filter(Campaign.business_user_id == user_id).delete(synchronize_session=False)
    # Reviews require an escrow, so after the escrow check none should exist
    # in either direction; deleted anyway so the users FK can never be left
    # dangling by legacy or test data. Reports made by the user go too;
    # admin_action_logs stay untouched because admin_id is a plain string,
    # not a users FK.
    db.query(Review).filter(
        (Review.reviewer_user_id == user_id) | (Review.reviewee_user_id == user_id)
    ).delete(synchronize_session=False)
    db.query(Report).filter(Report.reporter_user_id == user_id).delete(synchronize_session=False)
    db.query(OtpChallenge).filter(OtpChallenge.user_id == user_id).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


def request_password_reset(db: Session, payload: PasswordResetRequest) -> dict:
    generic = {"message": "If the phone is registered, a reset code has been sent"}
    user = db.query(User).filter(User.phone == payload.phone).first()
    if user is None:
        # Do not reveal whether the phone exists.
        return generic

    one_hour_ago = utcnow() - timedelta(hours=1)
    recent = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= one_hour_ago,
        )
        .count()
    )
    if recent >= RESET_MAX_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset requests, try again later",
        )

    token = PasswordResetToken(
        user_id=user.id,
        token=otp.generate_token(),
        expires_at=utcnow() + timedelta(minutes=RESET_TTL_MINUTES),
    )
    db.add(token)
    db.commit()
    _sender.send(user.phone, f"Your Kolabo password reset code is {token.token}")
    return generic


def confirm_password_reset(db: Session, payload: PasswordResetConfirm) -> dict:
    token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token)
        .first()
    )
    if token is None or token.consumed or token.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid or expired",
        )

    user = db.query(User).filter(User.id == token.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token is invalid or expired",
        )

    user.password_hash = hash_password(payload.new_password)
    token.consumed = True
    db.commit()
    return {"message": "Password has been reset"}
