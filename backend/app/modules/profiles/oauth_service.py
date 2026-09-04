"""Starting, finishing and renewing a social platform authorization.

A MODULE OF ITS OWN rather than more of service.py, which is already 1,300
lines covering profiles, packages, portfolios, media and enrichment. Nothing
here is a profile rule; it is all handshake and credential handling.

THE THREE RULES THAT ARE EASY TO GET WRONG, and where each is enforced:

  1. THE STATE ROW IS THE AUTHENTICATION FOR THE CALLBACK. The callback is a
     browser redirect arriving from the platform, so it has no bearer token and
     no session — the caller is, as far as this API can tell, an anonymous
     stranger holding a URL. The `user_id` on the row that `state` resolves to
     is the ONLY thing that decides whose profile the connected account lands
     on. Hence: unguessable (secrets.token_urlsafe(32)), single use (`consumed`
     flipped by a conditional UPDATE, so the database refuses a replay rather
     than a read-then-write racing itself), and ten minutes long.
     See complete_authorization, and models.OAuthState.

  2. A REFRESH MAY HAND BACK A DIFFERENT REFRESH TOKEN. TikTok rotates on every
     refresh: the response carries a new refresh_token and retires the one just
     used. Storing the old one back is a failure with NO symptom today — no
     exception, no log line, no failed request — and a creator whose connection
     silently dies at the next renewal. See save_tokens.

  3. NOTHING HERE VERIFIES ANYTHING YET. There is no provider implemented (see
     oauth.build_default_providers), so every account this creates is PENDING,
     exactly like a manual one. The `status = VERIFIED` conditional that
     service.connect_social_account removed belongs beside a callback talking
     to a REAL, reviewed platform app — which is the follow-up that adds one,
     not this change. A badge is only worth what the thing behind it checked.
"""
import logging
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.core.errors import AppError
from app.modules.profiles import models, oauth, service

_log = logging.getLogger("kolabo.profiles.oauth")

# How long an authorization may stay in flight. Longer than any real consent
# screen takes, short enough that a URL left in a browser history or a referer
# header is stale before anybody reads it.
STATE_TTL_MINUTES = 10

# Renew an access token slightly before the platform says it dies, so a token
# that was valid when we checked is not expired by the time the request it was
# fetched for actually lands. Clocks drift and requests take time; a minute
# costs nothing and removes a whole class of intermittent failure.
REFRESH_SKEW_SECONDS = 60

# Selected from configured credentials at import time, exactly as
# service.social_enricher is. A MODULE ATTRIBUTE rather than a call to
# oauth.build_default_providers() inside each function, so the test suite can
# point it at a fake with monkeypatch.setattr — the same seam, and the same
# reason, as test_follower_provenance.py's `social_enricher`.
providers: dict[str, oauth.OAuthProvider] = oauth.build_default_providers()


def _provider(platform: str) -> oauth.OAuthProvider:
    """The provider for a platform, or the refusal a creator can read.

    Unconfigured and unimplemented land on the same sentence on purpose. From
    the creator's side "we have not built this yet" and "this deployment has no
    credentials for it" are the same fact: the button does not work, and
    nothing they can do changes that.
    """
    provider = providers.get(platform)
    if provider is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="oauth_platform_unsupported",
            detail="This platform cannot be connected automatically yet.",
        )
    return provider


def redirect_uri(platform: str) -> str:
    """The callback URL, built once so both halves of the handshake agree.

    OAuth compares this string byte for byte: the value sent with the
    authorization request must equal the one sent to the token endpoint, and
    both must equal what is registered in the platform's console. One function,
    called from both places, is what makes that a fact rather than a habit.
    """
    return f"{settings.api_public_base_url.rstrip('/')}/profiles/oauth/{platform}/callback"


