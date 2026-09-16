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
    """What a signup carries. An address, not a number.

    NO min_length OR max_length ON THE EMAIL, unlike the phone this replaced.
    A length is a property of an address and app.core.emails owns it
    (MAX_EMAIL_CHARS); a second opinion here would be a second number to keep
    in step, and it would answer a mistyped address with an untranslated 422
    instead of the sentence auth_email_invalid exists to say. Same reasoning,
    and the same shape, as AccountPatch.email below.

    THE PHONE IS GONE FROM THIS REQUEST ENTIRELY and is not optional here. A
    number collected at signup is a number nothing verifies, on a form whose
    only job is to get somebody into the product; the settings screen asks for
    one later, when there is a reason to.
    """

    email: str
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
    email: str
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleSignInRequest(BaseModel):
    """A Google ID token, and the two things Google cannot tell us.

    ID TOKEN, NOT AN AUTHORIZATION CODE. The client obtains the token from
    Google and posts it here; there is no redirect uri, no callback route and
    no client secret on this path. See app.modules.auth.google.

    role AND country_code ARE OPTIONAL BECAUSE THIS IS TWO REQUESTS, not
    because they are ever optional for a new account. Google says who somebody
    is; it cannot say which country they sell in or whether they came here to
    sell at all. So a token whose address already has an account signs in with
    neither of these, and a token whose address does not is refused once with
    `auth_google_profile_required` so the client can ask both questions and
    call again with the SAME TOKEN. Sending them on the first call is allowed
    and simply saves the round trip.

    country_code carries the same two character bound registration puts on it,
    and both values are validated against ROLES and get_enabled_countries in
    the service, exactly as register validates them. A shape check here is not
    the rule; it only stops a twenty character string reaching the rule.

    referral_code is here for the same reason it is on RegisterRequest: this
    IS a registration when the address is new, and a creator who brought
    somebody in should not lose the attribution because that person happened
    to tap the Google button. Ignored silently when it resolves to nobody, and
    ignored entirely on the sign in branch, where there is no new account to
    attribute.
    """

    id_token: str
    role: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    referral_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # The stored role rides along with every token grant. The frontend picks
    # the home experience (creator vs business vs agency) from this value;
    # while it was absent, a re-login had nothing to restore the role from —
    # which is how an agency account came back as a creator.
    role: str


class DeleteAccountRequest(BaseModel):
    """Proof of ownership, in whichever of the two forms this account has.

    Deleting an account must cost more than a stolen session token: the bearer
    token says a session exists, and it cannot tell an owner from whoever
    picked the handset up. Something else has to.

    BOTH FIELDS ARE OPTIONAL AND EXACTLY ONE IS REQUIRED, which pydantic cannot
    say and the service says instead (see auth.account.require_reauth). The
    reason neither can be mandatory is that an account created through Google
    HAS NO USABLE PASSWORD: its password_hash is a hash of a secret nobody has
    ever seen. Leaving `password` required would have meant such an account
    could never be deleted by its owner at all, which both app stores and data
    protection regimes expect to work.

    The answer is not to drop the check. It is to accept a different proof of
    the same fact: a freshly verified Google ID token for the same address.
    """

    password: str | None = None
    # A Google ID token, verified exactly as a sign in verifies one and then
    # required to carry THIS account's address. See auth.account.require_reauth.
    google_token: str | None = None


