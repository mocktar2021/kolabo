"""The account a user owns: reading it, changing it, and getting back into it.

Two jobs live here and they are the same job seen from either side of the
door. A signed-in user changing their address or their password is account
settings; a locked-out user proving they still hold the mailbox is password
reset. Both turn on one fact — THE EMAIL ADDRESS IS THE LOGIN IDENTITY — so
both are written down in one place instead of split between a settings module
and a recovery one, where the rule would have to be restated and could drift.

THAT FACT USED TO BE THE PHONE NUMBER, and the whole of this module was written
around it. The argument then was that email is rare, often shared and
frequently abandoned in these markets. What settled it the other way is that
no SMS provider was ever contracted, so the phone half was a channel that
existed on paper only, while a mailbox is reachable in every one of the seven
countries for the price of an HTTP request.

Why there was no way back in before any of this. A user who forgot their
password was locked out permanently: nothing in the codebase read
password_reset_tokens except the delete-account sweep that cleaned it up, so
the table existed and the door did not.

A separate module from service.py, which is about registration, verification
and login. The dependency runs one way — router -> account -> otp, models —
and the OTP MACHINERY IS REUSED RATHER THAN REBUILT. There is exactly one way
this system puts a numeric code in front of a person (app.modules.auth.otp),
and a second one would mean a second code generator, a second expiry rule and
a second sender to swap the day the delivery channel changes again. The reset
code is otp.generate_code(), the body is otp.password_reset_message() and the
delivery is otp.default_sender: the same three calls registration makes.
"""
import logging
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.emails import normalized_email
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.modules.auth import google, otp
from app.modules.auth.models import PasswordResetToken, User, utcnow
from app.modules.auth.schemas import (
    AccountPatch,
    PasswordResetConfirm,
    PasswordResetRequest,
)
from app.modules.notifications.service import notify
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

# The same sender registration uses. Module level so a test can swap it, like
# the one in service.py.
_sender = otp.default_sender

_log = logging.getLogger("kolabo.auth.account")

# One body, one status, for an address we know and an address we do not. Built
# once so the two return paths cannot drift into two different sentences —
# which is the entire attack this endpoint is written to defeat.
GENERIC_RESET_RESPONSE = {
    "message": "If the email address is registered, a reset code has been sent"
}

# Said the same way for a wrong code, an expired code, an already-used code and
# an address that has never asked for one. Four different failures, one
# sentence: telling them apart would let a caller walk the difference backwards
# into "this address is registered and has an outstanding reset".
INVALID_CODE_DETAIL = "Reset code is invalid or expired"


def _own_identity(db: Session, user_id: str) -> tuple[str | None, str | None]:
    """The caller's own name and picture, in ONE query.

    Why this is on the account response at all. The users table holds an email
    address, a role and a country, and not one of those is something a person
    recognises themselves by — so the web nav had nothing to draw the
    signed-in user with and painted a gradient glyph instead. The alternative
    was a second request on every page to decorate a 28px button, which is a
    bad trade for a response the client already fetches.

    ONE OUTER-JOINED SELECT, not a lookup per table. /auth/me is called on
    every page load, so the cost of answering it is paid constantly, and
    asking two tables in turn would double that for a fact that is one row
    either way. Joining also lets the PROFILE ROW decide which branch we are
    in rather than the role column: role is what somebody signed up intending
    to be, and the profile is what they actually wrote.

    Precedence is the creator profile first, then the business one. A creator
    profile that exists with a blank display_name still wins and still answers
    None — falling through would show a name from the other table, and telling
    somebody they are called something they did not choose is worse than
    telling them nothing.

    A BUSINESS GETS A NAME AND NO AVATAR. That is not a gap on this endpoint;
    a business has a company name and no avatar anywhere in this system, which
    is the same fact messaging.conversations records when it sets
    counterparty_avatar_url for creators only.

    Neither profile means two nulls, and they stay null. It must never fall
    back to the users table: the only human-readable column there is the email
    address, and an address is not a display name — it is the credential this
    whole module exists to protect.
    """
    row = (
        db.query(
            # Selected as the presence marker for the join, because
            # display_name is nullable and "no creator profile" and "a creator
            # profile with no name yet" are different answers.
            InfluencerProfile.id,
            InfluencerProfile.display_name,
            InfluencerProfile.avatar_media_id,
            BusinessProfile.company_name,
        )
        .select_from(User)
        .outerjoin(InfluencerProfile, InfluencerProfile.user_id == User.id)
        .outerjoin(BusinessProfile, BusinessProfile.user_id == User.id)
        .filter(User.id == user_id)
        .first()
    )
    if row is None:
        return None, None

    profile_id, display_name, avatar_media_id, company_name = row
    if profile_id is not None:
        # The same URL shape profiles.service._media_url builds, restated here
        # rather than imported for the reason core.identity restates it: one
        # media route serves every surface that shows a face, and auth has no
        # business reaching into another module's private helper.
        avatar_url = f"/profiles/media/{avatar_media_id}" if avatar_media_id else None
        return display_name, avatar_url
    return company_name, None