def start_authorization(
    db: Session, user_id: str, platform: str, redirect_to: str | None = None
) -> dict:
    """Mint a state row and return where to send the creator.

    Authenticated: the caller is the account being connected, taken from the
    bearer token by the router's `profile_owner` dependency and never from a
    path. That is what puts a trustworthy `user_id` on the row the callback
    will later read — the whole handshake's identity is decided here, where
    there IS a token, and merely looked up there, where there is not.
    """
    service._require_user(db, user_id)
    provider = _provider(platform)

    state_value = oauth.new_state()
    verifier = oauth.new_code_verifier()
    db.add(
        models.OAuthState(
            state=state_value,
            code_verifier=verifier,
            user_id=user_id,
            platform=platform,
            redirect_to=redirect_to,
            expires_at=models.utcnow() + timedelta(minutes=STATE_TTL_MINUTES),
            consumed=False,
        )
    )
    db.commit()
    return {"authorize_url": provider.authorize_url(state_value, verifier, redirect_uri(platform))}


def complete_authorization(db: Session, platform: str, code: str, state: str) -> dict:
    """Finish the handshake: resolve the state, burn it, exchange the code.

    UNAUTHENTICATED BY NECESSITY. This is a redirect the platform sends the
    creator's browser to; there is no Authorization header to read and there
    never can be. Everything about the request except the state row is under
    the control of whoever holds the URL, which is why the row is checked
    before it is used and used exactly once.
    """
    row = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()

    # An unknown state, and a state minted for a DIFFERENT platform, are the
    # same refusal. Pairing them means a state for tiktok cannot be replayed
    # against instagram's callback to attach an account on a platform the
    # creator never authorised.
    if row is None or row.platform != platform:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="oauth_state_invalid",
            detail="This connection link is not valid. Start again from your profile.",
        )
    if row.consumed:
        # A REPLAY: this URL has been used. It reaches here from a browser
        # history, a referer header leaking the query string to a third party,
        # a shared screenshot, or an attacker who saw one go past. Same
        # sentence as an unknown state — telling the two apart would confirm
        # that a state was real, which is exactly what a replayer wants to
        # learn.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="oauth_state_invalid",
            detail="This connection link is not valid. Start again from your profile.",
        )
    if row.expires_at <= models.utcnow():
        # Its own code, because the creator can act on this one: nothing is
        # wrong, they just took too long, and starting again works.
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="oauth_state_expired",
            detail="This connection link has expired. Start again from your profile.",
        )

    user_id = row.user_id
    verifier = row.code_verifier
    redirect_to = row.redirect_to

    # SINGLE USE, ENFORCED BY THE DATABASE AND NOT BY THE READ ABOVE. The
    # `row.consumed` check is a nicety that produces a clear error; this
    # conditional UPDATE is the actual guarantee. Two callbacks arriving at the
    # same moment — a double-tapped link, a retrying mobile browser — both pass
    # the read, and exactly one of them updates a row, because the WHERE clause
    # is evaluated by the database against the row it is about to write. A
    # read-then-assign would let both through and connect the account twice.
    burned = (
        db.query(models.OAuthState)
        .filter(models.OAuthState.id == row.id, models.OAuthState.consumed.is_(False))
        .update({"consumed": True}, synchronize_session=False)
    )
    db.commit()
    if burned != 1:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="oauth_state_invalid",
            detail="This connection link is not valid. Start again from your profile.",
        )

    # BURNED BEFORE THE EXCHANGE, NOT AFTER, and it is a deliberate trade. A
    # failed exchange costs the creator a fresh start; leaving the state alive
    # so it could be retried would mean a state that survives a failure is a
    # state an attacker can keep trying. The authorization code itself is
    # single-use at the provider anyway, so a retry with the same URL was never
    # going to work twice.
    provider = _provider(platform)
    try:
        tokens = provider.exchange_code(code, verifier, redirect_uri(platform))
    except Exception as exc:  # network, refusal, malformed body
        # The platform's own error text is never shown: it is written for a
        # developer, in English, and it routinely names client ids. It goes to
        # the log, where somebody can act on it.
        _log.warning("OAuth code exchange failed for %s: %s", platform, exc)
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            code="oauth_exchange_failed",
            detail="The platform refused the connection. Nothing was saved.",
        )

    account = _account_for(db, user_id, platform, tokens.provider_user_id)
    save_tokens(db, account.id, tokens)
    db.refresh(account)
    # service._social_out rather than a dict written out again here. It exists
    # precisely so a new column on SocialAccount does not have to be remembered
    # in a fifth place, and re-listing the fields would recreate the drift it
    # was written to prevent.
    return {"account": service._social_out(account), "redirect_to": redirect_to}