class MeOut(BaseModel):
    """The caller's own account, and only ever the caller's own.

    Both contact columns are on it, which is the one place in this system that
    is true: everywhere else they are deliberately withheld, because handing
    either to the other side of a deal is how a negotiation leaves the
    platform. Here the reader IS the subject, and a settings screen that cannot
    show you what you log in with is a settings screen you cannot use.

    password_hash is absent and there is no field it could arrive in. A hash
    is not a display value, and shipping one gives an attacker who has
    already stolen a session something to crack offline at leisure.
    """

    id: str
    # NOW OPTIONAL, AND NULL FOR EVERY ACCOUNT CREATED AFTER THE FLIP.
    # Registration stopped asking for a number, so this is either a value an
    # account carried over from before or one its owner typed into the settings
    # screen afterwards. It is still readable because the settings screen has
    # to show what is on file, and because it is the number a business's
    # checkout is started against.
    phone: str | None = None
    # THE LOGIN IDENTITY. This is what the account signs in with, what a
    # verification code is sent to and what a password reset resolves.
    #
    # Still typed optional, and the type is honest rather than lazy: accounts
    # registered before the flip have no address, and users.email is nullable
    # for the reason migration e1b7d4c92f08 sets out. A client reading null
    # here is looking at an account that predates the change, not at a bug.
    email: str | None = None
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
    # reconciles this from a configured list of email addresses on every boot,
    # granting and revoking, because deployment configuration is the one
    # channel an attacker who has reached the API does not automatically have.
    # AccountPatch below cannot carry it either.
    is_admin: bool = False
    # WHETHER THIS ACCOUNT CAN BE SIGNED INTO WITH GOOGLE, which is all a
    # settings screen needs in order to draw the "connected with Google" row
    # and all any client has ever needed from the link.
    #
    # A BOOLEAN, AND DELIBERATELY NOT THE SUBJECT ITSELF. Google's `sub` is a
    # stable identifier for a person across every site that has seen one of
    # their tokens, so putting it here would hand every client, every proxy log
    # and every browser cache a durable cross site handle on the user, in
    # exchange for nothing: no client has a use for the VALUE, only for whether
    # there is one. That is the same rule that keeps password_hash off this
    # schema, and the same reason the docstring above gives for withholding
    # contact details everywhere except here.
    #
    # False for an account that has never signed in with Google, and false for
    # every row written before users.google_sub existed. The second of those is
    # the truth rather than a gap: nothing recorded the link before the column
    # did, and no address can be turned back into a `sub`. Such an account
    # starts answering true the next time its owner signs in with Google.
    google_linked: bool = False
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
    # only human-readable columns there are the contact ones, and putting an
    # address or a number in a display slot is how it ends up rendered
    # somewhere it should not be.
    display_name: str | None = None
    avatar_url: str | None = None


class AccountPatch(BaseModel):
    """A change to the account itself: the login email, the phone, the password.

    BOTH COLUMNS STAY WRITABLE HERE even though only one of them is now an
    identity. The email because it is the identity, and the phone because it
    is the contact detail registration stopped collecting, which means this
    patch is the ONLY way an account ever acquires one.

    PROOF OF OWNERSHIP IS REQUIRED, in one of its two forms, and the form is
    what is optional rather than the proof. Every one of these changes
    something the account is reached or identified by, and a bearer token only
    proves that a session exists: it cannot tell an owner from whoever picked
    the handset up. The current password tells them apart, and for an account
    created through Google, which has no usable password, a freshly verified
    Google ID token tells them apart instead. Exactly one of the two, and the
    service enforces that because pydantic cannot.

    Partial like every other patch here: a field the client did not send is
    left alone. No field sent at all is refused in the service with a sentence,
    rather than silently succeeding at nothing.

    NOTHING HERE TOUCHES is_admin, and nothing ever should. Pydantic ignores
    unknown keys, so a client posting one is not refused — it is simply not
    read, which test_me_is_admin.py asserts rather than assumes.
    """

    current_password: str | None = Field(default=None, min_length=1)
    # The other proof of the same thing, for an account that has no usable
    # password to send. THIS IS ALSO WHAT LETS A GOOGLE USER SET A PASSWORD
    # FOR THE FIRST TIME: new_password below is the only way to acquire one,
    # and until this field existed it was gated behind a current password that
    # such an account could never have. See auth.account.require_reauth.
    google_token: str | None = None
    phone: str | None = Field(default=None, min_length=6, max_length=20)
    # THE LOGIN IDENTITY, so changing it is the single most consequential
    # thing on this schema: it moves where a reset code goes and it moves what
    # the account signs in with. A bearer token alone must never be able to
    # point it at a mailbox somebody else owns.
    #
    # No min_length or max_length beside it, unlike the phone. A length is a
    # property of an address and app.core.emails owns it (MAX_EMAIL_CHARS); a
    # second opinion here would be a second number to keep in step, and it
    # would answer a mistyped address with an untranslated 422 instead of the
    # sentence auth_email_invalid exists to say.
    email: str | None = None
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
    email: str


class PasswordResetConfirm(BaseModel):
    """Address plus code, not a bare token.

    The address is part of the request because the code is six digits sent by
    email, exactly like the registration OTP: it is short enough to be worth
    typing and therefore short enough to be worth guessing, so it is only ever
    resolved together with the mailbox it was sent to. A bare six digit token
    accepted on its own would be a lottery anyone could enter.
    """

    email: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class MessageResponse(BaseModel):
    message: str