def _me_out(db: Session, user: User) -> dict:
    """The account, without the hash.

    Assembled field by field rather than dumped off the model. A whitelist is
    the only version of this that stays safe when somebody adds a column: an
    exclude list silently starts leaking the moment a new secret is stored on
    the users row and nobody remembers this function exists.

    Which is also why is_admin had to be added here deliberately rather than
    appearing on its own. It is the one thing the frontend could not ask —
    admin is a flag beside a role, not a role, so getStoredRole cannot answer
    for it and no route guard had an input. See MeOut in schemas.py.

    Takes the session because two of the fields are not on the users row at
    all — see _own_identity for why they are answered here anyway.
    """
    display_name, avatar_url = _own_identity(db, user.id)
    return {
        "id": user.id,
        # Null for everybody who signed up after the flip, and that is a real
        # answer rather than a gap: registration stopped asking. It is here so
        # a settings screen can show what is on file and offer to fill it in.
        "phone": user.phone,
        # What the account IS. Present for every account created since the
        # flip; null only on rows that predate it.
        "email": user.email,
        "role": user.role,
        "country_code": user.country_code,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "created_at": user.created_at,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }


def require_reauth(user: User, password: str | None, google_token: str | None) -> None:
    """Prove the caller is the OWNER, not merely the holder of a session.

    THE RULE HAS NOT BEEN RELAXED, IT HAS BEEN GIVEN A SECOND FORM. A bearer
    token says a session exists; it cannot tell an owner from whoever picked
    the handset up. Changing the login address or destroying the account has
    always cost more than that, and still does.

    What changed is that an account created through Google HAS NO USABLE
    PASSWORD. Its password_hash is a hash of a freshly generated secret nobody
    has ever seen, written so the NOT NULL column stays honest (see
    auth.service._unusable_password_hash). Left as it was, the password check
    would have made such an account impossible for its owner to delete or to
    edit, which is not a rule, it is a trap: both app stores and every data
    protection regime these markets have expect a person to be able to close
    their own account.

    So the proof may be a Google ID token instead, verified exactly as a sign
    in verifies one and then required to carry THIS account's address. That is
    the same claim the password makes, arriving through a different door.

    EXACTLY ONE, NEVER BOTH AND NEVER NEITHER. Neither is nothing to check.
    Both is a request whose author does not know which proof they hold, and
    accepting it would mean deciding, silently, which one counted.

    403 THROUGHOUT, including for "you sent nothing". The request is not
    malformed, it is refused: the caller has not shown they may do this.

    THE PASSWORD BRANCH GUARDS ITS ARGUMENTS BEFORE IT CALLS verify_password,
    and that is not defensive habit, it is this function's own doing. passlib
    raises rather than returning False on the two shapes that only became
    reachable here: verify(None, hash) raises TypeError because the password
    is no longer a required field, and verify(raw, "") raises UnknownHashError
    on an empty stored hash. Either would be a 500 on a request that has a
    perfectly good 403 waiting for it. (verify(raw, None) does return False,
    which is the one case that would have been survivable.)

    A WRONG PASSWORD KEEPS auth_password_incorrect; everything else answers
    auth_reauth_required. The two sentences say different things to do, and
    telling somebody who sent a Google token that their password is wrong
    sends them to look for a password they may not have.
    """
    supplied = [proof for proof in (password, google_token) if proof]
    if len(supplied) != 1:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="auth_reauth_required",
            detail="We could not confirm it is you. Enter your current password, or confirm with Google, and try again.",
        )

    if password:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                # Shared with the delete endpoint: in both places the rule is
                # that the CURRENT password supplied does not match.
                code="auth_password_incorrect",
                detail="Current password is incorrect",
            )
        return

    identity = google.verify(google_token)
    # THE ADDRESS HAS TO BE THIS ACCOUNT'S. A verified Google token proves who
    # the holder is; it says nothing about which Kolabo account they are
    # pointing it at. Without this comparison anybody with any Google account
    # could re-authenticate as anybody else, which is a worse hole than the one
    # this whole function exists to keep shut. Both sides are normalised: the
    # token's address by google.verify, the stored one at registration.
    if identity is None or identity.email != user.email:
        # Logged, not disclosed. The caller gets one sentence whether the token
        # was forged, expired, addressed to another application, carried an
        # unconfirmed address, or simply belonged to somebody else.
        _log.warning("Re-authentication with a Google token refused for user %s", user.id)
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="auth_reauth_required",
            detail="We could not confirm it is you. Enter your current password, or confirm with Google, and try again.",
        )


