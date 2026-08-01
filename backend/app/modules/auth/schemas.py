"""Request and response schemas for the auth module."""
from datetime import datetime

from pydantic import BaseModel, Field

ROLES = {"influencer", "business", "agency"}

# The minimum a password may be, stated once. Registration, a change from the
# settings screen and a reset all spend it: a reset that accepted a weaker
# password than registration would be a way to walk an account DOWN to four
# characters, which is not a recovery flow, it is a downgrade flow.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
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


class MeOut(BaseModel):
    """The caller's own account, and only ever the caller's own.

    The phone number is on it, which is the one place in this system that is
    true: everywhere else a phone is deliberately withheld, because handing it
    to the other side of a deal is how a negotiation leaves the platform. Here
    the reader IS the subject, and a settings screen that cannot show you
    which number you log in with is a settings screen you cannot use.

    password_hash is absent and there is no field it could arrive in. A hash
    is not a display value, and shipping one gives an attacker who has
    already stolen a session something to crack offline at leisure.
    """

    id: str
    phone: str
    role: str
    country_code: str
    is_verified: bool
    created_at: datetime


class AccountPatch(BaseModel):
    """A change to the account itself: the login phone, the password, or both.

    current_password is REQUIRED and not optional-per-field. Both of these
    change the credentials somebody logs in with, and a bearer token only
    proves that a session exists — it cannot tell an owner from whoever picked
    the handset up. The password is what tells them apart.

    Partial like every other patch here: a field the client did not send is
    left alone. Neither field sent is refused in the service with a sentence,
    rather than silently succeeding at nothing.
    """

    current_password: str = Field(min_length=1)
    phone: str | None = Field(default=None, min_length=6, max_length=20)
    # Same floor as registration, on purpose. See MIN_PASSWORD_LENGTH.
    new_password: str | None = Field(
        default=None, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )


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
    """Phone plus code, not a bare token.

    The phone is part of the request because the code is six digits delivered
    by SMS, exactly like the registration OTP: it is short enough to be worth
    typing and therefore short enough to be worth guessing, so it is only ever
    resolved together with the number it was sent to. A bare six digit token
    accepted on its own would be a lottery anyone could enter.
    """

    phone: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class MessageResponse(BaseModel):
    message: str
