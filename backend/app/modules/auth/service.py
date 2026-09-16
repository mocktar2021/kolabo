"""Auth business logic: registration with OTP, verification, and login.

Design notes tied to the Jira acceptance criteria:
- KOL-12: a user row is created at registration but stays unverified and cannot
  log in until the OTP is confirmed. The OTP is delivered immediately through
  the Sender interface (which now puts it in a mailbox, see app.modules.auth.otp),
  which satisfies the "sent within 30 seconds" criterion by design. An address
  that already belongs to a verified account is blocked as a duplicate.
- KOL-13: the country selected at signup must be enabled in country_config, and
  the value drives all later country specific behavior.
- KOL-14: password reset. It lives next door in app.modules.auth.account,
  together with the account settings that change the same two credentials, and
  it REUSES the OTP machinery below rather than owning a second one.

THE EMAIL ADDRESS IS THE IDENTITY, and every lookup in this module is by it.
Registration takes no phone number at all. Each address is normalised through
core.emails before it is compared to anything, so the string that is looked up
is the string that would be stored, which is what stops one spelling of an
address looking free while another is taken — and stops the unique index
turning a clear 409 into a 500 on the write that finds out.

Registration still only records attribution — signing up with a code is worth
nothing on its own, deliberately. What a referral eventually earns, and when,
lives in app.modules.auth.referrals.
"""
import logging
import secrets
from datetime import timedelta

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_config import get_enabled_countries
from app.core.emails import normalized_email
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.auth import google, otp, referrals
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
    GoogleSignInRequest,
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

_log = logging.getLogger("kolabo.auth.service")


def _issue_otp(db: Session, user: User) -> None:
    """Write a challenge, put its code in the mailbox, and refuse if it did not go.

    THE ROW IS COMMITTED BEFORE THE SEND, and that order is the safe one. A
    code that reaches a mailbox must already exist to be verified against; a
    send that went out before the commit could hand somebody a code the
    database then failed to record. The price of that order is the case this
    function now handles: the send fails AFTER the row exists.

    WHEN THE SEND FAILS THE CHALLENGE IS CONSUMED ON THE SPOT. Left live, it
    would count against the per-account and platform ceilings as a code in
    flight that never flew, and it would be the newest unconsumed challenge
    that verify_otp resolves the next guess against. Consumed, it is history.
    Then the request refuses with a code of its own, so no client ever shows
    "code sent" for a code that never left the server. The account row stays,
    and registering the same address again is the resend.

    A provider that raises is a provider that failed: otp.deliver turns the
    exception into a result, so a mail outage is a 503 that says so rather
    than a 500 on a request whose row was already committed. What a mail
    provider that merely REFUSES cannot tell us is written down on
    otp.EmailSender, where the gap lives.

    THE TARGET IS user.email AND NOTHING ELSE. Only register() calls this, and
    register writes the address on the row before it does, so there is never
    a case here where the account has nowhere to send to.
    """
    code = otp.generate_code()
    challenge = OtpChallenge(
        user_id=user.id,
        code=code,
        expires_at=utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(challenge)
    db.commit()
    result = otp.deliver(
        _sender,
        user.email,
        # Subject and body, in the language their country defaults to. Composed
        # in otp.py because the reset path needs the identical treatment.
        otp.verification_message(user.country_code, code, OTP_TTL_MINUTES),
    )
    if result.ok:
        return
    challenge.consumed = True
    db.commit()
    _log.error(
        "verification code not delivered to %s via %s: %s",
        user.email,
        result.provider,
        result.error,
    )
    raise AppError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        # 503, not 500 and not 400: nobody sent anything wrong and the server
        # is not broken, the thing between us and the mailbox is. The client
        # says so in the reader's language and offers the retry that will
        # succeed the moment the provider is back.
        code="auth_otp_delivery_failed",
        detail="We could not send the verification code. Please try again in a moment.",
    )


def _live_otp_challenges(db: Session, user: User, now):
    """Verification codes for this account that a caller could still use.

    Live means the same three things it means for a reset code — see
    auth.account._live_reset_tokens, which this is deliberately a copy of:
    issued within the last hour, never consumed, and not yet expired. Counting
    rows by age alone would keep punishing somebody an hour after codes that
    lasted ten minutes had already died.
    """
    one_hour_ago = now - timedelta(hours=1)
    return (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.user_id == user.id,
            OtpChallenge.created_at >= one_hour_ago,
            OtpChallenge.consumed.is_(False),
            OtpChallenge.expires_at > now,
        )
        .all()
    )