def _require_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="auth_user_not_found",
            detail="User not found",
        )
    return user


def _notify_password_changed(db: Session, user: User) -> None:
    """Tell the owner their password moved, whoever moved it.

    Sent for a change made from settings as well as for a reset, because the
    message is not a receipt for the person who did it — they already know. It
    is for the person who did NOT do it, and that person cannot be identified
    in advance. An account takeover that arrives silently is one nobody
    reports until the money is gone.
    """
    notify(
        db,
        user.id,
        "security",
        "Your Kolabo password was changed. If this was not you, contact support now.",
        # One key for both callers (settings change and reset), because the
        # message is deliberately the same either way: it is written for the
        # person who did NOT do it, and they cannot tell which path was used.
        link="/account",
        params={"key": "password_changed"},
    )


def get_me(db: Session, user_id: str) -> dict:
    """The caller's own account. Never anyone else's — there is no id to pass.

    The subject is taken from the bearer token and from nothing else, so this
    endpoint has no lookup surface at all: there is no parameter an attacker
    could walk through other people's rows with. That holds for the name and
    the picture too — they are resolved from the same token-derived id.
    """
    return _me_out(db, _require_user(db, user_id))


def update_me(db: Session, user_id: str, payload: AccountPatch) -> dict:
    """Change the email, the phone, the password — at the price of the password.

    THE EMAIL IS THE LOGIN IDENTITY, so changing it must cost the password.
    Anyone holding a live bearer token could otherwise point the account at a
    mailbox they own and then reset the password from it at leisure, which
    turns a borrowed session into a permanent takeover of somebody's
    livelihood. The bearer token says a session exists; only the current
    password says the owner is the one asking.

    Addresses really do change — a job, a provider closing, a name change — so
    this has to exist rather than being a support ticket. What it must not
    become is a way to take somebody else's mailbox.

    OR A GOOGLE TOKEN, FOR AN ACCOUNT THAT HAS NO PASSWORD TO SEND. An account
    created through Google never had one, so a rule written as "the password"
    would have locked its owner out of their own settings screen. The price is
    unchanged; what is accepted in payment now includes a freshly verified
    Google ID token for this same address. See require_reauth above, and note
    that this is also the ONLY way such an account ever acquires a password:
    new_password below needs a current one, and there was none.

    THE PHONE IS NOT THE LOGIN IDENTITY ANY MORE AND STILL COSTS THE PASSWORD.
    It is no longer what anybody signs in with and no code is sent to it, so
    the takeover argument above does not apply to it. It keeps the price for a
    plainer reason: this patch is the only way an account ever gets a number at
    all now that registration does not ask, that number is what a business's
    FedaPay checkout is started against and what support calls back on, and a
    field that moves money and identifies a caller is not one a stolen session
    should be able to rewrite quietly.

    It is normalised through core.emails before it is compared to anything, so
    the value tested for uniqueness is the value that would be stored. Doing it
    the other way round would let one spelling look free while another is
    taken, and the unique index would then turn a clear 409 into a 500 on the
    write that found out.

    NOTHING HERE CAN TOUCH is_admin. AccountPatch has four fields and that is
    not one of them, and pydantic drops unknown keys rather than refusing
    them, so a client posting it gets a 200 and no privilege. The flag comes
    from deployment configuration only — see app.modules.auth.admins, which
    now matches on the address rather than on the number.
    """
    user = _require_user(db, user_id)

    data = payload.model_dump(exclude_unset=True)
    new_phone = data.get("phone")
    new_email = data.get("email")
    new_password = data.get("new_password")
    if new_phone is None and new_email is None and new_password is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_account_nothing_to_change",
            detail="Send a new phone number, a new email address, a new password, or any combination of them.",
        )

    # Checked before anything is looked up or written, and before the 409 on a
    # taken phone: a caller who cannot prove they own this account must not be
    # able to use it to discover whether a number is registered.
    require_reauth(user, payload.current_password, payload.google_token)

    if new_phone is not None and new_phone != user.phone:
        # Any row at all, verified or not. An unverified registration still
        # holds the number, and letting a verified account take it would let
        # somebody who half-signed-up be quietly displaced.
        #
        # THERE IS NO UNIQUE INDEX UNDERNEATH THIS ANY MORE. f3c0a84e17d9
        # dropped ix_users_phone when the phone stopped being an identity, so
        # this query is now the whole of the rule rather than a friendlier
        # spelling of a constraint the database would also have enforced. Two
        # requests racing through the gap between this SELECT and the commit
        # below would both succeed. That is an acceptable trade for a field
        # nothing authenticates with, and the migration says why.
        taken = db.query(User).filter(User.phone == new_phone, User.id != user.id).first()
        if taken is not None:
            raise AppError(
                status.HTTP_409_CONFLICT,
                code="auth_phone_taken",
                detail="That phone number is already in use",
            )
        user.phone = new_phone

    if new_email is not None:
        # Normalised first, so what is compared and what is stored are the same
        # string. See core.emails for what it does and, more to the point, for
        # what it deliberately does not do: this is a claim, not a verified
        # mailbox, and no confirmation link exists yet to make it one.
        email = normalized_email(new_email)
        if email is None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                code="auth_email_invalid",
                detail="That email address does not look right. Check it and try again.",
            )
        if email != user.email:
            # Any row at all, verified or not: an unverified registration still
            # holds the address it claimed, and a second account taking it
            # would collide on ix_users_email anyway, turning a clear 409 into
            # a 500 on the write that found out. Unlike the phone above, this
            # one does still have a constraint behind it, and it is the one
            # that needs it. Asked only after the password check, so this
            # cannot be used as a "does this person have a Kolabo account"
            # lookup.
            taken = db.query(User).filter(User.email == email, User.id != user.id).first()
            if taken is not None:
                raise AppError(
                    status.HTTP_409_CONFLICT,
                    code="auth_email_taken",
                    detail="That email address is already on another account.",
                )
            user.email = email

    if new_password is not None:
        user.password_hash = hash_password(new_password)
        _notify_password_changed(db, user)

    db.commit()
    db.refresh(user)
    return _me_out(db, user)


