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

  2. A REFRESH MAY HAND BACK A DIFFERENT REFRESH TOKEN — OR THERE MAY BE NO
     REFRESH TOKEN AT ALL. TikTok rotates on every refresh: the response
     carries a new refresh_token and retires the one just used. Storing the old
     one back is a failure with NO symptom today — no exception, no log line,
     no failed request — and a creator whose connection silently dies at the
     next renewal. Meta is the other end of the same axis: it issues no refresh
     token ever, so its TokenSet carries None and load_access_token refuses on
     a null column rather than renewing. Both are handled in save_tokens, and
     the rule that covers both is "absent means unchanged, present means
     replace".

  3. NOTHING HERE VERIFIES A HANDLE, EVEN NOW THAT A REAL PROVIDER EXISTS.
     There is a Meta provider (see oauth.MetaOAuthProvider), so a Facebook
     connection is a genuine authorization by the creator against a real app —
     and every account this creates is still PENDING, exactly like a manual
     one. The `status = VERIFIED` conditional that service.connect_social_account
     removed is NOT restored here. A reviewed provider is a much better
     argument for a badge than a string in a request body ever was, and the
     case for turning it on is made in the pull request that added the
     provider; but a badge is a product promise about who somebody is, and
     switching it on is a decision to take deliberately rather than to inherit
     from a plumbing change. What the provider DOES earn honestly is the
     follower number: see _apply_audience.
"""
import logging
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.core.errors import AppError
from app.core.platforms import PLATFORMS_WITH_AUDIENCE
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

# The mobile app's deep link scheme, and the second half of the redirect
# allowlist. A phone has no origin to compare: the app registers kolabo:// with
# the operating system, and the browser hands any such URL to whatever claims
# it. There is nothing narrower to check than the scheme, which is why the web
# half of the allowlist is an origin and this half is a prefix.
MOBILE_REDIRECT_SCHEME = "kolabo://"

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

    IT IS ONLY AS RIGHT AS settings.api_public_base_url, whose default is the
    local dev API. A deployed server that never sets API_PUBLIC_BASE_URL builds
    every redirect_uri against localhost:8000, which no platform will accept
    and which Meta refuses as `redirect_uri_mismatch` — an error that names
    neither this function nor that setting.
    """
    return f"{settings.api_public_base_url.rstrip('/')}/profiles/oauth/{platform}/callback"


def redirect_allowed(target: str) -> bool:
    """Whether a client's `redirect_to` is somewhere we are willing to send a browser.

    TWO THINGS ARE ALLOWED AND NOTHING ELSE IS: any URL on the web app's own
    origin (settings.web_public_base_url), and any kolabo:// deep link.

    AN ORIGIN COMPARISON, NOT A PREFIX ONE, and that distinction is the whole
    security value of this function. "https://app.kolabo.africa" is a prefix of
    "https://app.kolabo.africa.evil.example", and
    "https://app.kolabo.africa@evil.example" is a URL whose HOST is
    evil.example and whose first half a browser discards as userinfo. Both are
    the standard way an allowlist leaks, and both are refused here because
    neither one's netloc EQUALS the configured netloc. Scheme is compared too,
    so an https deployment cannot be redirected to its own cleartext twin.
    """
    if target.lower().startswith(MOBILE_REDIRECT_SCHEME):
        return True
    base = urlsplit(settings.web_public_base_url)
    if not base.scheme or not base.netloc:
        # A deployment with no web origin configured allows no web redirect at
        # all. For an allowlist whose only job is to be narrow, refusing
        # everything is the correct reading of "not configured".
        return False
    here = urlsplit(target)
    return (here.scheme.lower(), here.netloc.lower()) == (
        base.scheme.lower(),
        base.netloc.lower(),
    )


