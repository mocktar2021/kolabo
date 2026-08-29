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
    # WHETHER THIS ACCOUNT MAY REACH THE ADMIN SURFACE, and the reason it is
    # here rather than derivable from `role` above: admin is NOT a role. It is
    # a flag beside one, so that every existing role check keeps working and
    # an admin is also an ordinary marketplace user (see User.is_admin).
    #
    # Which left the frontend unable to ask the question at all. getStoredRole
    # answers "influencer | business | agency" and nothing else, so there was
    # no input a route guard could read — which is precisely why /admin/disputes
    # is declared in App.tsx with no guard on it. The page was reachable, every
    # request on it 403'd, and it rendered empty.
    #
    # READ-ONLY, AND SETTABLE NOWHERE IN THE API. app.modules.auth.admins
    # reconciles this from a configured list of phone numbers on every boot,
    # granting and revoking, because deployment configuration is the one
    # channel an attacker who has reached the API does not automatically have.
    # AccountPatch below cannot carry it either.
    is_admin: bool = False
    created_at: datetime
    # WHO THE CALLER IS TO LOOK AT, which nothing else on this row answers: a
    # phone number, a role and a country are not things a person recognises
    # themselves by, so a nav that wanted to draw the signed-in user had no
    # source and drew a glyph. Resolved from the creator profile if there is
    # one, else the business profile's company name — with a NULL AVATAR,
    # because a business has a company name and no avatar anywhere in this
    # system — else both null.
    #
    # Null is a real answer for somebody who has not written a profile yet,
    # and it stays null. It must never be filled in from the users table: the
    # only human-readable column there is the phone number, and putting that
    # in a display slot is how it ends up rendered somewhere it should not be.
    display_name: str | None = None
    avatar_url: str | None = None


class AccountPatch(BaseModel):
    """A change to the account itself: the login phone, the password, or both.

    current_password is REQUIRED and not optional-per-field. Both of these
    change the credentials somebody logs in with, and a bearer token only
    proves that a session exists — it cannot tell an owner from whoever picked
    the handset up. The password is what tells them apart.

    Partial like every other patch here: a field the client did not send is
    left alone. Neither field sent is refused in the service with a sentence,
    rather than silently succeeding at nothing.

    NOTHING HERE TOUCHES is_admin, and nothing ever should. Pydantic ignores
    unknown keys, so a client posting one is not refused — it is simply not
    read, which test_me_is_admin.py asserts rather than assumes.
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
