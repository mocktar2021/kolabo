"""Request and response schemas for the auth module."""
from datetime import datetime

from pydantic import BaseModel, Field

ROLES = {"influencer", "business", "agency"}


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    country_code: str = Field(min_length=2, max_length=2)
    role: str
    # Optional referral attribution. A code that resolves to nobody is ignored
    # server-side, never fatal — see _attribute_referral in the service.
    referral_code: str | None = None


class RegisterResponse(BaseModel):
    user_id: str
    message: str


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # The stored role rides along with every token grant. The frontend picks
    # the home experience (creator vs business vs agency) from this value;
    # while it was absent, a re-login had nothing to restore the role from —
    # which is how an agency account came back as a creator.
    role: str


class DeleteAccountRequest(BaseModel):
    # Deleting an account must cost more than a stolen session token: the
    # bearer token says who is asking, but only the current password proves
    # it is really them.
    password: str


class ReferralEntry(BaseModel):
    joined_at: datetime
    role: str
    # "signed_up" until their first order completes, "ordered" afterwards.
    # Only the second one pays, so the screen has to distinguish them: a wall
    # of signups that never ordered is exactly what this reward does not buy.
    status: str


class ReferralOut(BaseModel):
    code: str
    referred_count: int
    # One code brings in both audiences, so the counts are split: "3 people
    # joined" does not tell a creator whether they are recruiting peers or
    # bringing in the businesses that will pay them.
    referred_creators: int
    referred_businesses: int
    # Platform credit earned, in the owner's own market currency. The currency
    # is None only while that market has no configured credit value.
    credit_total: int
    credit_currency: str | None
    referrals: list[ReferralEntry] = Field(default_factory=list)


class PasswordResetRequest(BaseModel):
    phone: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str