def _allowlisted_or_discarded(
    redirect_to: str | None, user_id: str, platform: str
) -> str | None:
    """The destination to store on the state row, or None if we will not honour it.

    DISCARDED, NEVER RAISED, and that trade is the reason this function exists
    rather than an inline `if`. A redirect_to outside the allowlist is a client
    bug or somebody probing for an open redirect. It is never something a
    creator typed, chose or can fix, so failing their connection over it
    punishes the only party in the exchange who did nothing wrong. The value is
    dropped, the handshake continues, and the creator ends up on the callback's
    JSON instead of back in the app.

    IT ALSO KEEPS THIS CHANGE FREE OF A NEW ERROR CODE. Refusing would need
    one, and a new code needs a French and an English sentence in both
    web/src/lib/errorMessages.ts and mobile/src/lib/errorMessages.ts, each
    about 50 KB, or test_error_codes.py and errorMessages.test.ts go red.
    Churning two translation catalogues to deliver a refusal that no creator
    can act on is the wrong way round.

    %r rather than %s on the value: it is attacker-controlled text on its way
    into a log file, and repr escapes the newlines somebody would otherwise use
    to forge a log line of their own around it.
    """
    if redirect_to is None or redirect_allowed(redirect_to):
        return redirect_to
    _log.warning(
        "Discarding redirect_to outside the allowlist for user %s on %s: %r "
        "(allowed: the %s origin, or %s)",
        user_id,
        platform,
        redirect_to,
        settings.web_public_base_url,
        MOBILE_REDIRECT_SCHEME,
    )
    return None


def _client_redirect(redirect_to: str | None, key: str, value: str) -> str | None:
    """`redirect_to` with one marker on its query string, or None to stay on JSON.

    THE ONLY PLACE A Location VALUE IS BUILT, which is what makes the allowlist
    a property of the callback rather than of the call sites that remembered to
    ask. Nothing failing redirect_allowed can come out of here, whatever is on
    the row. That is not belt and braces for the check in start_authorization:
    rows written before that check existed hold whatever a client sent, and at
    the moment this ships some of them have ten minutes of life left.

    BUILT WITH urllib RATHER THAN BY CONCATENATION, because both halves of the
    input are awkward. `redirect_to` may already carry a query string, and
    gluing "?connected=x" onto one produces a URL with two question marks and a
    parameter nobody can parse; it may carry a fragment, which has to stay
    after the query rather than before it; and kolabo:// is a custom scheme
    that urlsplit understands and a hand-rolled "?" does not.
    """
    if not redirect_to or not redirect_allowed(redirect_to):
        return None
    parts = urlsplit(redirect_to)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append((key, value))
    return urlunsplit(parts._replace(query=urlencode(query)))


def success_redirect(redirect_to: str | None, platform: str) -> str | None:
    """Where to send a creator whose connection worked, if anywhere.

    The marker names the platform, so a client that offered two connect buttons
    on one screen can tell which one has just come back.
    """
    return _client_redirect(redirect_to, "connected", platform)


def failure_redirect(db: Session, platform: str, state: str, code: str) -> str | None:
    """Where to send a creator whose connection failed, if anywhere.

    A FAILURE HAS TO REDIRECT TOO, and saying so is this function's whole
    reason for existing. A creator who declines a permission on the consent
    screen, or who takes eleven minutes over it, has done nothing unusual;
    leaving them on a JSON error page is the same defect as leaving a
    successful one there, and it is the more likely of the two to be met with
    "the app is broken".

    `code` is the AppError's own code, carried so the client can render the
    sentence it already holds for it. NOTHING NEW IS INVENTED HERE: every
    string this can carry is one that already exists in both translation
    catalogues.

    RE-READS THE STATE ROW rather than having complete_authorization carry a
    destination out through each of the four places it raises. One SELECT, on a
    path that is ending a request anyway, against threading an HTTP concern
    through a function whose subject is the handshake.
    """
    row = db.query(models.OAuthState).filter(models.OAuthState.state == state).first()
    if row is None or row.platform != platform:
        # An unknown state names no destination anybody ever validated, so
        # there is nowhere to go and the JSON refusal stands. The platform is
        # compared for the same reason complete_authorization compares it: a
        # state minted for tiktok must not get to choose where instagram's
        # callback sends somebody.
        return None
    return _client_redirect(row.redirect_to, "social_error", code)


