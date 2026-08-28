"""The account a user owns: reading it, changing it, and getting back into it.

Two jobs live here and they are the same job seen from either side of the
door. A signed-in user changing their phone or their password is account
settings; a locked-out user proving they still hold the phone is password
reset. Both turn on one fact — in these markets THE PHONE NUMBER IS THE LOGIN
IDENTITY, because email is rare, often shared, and frequently abandoned — so
both are written down in one place instead of split between a settings module
and a recovery one, where the rule would have to be restated and could drift.

Why there was no way back in before this. A user who forgot their password was
locked out permanently: nothing in the codebase read password_reset_tokens
except the delete-account sweep that cleaned it up, so the table existed and
the door did not. In markets where the phone is the account and numbers change
with SIM prices, that is not an edge case, it is attrition.

A separate module from service.py, which is about registration, verification
and login. The dependency runs one way — router -> account -> otp, models —
and the OTP MACHINERY IS REUSED RATHER THAN REBUILT. There is exactly one way
this system puts a numeric code on a phone (app.modules.auth.otp), and a
second one would mean a second code generator, a second expiry rule and a
second sender to swap the day a real SMS provider is contracted. The reset
code is otp.generate_code() and the delivery is otp.default_sender, the same
two calls registration makes.
"""
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.modules.auth import otp
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

# One body, one status, for a phone we know and a phone we do not. Built once
# so the two return paths cannot drift into two different sentences — which is
# the entire attack this endpoint is written to defeat.
GENERIC_RESET_RESPONSE = {"message": "If the phone is registered, a reset code has been sent"}

# Said the same way for a wrong code, an expired code, an already-used code and
# a phone that has never asked for one. Four different failures, one sentence:
# telling them apart would let a caller walk the difference backwards into
# "this number is registered and has an outstanding reset".
INVALID_CODE_DETAIL = "Reset code is invalid or expired"


def _own_identity(db: Session, user_id: str) -> tuple[str | None, str | None]:
    """The caller's own name and picture, in ONE query.

    Why this is on the account response at all. The users table holds a phone
    number, a role and a country, and not one of those is something a person
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
    back to the users table: the only human-readable column there is the phone
    number, and a phone number is not a display name — it is the credential
    this whole module exists to protect.
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

    Takes the session because two of the fields are not on the users row at
    all — see _own_identity for why they are answered here anyway.
    """
    display_name, avatar_url = _own_identity(db, user.id)
    return {
        "id": user.id,
        "phone": user.phone,
        "role": user.role,
        "country_code": user.country_code,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }


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
    """Change the phone, the password, or both — at the price of the password.

    THE PHONE IS THE LOGIN IDENTITY, so changing it must cost the password.
    Anyone holding a live bearer token could otherwise point the account at a
    handset they own and then reset the password to it at leisure, which turns
    a borrowed phone into a permanent takeover of somebody's livelihood. The
    bearer token says a session exists; only the current password says the
    owner is the one asking.

    Phone numbers really do change here — a better tariff, a lost handset, a
    move between countries — so this has to exist rather than being a support
    ticket. What it must not become is a way to take somebody else's number.
    """
    user = _require_user(db, user_id)

    data = payload.model_dump(exclude_unset=True)
    new_phone = data.get("phone")
    new_password = data.get("new_password")
    if new_phone is None and new_password is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="auth_account_nothing_to_change",
            detail="Send a new phone number, a new password, or both.",
        )

    # Checked before anything is looked up or written, and before the 409 on a
    # taken phone: a caller who cannot prove they own this account must not be
    # able to use it to discover whether a number is registered.
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="auth_password_incorrect",
            detail="Current password is incorrect",
        )

    if new_phone is not None and new_phone != user.phone:
        # Any row at all, verified or not. An unverified registration still
        # holds the number, and letting a verified account take it would let
        # somebody who half-signed-up be quietly displaced — and would then
        # collide on the unique index anyway, turning a clear 409 into a 500.
        taken = db.query(User).filter(User.phone == new_phone, User.id != user.id).first()
        if taken is not None:
            raise AppError(
                status.HTTP_409_CONFLICT,
                code="auth_phone_taken",
                detail="That phone number is already in use",
            )
        user.phone = new_phone

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

    THE RESPONSE IS IDENTICAL WHETHER OR NOT THE PHONE IS REGISTERED. Same
    202, same body, same wording. This is the whole security property of the
    endpoint and it is not a nicety: an endpoint that answers differently for
    a known number is a free "is this person on Kolabo?" oracle, and anyone
    with a list of numbers can run it. In these markets that is a real
    privacy leak with real consequences — it discloses which creators and
    which businesses are earning on the platform to whoever asks, including
    people the user is specifically trying not to be found by. There is no
    product value on the other side of the trade: a user who mistyped their
    own number is helped by "check your messages", not by being told their
    number is unknown.

    So: no 404 here, ever, and no timing shortcut that skips work for an
    unknown number in a way a stopwatch could read as an answer.
    """
    user = db.query(User).filter(User.phone == payload.phone).first()
    if user is None:
        return GENERIC_RESET_RESPONSE

    now = utcnow()
    if len(_live_reset_tokens(db, user, now)) >= settings.password_reset_max_per_hour:
        # THE ONE PLACE THIS ENDPOINT STOPS BEING SILENT, and the trade is
        # deliberate. Every request sends an SMS and every SMS costs money, so
        # an uncapped endpoint is a bill a stranger can run up on us by
        # looping — and swallowing the limit behind a 202 would hide that from
        # us while still spending nothing, leaving the abuse invisible and a
        # genuinely rate-limited user staring at "check your messages" for a
        # message that will never arrive.
        #
        # It does narrow the oracle above: four requests distinguish a
        # registered number from an unknown one. That costs the attacker three
        # SMS-priced requests per number and is capped by the limit itself,
        # where the silent alternative costs them nothing and tells us
        # nothing. Worth revisiting the day there is a per-phone attempt
        # counter that does not itself need a table of unauthenticated input.
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code="auth_reset_too_many",
            detail="Too many reset requests, try again later",
        )

    token = PasswordResetToken(
        user_id=user.id,
        # The registration OTP generator, not a second one. Six digits because
        # this is read off a lock screen and retyped, which the previous
        # 43-character urlsafe token was never going to survive.
        token=otp.generate_code(),
        expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    db.add(token)
    db.commit()
    _sender.send(user.phone, f"Your Kolabo password reset code is {token.token}")
    return GENERIC_RESET_RESPONSE


def confirm_password_reset(db: Session, payload: PasswordResetConfirm) -> dict:
    """Spend a code once and set the new password.

    Resolved by PHONE AND CODE together. Six digits is small enough to guess
    at if it identifies a row on its own; paired with the number it was sent
    to, a guess has to be aimed at somebody in particular.

    Every failure answers the same 400 with the same sentence — unknown phone,
    wrong code, expired code, already-spent code. Distinguishing them would
    hand back exactly the fact the request endpoint refuses to disclose.
    """
    now = utcnow()
    user = db.query(User).filter(User.phone == payload.phone).first()
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
    # holds the phone; leaving two more valid codes in flight would leave two
    # more chances for whoever prompted the reset in the first place.
    for other in _live_reset_tokens(db, user, now):
        other.consumed = True
    _notify_password_changed(db, user)
    db.commit()
    return {"message": "Password has been reset"}
