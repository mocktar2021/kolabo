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
    return {"access_token": create_access_token(user.id)}


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
    return {"access_token": create_access_token(user.id)}


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