def _live_otp_challenge_count(db: Session, now) -> int:
    """How many verification codes are alive ACROSS THE WHOLE PLATFORM.

    The same three conditions _live_otp_challenges applies to one account,
    applied to all of them: issued within the last hour, never consumed, not
    yet expired. Same table, same query, same notion of "live" — one COUNT
    rather than the rows, because nothing here reads them and loading every
    live challenge on the platform in order to call len() on it would be a
    strange way to ask how many there are.

    LIVE RATHER THAN SENDS-PER-HOUR, deliberately, so this number means the
    same kind of thing as the per-account one beside it. With a ten-minute OTP
    lifetime that makes both of them really "codes in flight" — which is also
    the quantity that tracks money already spent.

    No new table, no counter store, no middleware: the rows counted here are
    the rows registration was already writing.
    """
    one_hour_ago = now - timedelta(hours=1)
    return (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.created_at >= one_hour_ago,
            OtpChallenge.consumed.is_(False),
            OtpChallenge.expires_at > now,
        )
        .count()
    )


def _unusable_password_hash() -> str:
    """A hash of a secret that is generated, used once and never revealed.

    users.password_hash IS NOT NULL AND STAYS THAT WAY. Making the column
    nullable to accommodate accounts that sign in with Google would be a
    migration whose real effect is to let every other reader of that column
    meet None, and there are several, in two modules. A row that cannot happen
    is cheaper to reason about than a None that has to be handled everywhere.

    So a Google created account gets a password it is not possible to use: 32
    bytes from secrets, hashed, and the plaintext dropped on the floor when
    this function returns. Nothing shows it to anybody, nothing stores it, and
    nobody can guess it, so login() keeps working exactly as written and simply
    always answers auth_bad_credentials for such an account, which is the
    correct behaviour rather than a special case.

    WHICH IS WHY THE RE-AUTHENTICATION WORK SHIPPED WITH THIS AND NOT AFTER IT.
    Three places prove ownership by checking the password, and this account has
    no usable one, so without a second form of proof it could never be deleted
    or edited by its owner. See auth.account.require_reauth.

    token_urlsafe(32) is about 43 characters, comfortably under the 72 byte
    ceiling bcrypt silently truncates at, so the whole secret is hashed rather
    than most of it.
    """
    return hash_password(secrets.token_urlsafe(32))


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

    # NORMALISED BEFORE ANYTHING IS LOOKED UP OR WRITTEN, so that the address
    # compared against existing rows is the address that would be stored. The
    # other order would let "Kofi@gmail.com" look free while "kofi@gmail.com"
    # is taken, and the unique index would then turn a clear 409 into a 500 on
    # the insert that discovered it. core.emails owns what a valid address is.
    email = normalized_email(payload.email)
    if email is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            # The same code the account screen raises for the same reason, so
            # the client has one sentence to say about a mistyped address
            # wherever it was typed. See auth/account.py.
            code="auth_email_invalid",
            detail="That email address does not look right. Check it and try again.",
        )

    existing = db.query(User).filter(User.email == email).first()
    if existing is not None and existing.is_verified:
        raise AppError(
            status.HTTP_409_CONFLICT,
            # The same rule the account screen enforces when somebody changes
            # their address, so the same code — see auth/account.py. One
            # sentence covers both because the fact is the same one: that
            # address belongs to an account already.
            code="auth_email_taken",
            detail="That email address is already registered.",
        )

    # THE CEILING THAT IS ABOUT THE BILL RATHER THAN ABOUT ONE ACCOUNT.
    #
    # The per-account cap below stops a loop over ONE address. It does nothing
    # about a loop over MANY: three codes per address, times as many addresses
    # as somebody cares to type, is still a send bill with no top to it, and
    # until this line nothing anywhere counted the total.
    #
    # A BACKSTOP, NOT A GATE, and the difference is the whole design. Whoever
    # fills this ceiling locks out every legitimate signup until those codes
    # expire, so a global limit is a denial of service in its own right and
    # the number has to sit far above any plausible honest burst rather than
    # anywhere near real traffic — see settings.otp_global_max_per_hour for
    # the value and the arithmetic behind it. Reaching it should mean
    # something is wrong, never that a good afternoon was busy.
    #
    # CHECKED HERE, after the duplicate-address 409 and before either branch
    # below writes anything, for exactly the reason the per-account cap is
    # checked before the credentials are rewritten: a refused request must
    # change nothing. A caller over both ceilings is told about this one,
    # which is the honest answer — it is the condition that will still be true
    # when they try again from a different address.
    if _live_otp_challenge_count(db, utcnow()) >= settings.otp_global_max_per_hour:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            # Not auth_otp_too_many. That sentence tells the reader they have
            # asked for too many codes, and this reader may have asked for
            # none: the ceiling that stopped them is the platform's, not
            # theirs, and a refusal that blames the wrong party sends somebody
            # off to check a mailbox that was never the problem.
            code="auth_otp_capacity",
            detail="Verification codes are temporarily unavailable, try again in a few minutes",
        )

    if existing is not None:
        # THE SAME CAP THE RESET ENDPOINT ENFORCES, for the same reason and by
        # the same means — see auth.account.request_password_reset. Registering
        # an address that already has an unverified row RE-SENDS the code, so
        # /auth/register is the resend endpoint too, and it had no ceiling at
        # all: looping it over one address was a bill a stranger could run up
        # on us. Growth does not look like the same address four times in ten
        # minutes; abuse does.
        #
        # CHECKED BEFORE THE CREDENTIALS BELOW ARE REWRITTEN, so a refused
        # request changes nothing. Re-registering overwrites the password on
        # an unverified account, and a 429 that still wrote would hand whoever
        # ran the cap out a free way to take over somebody's half-finished
        # signup.
        #
        # It says out loud that this address has a registration pending, which
        # is a narrower disclosure than the 409 a few lines above already
        # makes for a verified one. The reset endpoint pays a real privacy
        # cost for its 429 and takes it deliberately; this one pays nothing it
        # was not already paying.
        if len(_live_otp_challenges(db, existing, utcnow())) >= settings.otp_max_per_hour:
            raise AppError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                code="auth_otp_too_many",
                detail="Too many verification codes requested, try again later",
            )
        # Unverified registration for this address. Refresh credentials and
        # resend.
        existing.password_hash = hash_password(payload.password)
        existing.country_code = payload.country_code
        existing.role = payload.role
        db.commit()
        user = existing
    else:
        # NO PHONE NUMBER. The column is nullable since f3c0a84e17d9 precisely
        # so this row can be written without one: a number asked for at signup
        # is a number nothing verifies, on the form whose only job is to get
        # somebody into the product. The settings screen collects one later,
        # when a payment or a support call gives it a purpose.
        user = User(
            email=email,
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
    # Normalised before the lookup, exactly as register normalises before the
    # insert. Somebody who registered as Kofi@ and types kofi@ on the
    # verification screen is the same person and must find the same row.
    user = db.query(User).filter(User.email == normalized_email(payload.email)).first()
    if user is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_no_pending_verification",
            detail="No pending verification for this email address",
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
        # A WRONG GUESS NOW COSTS SOMETHING. It used to cost nothing at all:
        # the challenge stayed live, nothing was counted, and with no rate
        # limiting anywhere in the application a script could spend a code's
        # entire ten minute life guessing it, in parallel. Six digits is a
        # million values; ten minutes of unmetered parallel guessing is not.
        #
        # Charged against every live code for this account rather than only
        # the one tried, and all of them are spent together when the allowance
        # runs out — see otp.spend_attempt for why per-row counting would be a
        # loophole. Committed before the refusal, so the count survives it.
        live = _live_otp_challenges(db, user, utcnow())
        if otp.spend_attempt(live, challenge):
            for spent in live:
                spent.consumed = True
            challenge.consumed = True
        db.commit()
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            # Unchanged, and deliberately the same sentence whether this was
            # guess one or guess five. "Too many attempts" would tell an
            # attacker exactly when to stop guessing and request a fresh code,
            # which is the one thing the allowance exists to prevent. A
            # locked-out user's next request finds no live challenge and gets
            # auth_code_expired — "request a new one" — which is the
            # instruction they actually need.
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
    # THE NORMALISATION IS THE LOGIN FIX. core.emails lowercases the whole
    # address, here and at registration alike, so the capitalisation somebody
    # happened to use on the signup form is not a credential they have to
    # remember. Without this line a login is case sensitive in a way no mail
    # provider these users have is.
    user = db.query(User).filter(User.email == normalized_email(payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            # Deliberately one code for two different failures — no such
            # account, and wrong password. Splitting them would let anybody
            # enumerate which addresses are registered here, which is the whole
            # reason the English sentence is vague too.
            code="auth_bad_credentials",
            detail="Invalid email or password",
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


def _link_google_identity(db: Session, user: User, identity: google.GoogleIdentity) -> None:
    """Record WHICH Google account this is, and never fail a sign in over it.

    BEST EFFORT, LIKE _attribute_referral ABOVE, and for a sharper reason. The
    sign in itself was authorised by a mailbox Google has confirmed, which is
    this platform's whole notion of identity. What this function writes is the
    state a settings screen reads in order to say "connected with Google", and
    refusing somebody entry to their own account because that bookkeeping could
    not be done would be paying for a row with a person's access.

    WHEN THE STORED SUBJECT AND THE PRESENTED ONE DISAGREE FOR ONE ADDRESS, THE
    MAILBOX STILL DECIDES AND THE ROW IS RE-LINKED. The case is real rather
    than theoretical: a Workspace address can be deleted and recreated, and
    what stands behind it afterwards is a different Google account carrying a
    new `sub` at the same address. A `sub` is stable and an address is not,
    which is exactly why the link is kept on the `sub`, and it is also why the
    two can come apart.

      THE ALTERNATIVE WAS TO REFUSE THE SIGN IN, and it was rejected because it
      buys nothing and costs the honest case everything. Whoever holds that
      mailbox can already take the account by asking for a password reset and
      reading the code, in about ten minutes, so refusing here keeps no
      attacker out. It only strands somebody whose employer recreated their
      address, with a sentence they cannot act on. The disagreement IS logged
      at WARNING, because it has the shape a takeover through a recreated
      Workspace address would have and nothing else in the system records it.

    A SUBJECT ANOTHER ACCOUNT ALREADY HOLDS IS NOT TAKEN FROM IT. One Google
    account can present under two addresses over its life, and each of those
    addresses may have its own Kolabo account, so this is reachable without
    anybody doing anything wrong. The second account signs in on the strength
    of its own mailbox and is left unlinked: the identity belongs to the row
    that claimed it first, and moving it is precisely what the unique index on
    users.google_sub exists to prevent.

    THE COMMIT IS GUARDED ANYWAY. The query below and the write after it are
    not one atomic step, so two sign ins for one Google account arriving
    together can both pass it. The index refuses the second, and the exception
    becomes "left unlinked", which is the answer the query itself would have
    given a moment later. A 500 on a sign in that has otherwise succeeded is
    not an answer anybody can use.

    THE SUBJECT IS NOT WRITTEN TO THE LOG, on any branch. It identifies a
    person across every site that has ever seen one of their tokens, and the
    account id already says which row is being talked about, which is what
    anybody reading these lines needs.
    """
    if user.google_sub == identity.subject:
        return

    claimed_by = (
        db.query(User)
        .filter(User.google_sub == identity.subject, User.id != user.id)
        .first()
    )
    if claimed_by is not None:
        _log.warning(
            "Google identity for %s is already linked to account %s, leaving %s unlinked",
            identity.email,
            claimed_by.id,
            user.id,
        )
        return

    if user.google_sub is not None:
        _log.warning(
            "Google identity for account %s has changed, re-linking to the new one",
            user.id,
        )

    user.google_sub = identity.subject
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _log.warning(
            "Google identity was claimed concurrently, account %s left unlinked",
            user.id,
        )


def google_sign_in(db: Session, payload: GoogleSignInRequest) -> dict:
    """Sign somebody in with a Google ID token, creating the account if needed.

    THE LINKING RULE IS THE DECISION IN HERE, and it was taken deliberately
    rather than arrived at. A verified Google address that already belongs to a
    Kolabo account SIGNS INTO THAT ACCOUNT. It does not refuse, it does not
    create a second account, and it does not ask for the password first. The
    reason is the rule this whole module is built on: THE MAILBOX IS THE LOGIN
    IDENTITY here. Everything about an account resolves from its address, a
    password reset is a code sent to it, and somebody who can prove they hold
    that mailbox can already take the account back by that route in ten
    minutes. Google proving they hold it is the same fact, arriving faster.

    WHICH IS EXACTLY WHY email_verified IS LOAD BEARING. Given this rule, that
    one claim is the only thing between an attacker and an existing account:
    an address Google has not confirmed is not evidence of anything, and
    accepting one would mean anyone could take over a Kolabo account by
    asserting its owner's address on a domain of their own. auth.google refuses
    an unverified address outright and the whole of that argument is written
    down there.

    The password is left exactly where it is. An account that had one keeps it
    and keeps logging in with it; this adds a second door rather than replacing
    the first.

    THE LINK IS RECORDED ON BOTH BRANCHES, which is what users.google_sub is
    for. The account created here and the account that already existed and has
    just been signed into both come away knowing which Google account reaches
    them, so a settings screen can draw the connected row and a later revoke
    has something to clear. How it is written, and what happens when the stored
    subject and the presented one disagree, is _link_google_identity above.

    NO OTP IS SENT ON THE CREATE PATH, and the new row is verified from birth.
    Registration sends one to prove the mailbox; Google has just proved it. A
    row created unverified here would be one that login() immediately locks out
    with auth_not_verified, over a code nothing ever sent.
    """
    if not google.client_ids():
        # 503 rather than 404 or 400: the feature exists, this deployment has
        # not been given what it needs to offer it, and the caller did nothing
        # wrong. The client hides the button on this one.
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="auth_google_unavailable",
            detail="Signing in with Google is not available. Use your email address and password.",
        )

    identity = google.verify(payload.id_token)
    if identity is None:
        # ONE REFUSAL FOR EVERY WAY A TOKEN CAN BE REFUSED, including an
        # address Google has not confirmed. auth.google has already written
        # the reason to the log; saying it here as well would tell whoever is
        # holding a forged token which check caught it, and no honest caller is
        # helped by the difference.
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            code="auth_google_token_invalid",
            detail="We could not sign you in with Google. Try again, and check that your Google email address is confirmed.",
        )

    # Already normalised by auth.google, which is the only reason this lookup
    # is safe to write in one line. See core.emails for what normalising is
    # for and what it costs to skip.
    user = db.query(User).filter(User.email == identity.email).first()

    if user is not None:
        if not user.is_verified:
            # A half finished signup, completed by a different route. The
            # account was created by /auth/register, the code was never
            # entered, and Google has now proved the mailbox that code was
            # sent to. Leaving the flag alone would strand the account: it
            # would hold a token from here and still be refused by login().
            user.is_verified = True
            db.commit()
        # password_hash is deliberately untouched. An account with a password
        # keeps both ways in.
        #
        # AND THE LINK IS RECORDED HERE, not only on the create path below. An
        # account that registered with a password and has now signed in with
        # Google IS linked to Google from this moment, and a settings screen
        # saying otherwise would be describing a door its owner had just walked
        # through.
        _link_google_identity(db, user, identity)
        return {"access_token": create_access_token(user.id), "role": user.role}

    if payload.role is None or payload.country_code is None:
        # NOT AN ERROR, the first leg of a two step flow. Google says who
        # somebody is and cannot say which country they sell in or whether they
        # came here to sell. The client asks both questions and calls again
        # with the same token, which is still good for the best part of an hour.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_google_profile_required",
            detail="Tell us your country and whether you are a creator or a business, then sign in with Google again.",
        )

    # VALIDATED EXACTLY AS register VALIDATES THEM, with the same two codes.
    # A second opinion about what a role is, or about which markets are open,
    # would be a second thing to keep in step with country_config the day a
    # market closes.
    if payload.role not in ROLES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_role_unknown",
            detail=f"Role must be one of {sorted(ROLES)}",
            values={"roles": ", ".join(sorted(ROLES))},
        )
    if payload.country_code not in get_enabled_countries():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_country_unavailable",
            detail="Country is not available yet",
        )

    user = User(
        email=identity.email,
        # An unusable password ON PURPOSE, so the NOT NULL column stays honest
        # without a migration and without making it nullable. See
        # _unusable_password_hash, and see auth.account.require_reauth for how
        # such an account still proves it owns itself.
        password_hash=_unusable_password_hash(),
        country_code=payload.country_code,
        role=payload.role,
        # Verified from birth, and no OTP. See the docstring.
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # The link, on the row that exists only because of it. Written after the
    # insert rather than as a column on it, so that a subject some other
    # account already holds costs this one nothing: the account is still
    # created and still signed in, and only the bookkeeping is skipped.
    _link_google_identity(db, user, identity)

    # Attribution works here for the same reason it works at registration:
    # this IS a registration, and a creator who brought somebody in should not
    # lose the credit because that person tapped the Google button instead of
    # filling in the form. Best effort, exactly as there: a code that resolves
    # to nobody is dropped in silence rather than failing a signup.
    if payload.referral_code:
        _attribute_referral(db, user, payload.referral_code)

    # Same contract as verify_otp and login: every token grant says which role
    # the account has, so the client can mount the right home experience.
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
    # The bearer token proves possession of a session; the proof below proves
    # possession of the ACCOUNT. Destruction requires the stronger one, so a
    # stolen token alone cannot erase someone's livelihood.
    #
    # THE RULE IS SHARED WITH THE SETTINGS SCREEN and lives next door, because
    # it is one rule: a current password, or a freshly verified Google ID token
    # for this account's own address, and exactly one of the two. An account
    # created through Google has no usable password, so without the second form
    # this endpoint would be unreachable for its owner forever.
    #
    # Imported inside the function, like the model imports below and for the
    # same reason: auth.account reaches into profiles.models at module level,
    # and auth.service is imported by enough of this codebase that dragging
    # that in at import time would invert the dependency direction.
    from app.modules.auth.account import require_reauth

    require_reauth(user, payload.password, payload.google_token)

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
