"""Epic A (KOL-1): Registration, Authentication & Onboarding."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/register")
def register():
    """Register with phone number, trigger OTP. See KOL-12."""
    raise NotImplementedError


@router.post("/verify-otp")
def verify_otp():
    raise NotImplementedError


@router.post("/login")
def login():
    raise NotImplementedError


@router.post("/password-reset")
def password_reset():
    """See KOL-14."""
    raise NotImplementedError