def _account_for(
    db: Session, user_id: str, platform: str, provider_user_id: str | None
) -> models.SocialAccount:
    """The SocialAccount these tokens belong to, created if it is a new one.

    MATCHED THROUGH THE TOKEN ROW ON provider_user_id, never on the handle. A
    handle is something its owner can change this afternoon; the platform's own
    id for the account cannot be changed by anybody. So re-authorising an
    account we already hold credentials for updates that account, and
    authorising a different account on the same platform makes a second row —
    which is right, because creators legitimately run two Instagram accounts.

    NOT ADOPTING AN EXISTING MANUAL ROW, and that is the interesting choice. A
    creator who typed "@ama" by hand and then authorises through OAuth gets a
    second row rather than having the first one silently claimed, because
    nothing here can prove the two are the same account: the token exchange
    returns an ID, not a handle, so "adopt the one manual instagram row" would
    be a guess that could quietly attach one account's credentials to another
    account's name. Merging them belongs with the first real provider, which
    will have a user-info call and can compare something.

    THE HANDLE IS A PLACEHOLDER, and the follow-up is named. The exchange gives
    us `provider_user_id` and nothing human-readable; the display handle comes
    from the platform's user-info endpoint, which is enrichment's job and lands
    with the provider that can call it. Until then the id stands in, and the
    account stays PENDING so nothing on a storefront is badged off the back of
    it.
    """
    if provider_user_id:
        existing = (
            db.query(models.SocialAccount)
            .join(
                models.SocialToken,
                models.SocialToken.social_account_id == models.SocialAccount.id,
            )
            .filter(
                models.SocialAccount.user_id == user_id,
                models.SocialAccount.platform == platform,
                models.SocialToken.provider_user_id == provider_user_id,
            )
            .first()
        )
        if existing is not None:
            return existing

    account = models.SocialAccount(
        user_id=user_id,
        platform=platform,
        handle=provider_user_id or platform,
        method="oauth",
        # PENDING, like every other connection. See this module's docstring:
        # the badge belongs beside a provider that has actually been reviewed,
        # and there is no provider yet.
        status=models.PENDING,
        # No number is claimed by an authorization, so no provenance is
        # recorded — the rule connect_social_account already follows: null
        # count means null source, never "a report of nothing".
        follower_count=None,
        follower_source=None,
        follower_verified_at=None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def save_tokens(
    db: Session, social_account_id: str, tokens: oauth.TokenSet
) -> models.SocialToken:
    """Store a TokenSet against one account, replacing whatever was there.

    THE REFRESH TOKEN A PROVIDER RETURNS MAY DIFFER FROM THE ONE YOU SENT IT,
    and honouring that is this function's job. TikTok ROTATES: every refresh
    response carries a new refresh_token and retires the one just used. Writing
    the old value back — because it "is probably still the same", or because
    the update only touched the access token — is a defect with no symptom at
    the time it happens. Nothing throws, nothing logs, the request that
    triggered the refresh succeeds. The connection dies at the NEXT renewal,
    days or weeks later, and reaches us as "my TikTok disconnected itself".

    So: whatever came out of the provider is what goes in, and nothing here
    assumes the old value survived.

    THE ONE THING IT WILL NOT DO IS ERASE ONE. A provider that returns no
    refresh token on a refresh has not revoked anything — Google issues a
    refresh token at authorization time only and omits the field from every
    renewal after it — and blanking the stored value there would break exactly
    the connections this rule exists to protect. Absent means "unchanged";
    present means "replace", whether or not it looks the same. That asymmetry
    is deliberate and is the only exception.
    """
    now = models.utcnow()
    row = (
        db.query(models.SocialToken)
        .filter(models.SocialToken.social_account_id == social_account_id)
        .first()
    )
    if row is None:
        row = models.SocialToken(social_account_id=social_account_id, created_at=now)
        db.add(row)

    row.access_token_ciphertext = encrypt_bytes(tokens.access_token.encode("utf-8"))
    row.access_expires_at = now + timedelta(seconds=tokens.access_expires_in)

    # ROTATION. Written as its own branch, with its own comment, because this
    # is the line somebody will one day "optimise" into
    # `if row.refresh_token_ciphertext is None:` to avoid a re-encryption.
    # test_a_refresh_that_returns_a_different_refresh_token_persists_the_new_one
    # exists to make that edit fail loudly instead of shipping.
    if tokens.refresh_token is not None:
        row.refresh_token_ciphertext = encrypt_bytes(tokens.refresh_token.encode("utf-8"))
        row.refresh_expires_at = (
            now + timedelta(seconds=tokens.refresh_expires_in)
            if tokens.refresh_expires_in is not None
            else None
        )

    row.scope = tokens.scope
    # Only overwritten when the provider actually said something. A refresh
    # response that omits the id has not changed it, and clearing it would
    # break _account_for's ability to recognise this account next time.
    if tokens.provider_user_id is not None:
        row.provider_user_id = tokens.provider_user_id
    row.updated_at = now

    db.commit()
    db.refresh(row)
    return row


def load_access_token(db: Session, social_account_id: str) -> str:
    """A usable access token for an account, renewed on the way out if needed.

    The single entry point for every future caller — the TikTok enricher,
    YouTube Analytics — so that none of them separately decides what "expired"
    means, and none of them has to remember to write the refreshed credentials
    back. Ask for a token; get one that works, or a refusal to show the creator.
    """
    row = (
        db.query(models.SocialToken)
        .filter(models.SocialToken.social_account_id == social_account_id)
        .first()
    )
    if row is None:
        raise _reconnect_needed()

    if row.access_expires_at > models.utcnow() + timedelta(seconds=REFRESH_SKEW_SECONDS):
        return decrypt_bytes(row.access_token_ciphertext).decode("utf-8")

    if row.refresh_token_ciphertext is None:
        raise _reconnect_needed()
    if row.refresh_expires_at is not None and row.refresh_expires_at <= models.utcnow():
        raise _reconnect_needed()

    account = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.id == social_account_id)
        .first()
    )
    if account is None:
        raise _reconnect_needed()

    provider = _provider(account.platform)
    try:
        fresh = provider.refresh(decrypt_bytes(row.refresh_token_ciphertext).decode("utf-8"))
    except Exception as exc:
        # A refused refresh is usually a creator who revoked us in the
        # platform's own settings, which is their right and not an error worth
        # alarming about — but it does mean the connection is over, and the
        # sentence says the only thing that helps.
        _log.warning("OAuth refresh failed for account %s: %s", social_account_id, exc)
        raise _reconnect_needed()

    save_tokens(db, social_account_id, fresh)
    return fresh.access_token


