"""Auth business logic: registration with OTP, verification, and login.

Design notes tied to the Jira acceptance criteria:
- KOL-12: a user row is created at registration but stays unverified and cannot
  log in until the OTP is confirmed. The OTP is delivered immediately through
  the Sender interface (synchronous logging sender for now), which satisfies the
  "sent within 30 seconds" criterion by design. A phone that already belongs to
  a verified account is blocked as a duplicate.
- KOL-13: the country selected at signup must be enabled in country_config, and
  the value drives all later country specific behavior.
- KOL-14: password reset. It lives next door in app.modules.auth.account,
  together with the account settings that change the same two credentials, and
  it REUSES the OTP machinery below rather than owning a second one.

Registration still only records attribution — signing up with a code is worth
nothing on its own, deliberately. What a referral eventually earns, and when,
lives in app.modules.auth.referrals.
"""
import secrets
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.country_config import get_enabled_countries
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth import otp, referrals
from app.modules.auth.models import (
    REFEREE,
    OtpChallenge,
    PasswordResetToken,
    ReferralCredit,
    User,
    utcnow,
)
from app.modules.auth.schemas import (
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    VerifyOtpRequest,
)
from app.modules.auth.schemas import ROLES

OTP_TTL_MINUTES = 10

# Referral codes: uppercase A-Z minus the lookalikes I and O, plus digits 2-9
# (0 and 1 are out for the same reason). Codes get read aloud and retyped from
# a friend's phone screen, so no character may be mistakable for another.
REFERRAL_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERRAL_CODE_LENGTH = 8
REFERRAL_MAX_ATTEMPTS = 3

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


def _generate_referral_code() -> str:
    return "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(REFERRAL_CODE_LENGTH))


def _attribute_referral(db: Session, user: User, raw_code: str) -> None:
    """Link a signup to the creator whose code it carried.

    Best-effort by design: a mistyped code must NEVER block a signup. When the
    code resolves to nobody it is ignored silently — no error, no warning —
    because the account matters more than the attribution.
    """
    # Codes are stored uppercase; people retype them from a phone screen, so
    # lowercase and stray whitespace are forgiven rather than punished.
    code = raw_code.strip().upper()
    if not code:
        return
    referrer = db.query(User).filter(User.referral_code == code).first()
    if referrer is not None:
        user.referred_by_user_id = referrer.id
        db.commit()