def _live_reset_tokens(db: Session, user: User, now):
    """Codes for this account that a caller could still use right now.

    Live means three things at once: issued within the last hour, never
    consumed, and not yet expired. Counting rows by age alone would keep
    punishing somebody an hour after codes that lasted fifteen minutes had
    already died.
    """
    one_hour_ago = now - timedelta(hours=1)
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= one_hour_ago,
            PasswordResetToken.consumed.is_(False),
            PasswordResetToken.expires_at > now,
        )
        .all()
    )


def request_password_reset(db: Session, payload: PasswordResetRequest) -> dict:
    """Send a reset code, and say the same thing either way.

    THE RESPONSE IS IDENTICAL WHETHER OR NOT THE ADDRESS IS REGISTERED. Same
    202, same body, same wording. This is the whole security property of the
    endpoint and it is not a nicety: an endpoint that answers differently for
    a known address is a free "is this person on Kolabo?" oracle, and anyone
    with a list of addresses can run it. In these markets that is a real
    privacy leak with real consequences — it discloses which creators and
    which businesses are earning on the platform to whoever asks, including
    people the user is specifically trying not to be found by. There is no
    product value on the other side of the trade: a user who mistyped their
    own address is helped by "check your inbox", not by being told their
    address is unknown.

    So: no 404 here, ever, and no timing shortcut that skips work for an
    unknown address in a way a stopwatch could read as an answer.

    THE ADDRESS IS NORMALISED FIRST, which is not a detail on this endpoint. A
    lookup that skipped it would answer the generic 202 to somebody who typed
    their own address with a capital letter, send nothing, and leave them
    waiting for a code that is never coming, with no way to tell that from a
    working reset. Silence is the failure mode this endpoint is built out of,
    so the one thing it must get right is finding the row.
    """
    user = db.query(User).filter(User.email == normalized_email(payload.email)).first()
    if user is None:
        return GENERIC_RESET_RESPONSE

    now = utcnow()
    if len(_live_reset_tokens(db, user, now)) >= settings.password_reset_max_per_hour:
        # THE ONE PLACE THIS ENDPOINT STOPS BEING SILENT, and the trade is
        # deliberate. Every request sends a message and every message costs
        # something, so an uncapped endpoint is a bill a stranger can run up on
        # us by looping — and swallowing the limit behind a 202 would hide that
        # from us while still spending nothing, leaving the abuse invisible and
        # a genuinely rate-limited user staring at "check your inbox" for a
        # message that will never arrive.
        #
        # It does narrow the oracle above: four requests distinguish a
        # registered address from an unknown one. That costs the attacker three
        # priced requests per address and is capped by the limit itself, where
        # the silent alternative costs them nothing and tells us nothing. Worth
        # revisiting the day there is a per-address attempt counter that does
        # not itself need a table of unauthenticated input.
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code="auth_reset_too_many",
            detail="Too many reset requests, try again later",
        )

    token = PasswordResetToken(
        user_id=user.id,
        # The registration OTP generator, not a second one. Six digits because
        # this is read off a screen and retyped, which the previous
        # 43-character urlsafe token was never going to survive.
        token=otp.generate_code(),
        expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    db.add(token)
    db.commit()
    result = otp.deliver(
        _sender,
        user.email,
        # Subject and body in the language their country defaults to, composed
        # by the same module registration uses so the two cannot drift.
        otp.password_reset_message(
            user.country_code, token.token, settings.password_reset_ttl_minutes
        ),
    )
    if not result.ok:
        # THE ONE CALL SITE THAT DOES NOT REFUSE, and the reason is the oracle
        # this whole endpoint exists to defeat. A 503 here would be answered
        # only for addresses that have an account, because only those reach a
        # send at all, so a provider outage would turn every request into a
        # free "is this address on Kolabo" lookup for as long as it lasted.
        # The 429 above narrows the oracle deliberately and says why; this
        # would open it wide for nothing the user could act on.
        #
        # So the answer stays the generic 202. What changes is that the token
        # is consumed, so a code that never left stops counting as one in
        # flight against the per-hour cap and the person can ask again the
        # moment delivery is back, and the failure is logged at ERROR in the
        # provider's own words, because a silent 202 over a dead provider is
        # how an outage goes unnoticed until support hears about it. The real
        # answer to a failing provider is a second one behind it, which is
        # what otp.CompositeSender is for.
        token.consumed = True
        db.commit()
        _log.error(
            "reset code not delivered to %s via %s: %s",
            user.email,
            result.provider,
            result.error,
        )
    return GENERIC_RESET_RESPONSE


def confirm_password_reset(db: Session, payload: PasswordResetConfirm) -> dict:
    """Spend a code once and set the new password.

    Resolved by ADDRESS AND CODE together. Six digits is small enough to guess
    at if it identifies a row on its own; paired with the mailbox it was sent
    to, a guess has to be aimed at somebody in particular.

    Every failure answers the same 400 with the same sentence — unknown
    address, wrong code, expired code, already-spent code. Distinguishing them
    would hand back exactly the fact the request endpoint refuses to disclose.
    """
    now = utcnow()
    user = db.query(User).filter(User.email == normalized_email(payload.email)).first()
    if user is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            # One code for "no such code" and for "expired", exactly as the
            # one shared English sentence already refuses to distinguish them.
            code="auth_reset_code_invalid",
            detail=INVALID_CODE_DETAIL,
        )

    live = _live_reset_tokens(db, user, now)
    token = next((t for t in live if t.token == payload.code), None)
    if token is None:
        # A WRONG GUESS NOW COSTS SOMETHING, and it matters more here than on
        # the registration challenge: spending a reset code CHANGES THE
        # PASSWORD, so unlimited guesses against six digits is a takeover
        # rather than a nuisance. Nothing counted before, and there is no rate
        # limiting anywhere in the application to fall back on.
        #
        # Charged against every live code for this account and they are all
        # spent together when the allowance runs out — see otp.spend_attempt.
        # `failed` is None because no row matched, so there is no single row
        # to blame; the account's whole allowance is what moves. Committed
        # before the refusal so the count survives it.
        if otp.spend_attempt(live, None):
            for spent in live:
                spent.consumed = True
        db.commit()
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            # One code for "no such code" and for "expired", exactly as the
            # one shared English sentence already refuses to distinguish them
            # — and now for "you have used up your guesses" as well, which is
            # the same decision for the same reason. A distinct sentence there
            # would tell an attacker precisely when to stop and ask for a
            # fresh code.
            code="auth_reset_code_invalid",
            detail=INVALID_CODE_DETAIL,
        )

    user.password_hash = hash_password(payload.new_password)
    token.consumed = True
    # Every other outstanding code for this account dies with it, not just the
    # one that was spent. The account has just changed hands back to whoever
    # holds the mailbox; leaving two more valid codes in flight would leave two
    # more chances for whoever prompted the reset in the first place.
    for other in _live_reset_tokens(db, user, now):
        other.consumed = True
    _notify_password_changed(db, user)
    db.commit()
    return {"message": "Password has been reset"}