def start_authorization(
    db: Session, user_id: str, platform: str, redirect_to: str | None = None
) -> dict:
    """Mint a state row and return where to send the creator.

    Authenticated: the caller is the account being connected, taken from the
    bearer token by the router's `profile_owner` dependency and never from a
    path. That is what puts a trustworthy `user_id` on the row the callback
    will later read — the whole handshake's identity is decided here, where
    there IS a token, and merely looked up there, where there is not.

    A VERIFIER IS MINTED FOR EVERY PLATFORM, INCLUDING THOSE THAT IGNORE IT.
    PKCE is offered to the provider rather than imposed on it: authorize_url is
    handed the verifier and decides what to send, and the Meta provider sends
    nothing because Meta's manual login flow does not document PKCE. The
    unused row costs one short string that is discarded within ten minutes,
    which is a far better trade than making the shape of the state row depend
    on which platform it was minted for.

    `redirect_to` IS CHECKED HERE, WHILE THE CREATOR IS STILL ON KOLABO. The
    callback turns that value into a 302, which makes it an open-redirect
    surface and means it needs an allowlist; the only real question is where
    the allowlist runs. Here, because the alternative is discovering that a
    destination is refused at the callback, which is AFTER the creator has
    already read a consent screen and granted permissions on somebody else's
    platform. Refusing somebody before they leave costs them a click; refusing
    them after costs them the whole errand.

    A value that fails the check is dropped rather than refused, and
    _allowlisted_or_discarded says why.
    """
    service._require_user(db, user_id)
    provider = _provider(platform)
    redirect_to = _allowlisted_or_discarded(redirect_to, user_id, platform)

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

    THE ROW'S `redirect_to` COMES BACK WITH THE ACCOUNT, and the router decides
    what to do with it: a 302 when there is one, and the JSON body this has
    always returned when there is not. That decision is HTTP shape rather than
    handshake, so it belongs there. What belongs here is the guarantee behind
    it, which is that the value on the row was allowlisted by
    start_authorization before it was ever written down.
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
    # AFTER THE TOKENS ARE STORED, AND NEVER BEFORE. This is the best-effort
    # half of a connection: it may fail, and the connection it describes has to
    # survive it failing. Ordering it here rather than earlier is what makes
    # that true rather than hopeful — by the time it runs, everything that
    # matters is already committed.
    _apply_audience(db, account, provider, tokens)
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
    account's name. Merging them belongs with a provider that has a user-info
    call and can compare something — the Meta provider now has one, and doing
    the merge is still its own change rather than a side effect of this one.

    THE HANDLE STARTS AS THE ID AND MAY NOT STAY THAT WAY. The exchange gives
    us `provider_user_id` and nothing human-readable, so the id stands in.
    _apply_audience below replaces it the moment a provider can name the
    account unambiguously — for Meta, when the creator manages exactly one
    Page. Where it cannot, the id remains on show, which is ugly and honest and
    is fixed by the creator choosing a Page in the app.

    The account stays PENDING either way, so nothing on a storefront is badged
    off the back of it.
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
        # a real reviewed provider is a better argument for a badge than
        # anything that came before it, and turning one on is still a decision
        # somebody makes rather than a consequence of adding a provider.
        status=models.PENDING,
        # No number is claimed by an authorization, so no provenance is
        # recorded — the rule connect_social_account already follows: null
        # count means null source, never "a report of nothing". If the provider
        # can read one, _apply_audience fills all three columns together.
        follower_count=None,
        follower_source=None,
        follower_verified_at=None,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _apply_audience(
    db: Session,
    account: models.SocialAccount,
    provider: oauth.OAuthProvider,
    tokens: oauth.TokenSet,
) -> None:
    """Ask a provider what the account it just connected actually shows.

    THIS IS THE FIRST PLACE IN THE CODEBASE THAT EARNS models.PLATFORM_API
    HONESTLY, which is worth stating plainly because the constant already
    existed. #161 defined it as "the platform itself stated it, in an API
    response about its own account" — and until now the only thing that could
    set it was service._apply_enrichment, reading a handle the creator TYPED
    through a Graph token belonging to Kolabo. That is the platform speaking
    about an account nobody proved the creator owns. Here the creator
    authorised us on the platform's own consent screen, the token is theirs,
    and the number is their own Page's. Same constant, much better claim.

    So all three provenance columns are written together, per #161's rule: the
    count, PLATFORM_API, and a follower_verified_at date, which only a platform
    ever earns.

    BEST EFFORT, ALWAYS. Every failure is a log line and a return. This runs
    after the tokens are stored and the connection exists, so nothing it does
    may undo that — the same contract enrichment.py keeps, for the same reason:
    a follower count is worth a great deal less than a connection.

    OPT IN BY getattr, NOT BY PROTOCOL. oauth.AudienceReader is a Protocol of
    its own and this looks for the method rather than requiring it. Making it a
    fourth method on OAuthProvider would have meant every provider grew one
    whether or not its platform has anything to read — including the
    FakeProvider that pins this entire mechanism in test_social_oauth.py, which
    would then have had to be edited to accommodate a real provider arriving.
    A provider opts IN by implementing it; nothing has to change to opt out.
    """
    read = getattr(provider, "read_audience", None)
    if read is None:
        return
    try:
        snapshot = read(tokens)
    except Exception as exc:
        # A provider is supposed to swallow its own failures — oauth.
        # AudienceReader says "NEVER RAISES" — and this catch is for the one
        # that forgets. Belt and braces is right here specifically because the
        # cost of being wrong is asymmetric: the account is already connected
        # and its tokens are already saved, so an exception escaping this
        # function would turn a completed handshake into `oauth_exchange_failed`
        # for a creator whose connection actually worked.
        _log.warning("Audience read failed for %s: %s", account.platform, exc)
        return
    if snapshot is None:
        return

    changed = False
    if snapshot.handle and snapshot.handle != account.handle:
        # The numeric id _account_for stood in with, replaced by something a
        # brand can read. The id is not lost — it lives on the token row, which
        # is what a re-authorisation is matched against.
        account.handle = snapshot.handle
        changed = True
    # THE SAME RULE connect_social_account AND update_social_account FOLLOW: a
    # platform that publishes no audience metric cannot back a number, so one
    # is not recorded for it however it arrived. Facebook is in this set; the
    # guard is here for the providers that come next, so that the rule lives in
    # every path that can write the column rather than in two of the three.
    if snapshot.follower_count is not None and account.platform in PLATFORMS_WITH_AUDIENCE:
        account.follower_count = snapshot.follower_count
        account.follower_source = models.PLATFORM_API
        account.follower_verified_at = models.utcnow()
        changed = True
    if changed:
        db.commit()


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

    IT IS ALSO WHAT MAKES META SAFE TO STORE. Meta issues no refresh token at
    any point, so every Meta TokenSet carries None and lands in the "absent"
    branch — on the first authorization there is nothing to blank, and on a
    reconnection the column is null already. A provider with no refresh token
    therefore needs no special case here, which is the whole reason its
    provider could be written without touching this function.
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

    A PLATFORM WITH NO REFRESH TOKEN NEEDS NO CODE HERE, and Meta proves it.
    Its rows have a null refresh_token_ciphertext, so an expired Meta token
    reaches the `_reconnect_needed()` below and the creator is asked to
    reconnect — several lines before this function would look up a provider or
    call refresh(). That is why oauth.MetaOAuthProvider.refresh can raise
    rather than pretend: it is unreachable through the only path that calls it.
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