def _reconnect_needed() -> AppError:
    """The one refusal for "these credentials will not work any more".

    409 rather than 401: nothing is wrong with the CALLER's authentication —
    they are signed in perfectly well — and nothing is wrong with their request
    either, which rules out 400. What is wrong is stored state that has to be
    renewed by a person, which is what a conflict says.
    """
    return AppError(
        status.HTTP_409_CONFLICT,
        code="oauth_token_expired",
        detail="Your connection to this platform has expired. Reconnect it from your profile.",
    )


def revoke(db: Session, social_account_id: str) -> None:
    """Forget the credentials for an account, keeping the account itself.

    Deleting the row rather than blanking it: there is no state between "has
    credentials" and "does not", and a row of nulls is one more thing somebody
    later has to interpret. It is also the smaller surface — a deleted secret
    cannot leak.

    NOT THE SAME AS DISCONNECTING. service.delete_social_account removes the
    account from the creator's profile, which is a decision about their
    storefront. This drops only the secret, and the account stays visible with
    whatever it already showed.

    Silent when there is nothing to forget: revoking twice is not an error, and
    a caller cleaning up after a refused refresh should not have to check first.

    Telling the PLATFORM to revoke is a provider's job and needs a method on the
    protocol; it lands with the first provider that has a revocation endpoint.
    Doing it here would mean guessing a URL for a platform nobody has
    implemented.
    """
    row = (
        db.query(models.SocialToken)
        .filter(models.SocialToken.social_account_id == social_account_id)
        .first()
    )
    if row is None:
        return
    db.delete(row)
    db.commit()
