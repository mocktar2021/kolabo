"""Epic A (KOL-1): Registration, Authentication and Onboarding."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth import schemas, service
from app.modules.auth.deps import get_current_user_id

router = APIRouter()


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """Register with a phone number and receive an OTP. See KOL-12, KOL-13."""
    return service.register(db, payload)


@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.VerifyOtpRequest, db: Session = Depends(get_db)):
    """Confirm the OTP, mark the account verified, and return a token. KOL-12."""
    return service.verify_otp(db, payload)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Log in a verified account."""
    return service.login(db, payload)


@router.get("/me/referral", response_model=schemas.ReferralOut)
def my_referral(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """The caller's referral code, who it brought in, and what it has earned.

    The code is minted on the first call and stable afterwards. Counts are
    split between creators and businesses because one code brings in both, and
    each referral carries whether that person has actually ordered — the only
    status that pays. See app.modules.auth.referrals for why.
    """
    return service.get_my_referral(db, user_id)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: schemas.DeleteAccountRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete the caller's own account.

    The bearer token identifies the account, but the current password is
    required in the body: destroying an account must cost more than a stolen
    session token. Hard delete happens only while the account has no contract
    or escrow history; otherwise 409 and support closes it instead.
    """
    service.delete_account(db, user_id, payload)


@router.post(
    "/password-reset/request",
    response_model=schemas.MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    payload: schemas.PasswordResetRequest, db: Session = Depends(get_db)
):
    """Request a password reset. Rate limited to 3 per hour. See KOL-14."""
    return service.request_password_reset(db, payload)


@router.post("/password-reset/confirm", response_model=schemas.MessageResponse)
def confirm_password_reset(
    payload: schemas.PasswordResetConfirm, db: Session = Depends(get_db)
):
    """Confirm a password reset with a valid, unexpired token. See KOL-14."""
    return service.confirm_password_reset(db, payload)
