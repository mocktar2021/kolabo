"""Epic A (KOL-1): Registration, Authentication and Onboarding."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth import account, schemas, service
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


@router.get("/me", response_model=schemas.MeOut)
def get_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """The caller's own account: id, phone, role, country, verified, joined —
    and who they are to look at.

    display_name and avatar_url ride along so a nav can draw the signed-in
    user without a second request per page. They come from the creator
    profile, else the business profile's company name with a null avatar, else
    both null; they are never assembled from the users table, whose only
    human-readable column is the phone number.

    Never anyone else's — the subject comes from the bearer token and there is
    no id parameter to walk. The password hash is not on the response and
    there is no field it could arrive in.
    """
    return account.get_me(db, user_id)


@router.patch("/me", response_model=schemas.MeOut)
def update_me(
    payload: schemas.AccountPatch,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Change the login phone, the password, or both.

    current_password is required for either. The phone IS the login identity,
    so moving it must cost the password: a stolen bearer token would otherwise
    be enough to point the account at somebody else's handset and reset it
    from there. A number already in use answers 409.
    """
    return account.update_me(db, user_id, payload)


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
    """Ask for a reset code by SMS. Always 202, always the same body.

    The answer is identical for a registered phone and an unknown one. Two
    answers would make this a free "is this number on Kolabo?" lookup for
    anyone with a list of numbers. Rate limited so an SMS bill cannot be run
    up on us. See KOL-14.
    """
    return account.request_password_reset(db, payload)


@router.post("/password-reset/confirm", response_model=schemas.MessageResponse)
def confirm_password_reset(
    payload: schemas.PasswordResetConfirm, db: Session = Depends(get_db)
):
    """Spend a reset code and set the new password. Single use. See KOL-14.

    The code is resolved together with the phone it was sent to, and every
    way of failing answers the same 400.
    """
    return account.confirm_password_reset(db, payload)