def get_my_referral(db: Session, user_id: str) -> dict:
    """The caller's referral code, who it brought in, and what it has earned.

    The code is minted lazily on the first request rather than at
    registration: most accounts never open the referral screen, and a code
    nobody was ever shown is a unique-column row for nothing.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="auth_user_not_found",
            detail="User not found",
        )
    if user.referral_code is None:
        # A 32^8 code space makes a collision practically impossible; the
        # retry loop is cheap insurance against the astronomically unlikely.
        for _ in range(REFERRAL_MAX_ATTEMPTS):
            candidate = _generate_referral_code()
            taken = db.query(User).filter(User.referral_code == candidate).first()
            if taken is None:
                user.referral_code = candidate
                db.commit()
                break
        else:
            raise AppError(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="auth_referral_code_failed",
                detail="Could not generate a referral code, try again",
            )

    referred = (
        db.query(User)
        .filter(User.referred_by_user_id == user_id)
        .order_by(User.created_at.desc())
        .all()
    )
    # One code brings in creators and buyers alike, so the counts are split
    # here rather than in the code itself: "3 people joined" does not tell a
    # creator whether they are recruiting peers or bringing in the businesses
    # that will pay them.
    referred_creators = sum(1 for u in referred if u.role in referrals.CREATOR_ROLES)
    referred_businesses = len(referred) - referred_creators

    credits = db.query(ReferralCredit).filter(ReferralCredit.user_id == user_id).all()
    credit_total = sum(c.amount for c in credits)
    # A user's credits are always denominated in their own market, so every
    # row shares one currency. Before the first one is earned there is no row
    # to read it from, so the country config answers instead and the screen
    # can show an honest zero rather than a blank.
    credit_currency = credits[0].currency if credits else referrals.market_currency(user)

    # Capped and newest first: a proof panel on a referral screen, not an
    # export of everyone the user has ever brought in.
    listed = referred[: referrals.REFERRAL_LIST_LIMIT]
    ordered_ids: set[str] = set()
    if listed:
        # One query rather than one per row. A "referee" credit exists exactly
        # for the people whose first order has completed.
        ordered_ids = {
            row[0]
            for row in db.query(ReferralCredit.user_id)
            .filter(
                ReferralCredit.kind == REFEREE,
                ReferralCredit.user_id.in_([u.id for u in listed]),
            )
            .all()
        }

    return {
        "code": user.referral_code,
        "referred_count": len(referred),
        "referred_creators": referred_creators,
        "referred_businesses": referred_businesses,
        "credit_total": credit_total,
        "credit_currency": credit_currency,
        "referrals": [
            {
                "joined_at": u.created_at,
                "role": u.role,
                "status": "ordered" if u.id in ordered_ids else "signed_up",
            }
            for u in listed
        ],
    }


def register(db: Session, payload: RegisterRequest) -> dict:
    if payload.role not in ROLES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_role_unknown",
            detail=f"Role must be one of {sorted(ROLES)}",
            # The machine values a client posts back, not prose. Translating
            # them would produce a list no endpoint accepts — a client that
            # reaches this has a bug, not a language problem.
            values={"roles": ", ".join(sorted(ROLES))},
        )
    if payload.country_code not in get_enabled_countries():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_country_unavailable",
            detail="Country is not available yet",
        )

    existing = db.query(User).filter(User.phone == payload.phone).first()
    if existing is not None and existing.is_verified:
        raise AppError(
            status.HTTP_409_CONFLICT,
            # The same rule the account screen enforces when somebody changes
            # their number, so the same code — see auth/account.py. One
            # sentence covers both because the fact is the same one: that
            # number belongs to an account already.
            code="auth_phone_taken",
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

    if payload.referral_code:
        _attribute_referral(db, user, payload.referral_code)

    _issue_otp(db, user)
    return {"user_id": user.id, "message": "Verification code sent"}


def verify_otp(db: Session, payload: VerifyOtpRequest) -> dict:
    user = db.query(User).filter(User.phone == payload.phone).first()
    if user is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_no_pending_verification",
            detail="No pending verification for this phone",
        )

    challenge = (
        db.query(OtpChallenge)
        .filter(OtpChallenge.user_id == user.id, OtpChallenge.consumed.is_(False))
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if challenge is None or challenge.expires_at < utcnow():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_code_expired",
            detail="Verification code has expired, request a new one",
        )
    if challenge.code != payload.code:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="auth_code_invalid",
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
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            # Deliberately one code for two different failures — no such
            # account, and wrong password. Splitting them would let anybody
            # enumerate which numbers are registered here, which is the whole
            # reason the English sentence is vague too.
            code="auth_bad_credentials",
            detail="Invalid phone or password",
        )
    if not user.is_verified:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="auth_not_verified",
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
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="auth_user_not_found",
            detail="User not found",
        )
    # The bearer token proves possession of a session; the password proves
    # possession of the account. Destruction requires the stronger proof, so
    # a stolen token alone cannot erase someone's livelihood.
    if not verify_password(payload.password, user.password_hash):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            # Shared with the account screen: in both places the rule is that
            # the CURRENT password supplied does not match.
            code="auth_password_incorrect",
            detail="Password is incorrect",
        )

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
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="auth_account_has_history",
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
    # Referral credits the user owns leave with them. Rows where they were
    # merely the other half of somebody else's pair survive with the pointer
    # cleared: that credit was earned by a different person and is not this
    # account's to take away.
    db.query(ReferralCredit).filter(ReferralCredit.user_id == user_id).delete(synchronize_session=False)
    db.query(ReferralCredit).filter(ReferralCredit.source_user_id == user_id).update(
        {ReferralCredit.source_user_id: None}, synchronize_session=False
    )
    # Accounts referred by this user keep existing; their attribution pointer
    # is cleared rather than cascaded — deleting a referrer must never touch
    # the people they brought in.
    db.query(User).filter(User.referred_by_user_id == user_id).update(
        {User.referred_by_user_id: None}, synchronize_session=False
    )
    db.delete(user)
    db.commit()
