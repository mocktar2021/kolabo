"""OAuth against the social platforms: the mechanism, and the first provider.

WHY THIS EXISTS. Connecting a social account is the one claim on this platform
a creator cannot settle by typing. Before #162 every connection was a handle
plus a screenshot link that an admin read by hand (admin.service.decide_social),
because there was no authorization URL, no callback, no token exchange and no
stored token anywhere in this repo.

THE PLATFORM THAT NEEDS THIS MOST IS STILL NOT THE ONE THAT GOT IT FIRST, and
the reason is worth writing down. TikTok's /v2/user/info/ answers ONLY for a
token belonging to the creator being read: there is no public handle lookup of
the kind YouTube's `forHandle` or Instagram's Business Discovery gives us — see
enrichment.py, where TikTok is the single entry that reads "Not yet wired". So
a token is not an optimisation for TikTok, it is the precondition. But TikTok's
Login Kit will not issue a client id until an application has been reviewed,
and Meta's App Review wants a video of the permissions ACTUALLY IN USE. With an
empty registry nothing could connect, on any platform, so there was nothing to
film and no way to open either review. Meta is first because Meta is the one
whose review can be opened from where we already stand: Business Verification
is approved, the app exists, and what was missing was a working handshake.

WHAT IS HERE. The shape of a provider, the registry that holds them, and one
implementation. The mechanism itself is still proved against a FAKE provider in
backend/tests/test_social_oauth.py, which needs no network, no developer
account and no app review to run in CI; MetaOAuthProvider is proved separately
in test_meta_oauth.py against a fake HTTP layer. Keeping those apart is
deliberate: a change to Meta's endpoints must not be able to quietly weaken the
state, encryption and rotation rules, and a change to those rules must fail in
a file whose name says so.

THE SHAPE MIRRORS enrichment.py DELIBERATELY, and now in one more way than it
used to. A Protocol, concrete implementations IN THE SAME MODULE beside it,
selection at import time from configured credentials, and nothing registered
when nothing is configured. That is why MetaOAuthProvider lives here rather
than in an oauth_meta.py: enrichment.py holds YouTubeEnricher, InstagramEnricher
and FacebookEnricher next to the SocialEnricher protocol they implement, and a
second arrangement for the same idea is a second thing to learn. With no
credentials build_default_providers() still returns an EMPTY registry and
`oauth_platform_unsupported` is still the sentence a creator gets — a feature
with no credentials reports itself unavailable rather than half working.

THE THREE THINGS ABOUT META THAT ARE NOT LIKE THE OTHER PLATFORMS, stated here
because the next provider author will read this docstring and should not carry
them over:

  * IT ISSUES NO REFRESH TOKEN. Not "not for this grant" — none, ever. The
    protocol's refresh() is therefore unimplementable for Meta and says so out
    loud. See MetaOAuthProvider.refresh.
  * THE TOKEN IT FIRST HANDS BACK IS WORTHLESS. A code buys a short-lived user
    token that expires "in hours"; it has to be exchanged again, immediately,
    for the ~60 day one. See MetaOAuthProvider.exchange_code.
  * THE CONSENT SCREEN IS ON A DIFFERENT HOST from everything else. www.
    facebook.com for the dialog, graph.facebook.com for every call after it.
"""
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.core.config import settings

_log = logging.getLogger("kolabo.profiles.oauth")

# Bytes of entropy behind the CSRF state. 32 bytes is 256 bits, rendered by
# token_urlsafe as 43 characters.
#
# THE STATE IS THE ONLY THING THAT SAYS WHOSE ACCOUNT THE CALLBACK IS FOR — see
# models.OAuthState — so guessing one is taking over the connection. This is
# not a request id and it is not a correlation key; it is a credential that
# happens to travel in a query string.
STATE_BYTES = 32

# Bytes behind the PKCE code verifier. RFC 7636 requires the verifier to be
# 43-128 characters from the unreserved set; token_urlsafe(64) is 86, which
# sits comfortably inside that and well above the 32-byte floor the RFC calls
# for.
CODE_VERIFIER_BYTES = 64

# How long any call to a platform's token or Graph endpoint may take.
#
# LONGER THAN enrichment.TIMEOUT_SECONDS (6.0), and the difference is about
# what happens when it runs out rather than about how slow the endpoints are.
# An enrichment timeout leaves a profile field empty and the creator never
# knows; a token-exchange timeout is a creator looking at a failed connection
# holding an authorization code that has already been spent at the provider and
# cannot be retried. Four more seconds to avoid making somebody start the whole
# handshake again is the right way round.
HTTP_TIMEOUT_SECONDS = 10.0


def new_state() -> str:
    """A fresh CSRF state. secrets, never random: see STATE_BYTES."""
    return secrets.token_urlsafe(STATE_BYTES)


def new_code_verifier() -> str:
    """A fresh PKCE verifier, kept server side until the token exchange."""
    return secrets.token_urlsafe(CODE_VERIFIER_BYTES)


def code_challenge(verifier: str) -> str:
    """The S256 challenge for a verifier: base64url(sha256(verifier)), unpadded.

    S256 rather than `plain`, which the RFC permits and which is worthless: a
    plain challenge IS the verifier, so anything that can read the
    authorization request can redeem the code. Providers that support PKCE at
    all support S256, and a provider that does not is one whose implementation
    can say so out loud rather than silently downgrading here.

    The padding is stripped because base64url in OAuth is unpadded everywhere
    (RFC 7636 section 4.2 is explicit), and a stray "=" is rejected by some
    providers and quietly accepted by others, which is the worst combination
    for something that must match byte for byte.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _int_at_least(value: object, minimum: int) -> int | None:
    """An int out of whatever a platform put in a JSON field, or None.

    Platforms send numbers as strings, as numbers, and sometimes not at all,
    and one field's floor is not another's. `expires_in` has a minimum of 1: a
    zero would store a token that is already expired, which then reads like a
    bug in this code rather than like the malformed response it was. A follower
    count has a minimum of 0, because a Page with no followers yet is a fact
    about that Page and a brand is entitled to see it.
    """
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= minimum else None


@dataclass
class TokenSet:
    """What a provider hands back from an authorization or a refresh.

    A dataclass rather than the provider's raw JSON, because every platform
    spells these differently — expires_in against expires_at, open_id against
    sub against user_id — and the service that stores them should not have to
    know which. Translating happens once, inside each provider.

    `access_expires_in` and `refresh_expires_in` are SECONDS FROM NOW, not
    absolute times, because that is what every provider actually sends and
    converting in one place (oauth_service.save_tokens) beats converting in
    each provider and hoping they all used the same clock.

    `refresh_token` is optional in both directions and it is the field with the
    trap in it. See save_tokens: what comes back from a REFRESH may not be what
    was sent to it — and, for Meta, there is no refresh token in either
    direction at any point.
    """

    access_token: str
    refresh_token: str | None
    access_expires_in: int
    refresh_expires_in: int | None
    scope: str | None
    provider_user_id: str | None


class OAuthProvider(Protocol):
    """One platform's half of the handshake.

    Three methods and no state of their own: everything that has to survive a
    round trip through the creator's browser lives in oauth_states, and
    everything that has to survive the session lives in social_tokens. A
    provider is a translator between this platform's HTTP and TokenSet, which
    is what makes it testable without a network and replaceable without
    touching the service.

    IMPLEMENTATIONS RAISE ON FAILURE and do not return None. That is the
    opposite of SocialEnricher in enrichment.py, and the difference is what the
    caller can do about it: enrichment failing means a profile field stays
    empty, which is survivable and must never break account connection, while a
    token exchange failing means there is no connection at all and the creator
    has to be told. oauth_service turns the exception into
    `oauth_exchange_failed`.
    """

    platform: str

    def authorize_url(self, state: str, code_verifier: str, redirect_uri: str) -> str:
        """Where to send the creator's browser to ask for their permission.

        Takes the VERIFIER, not the challenge, so that the S256 derivation and
        the choice of method stay inside the provider that has to agree with
        its own token endpoint about them.

        A PROVIDER MAY DECLINE TO USE IT AT ALL, and one already does. The
        parameter is what the service can offer, not what the provider must
        send: MetaOAuthProvider accepts the verifier and forwards nothing,
        because Meta's manual login flow does not document PKCE and a challenge
        an endpoint ignores is a claim of protection that is not there. That
        choice belongs to the provider precisely because only it knows what its
        own token endpoint will do with the answer.
        """
        ...

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        """Trade the one-time code from the callback for tokens."""
        ...

    def refresh(self, refresh_token: str) -> TokenSet:
        """Renew an expired access token.

        MAY RETURN A DIFFERENT REFRESH TOKEN THAN THE ONE PASSED IN. TikTok
        rotates on every refresh. Callers must persist whatever comes back —
        see oauth_service.save_tokens, which is the only caller and which
        carries the rule.

        AND MAY NOT BE IMPLEMENTABLE AT ALL. Meta issues no refresh token of
        any kind, so there is nothing to pass in and this method raises for
        that provider. It is not reached: a Meta TokenSet carries
        refresh_token=None, the column stays null, and load_access_token
        refuses with `oauth_token_expired` before it would ever call here. See
        MetaOAuthProvider.refresh for the whole argument, including what a real
        renewal for Meta would have to look like if one is ever wanted.
        """
        ...


@dataclass
class AudienceSnapshot:
    """What a provider can say about the account it has just connected.

    SEPARATE FROM TokenSet BECAUSE IT IS A DIFFERENT KIND OF CLAIM. A TokenSet
    is a credential — it either works or there is no connection. This is a fact
    about an audience, and failing to get it must leave the connection
    standing: the same contract SocialEnricher keeps in enrichment.py, for the
    same reason.

    Both fields are optional and None is an ordinary answer rather than an
    error. `handle` is a human-readable name to show instead of the numeric id
    the exchange returned. `follower_count` is a number the platform stated
    about its own account, which is the only kind that earns models.PLATFORM_API
    and a follower_verified_at date (#161).
    """

    handle: str | None
    follower_count: int | None


class AudienceReader(Protocol):
    """The OPTIONAL second half of a provider: what it can read once connected.

    NOT A FOURTH METHOD ON OAuthProvider, and that is the point. Putting it
    there would mean every provider had to grow one whether or not its platform
    has anything to read — including the FakeProvider in test_social_oauth.py
    that pins the whole mechanism, which would then have had to be edited to
    accommodate a real provider arriving. oauth_service._apply_audience looks
    for `read_audience` with getattr and skips a provider that has none, so a
    provider opts IN by implementing it and nothing at all has to change to opt
    out.

    NEVER RAISES. Returning None on any failure — network, refusal, a response
    shape nobody expected — is the contract, because this runs AFTER the
    account is connected and the tokens are stored. An exception escaping here
    would turn a successful connection into a failed one over a follower count.
    """

    def read_audience(self, tokens: TokenSet) -> AudienceSnapshot | None:
        ...


# ---------------------------------------------------------------------------
# Meta (Facebook)
# ---------------------------------------------------------------------------

# TWO HOSTS, AND MIXING THEM UP IS THE FIRST MISTAKE EVERYBODY MAKES. The
# consent dialog is served from www.facebook.com and nowhere else; every other
# call in this provider — the token exchange, the long-lived exchange, /me,
# /accounts — goes to graph.facebook.com. Pointing the dialog at the Graph host
# does not produce an error, it produces a page that is not a consent screen.
META_AUTHORIZE_HOST = "https://www.facebook.com"
META_GRAPH_HOST = "https://graph.facebook.com"

# What a creator is asked for, and deliberately nothing beyond it. App Review
# grants permissions one at a time against a demonstrated use, so a scope in
# this tuple that the submitted screencast does not show being used is a
# rejected submission rather than a harmless extra.
#
#   pages_show_list        lists the Pages this person manages. Without it,
#                          {user-id}/accounts answers with an empty set and
#                          there is no Page to connect at all.
#   pages_read_engagement  reads a Page's own data, which is where
#                          followers_count comes from.
#
# COMMA SEPARATED, which is Meta's spelling and not OAuth 2.0's space. A
# space-joined scope string is not rejected; it is read as one permission with
# an odd name, which is granted to nobody, and the handshake then succeeds with
# no permissions at all.
META_SCOPES = ("pages_show_list", "pages_read_engagement")

# What a long-lived user token is assumed to be worth when Meta does not say.
# Meta's own wording is that these "generally last about 60 days", and the
# token response normally carries an expires_in that says so precisely — this
# is only the floor under a response that omits it. Erring short is the safe
# direction: the cost of understating it is that a creator is asked to
# reconnect a little early, and the cost of overstating it is a connection that
# reports itself healthy while every call it makes is refused.
META_LONG_LIVED_FALLBACK_SECONDS = 60 * 24 * 60 * 60


class MetaOAuthError(RuntimeError):
    """A refusal from Meta, reduced to the parts of it worth logging.

    Its own class so the message can be assembled from Meta's error envelope
    rather than from the raw response body. `fbtrace_id` is the one string
    Meta's support will ask for and is the reason this exists at all; a body
    logged whole is both unbounded and a plausible way to write a bearer token
    into a log file, since error text routinely quotes its input back.

    NEVER REACHES A CREATOR. oauth_service turns every exception out of a
    provider into `oauth_exchange_failed` and logs this beside it.
    """


class MetaOAuthProvider:
    """Facebook's half of the handshake: manual login, Graph, and no refresh.

    WHAT A SUCCESSFUL CONNECTION ACTUALLY COSTS, in round trips, because it is
    more than the one this protocol suggests:

        1. the browser hits www.facebook.com/{version}/dialog/oauth and comes
           back to our callback with a code;
        2. graph.facebook.com/{version}/oauth/access_token turns that code into
           a SHORT-LIVED user token;
        3. the same endpoint, with grant_type=fb_exchange_token, turns that
           into a long-lived one — the only token that is ever stored;
        4. /me?fields=id names the person, which is what a re-authorisation is
           matched on;
        5. later, and separately, {user-id}/accounts lists their Pages.

    Steps 2 to 4 are the exchange and a failure in any of them is a failed
    connection. Step 5 is read_audience, runs after the tokens are saved, and
    can fail all it likes without costing the creator anything.

    PKCE IS DELIBERATELY NOT SENT. The service mints a verifier for every
    authorization (oauth_service.start_authorization does it unconditionally)
    and hands it to authorize_url and exchange_code; this provider accepts both
    and forwards neither. Meta does not document PKCE for the manual login flow
    these endpoints belong to — its PKCE documentation is scoped to the
    OIDC/limited-login flow, which is a different handshake with different
    endpoints — so a code_challenge here is a parameter the authorization
    server is under no obligation to remember, and a code_verifier at the token
    endpoint is a parameter it is under no obligation to check. Sending them
    anyway would not be harmful; it would be worse than harmless, because it
    would look from this code like the exchange is PKCE-protected when nothing
    on the other side has agreed to protect it.

    WHAT ACTUALLY PROTECTS THE EXCHANGE, since it is not PKCE:

      * the code is single-use and short-lived at Meta;
      * the token endpoint requires client_secret, which lives on the server
        and never enters a browser — so an intercepted code cannot be redeemed
        by whoever intercepted it. That is the classic confidential-client
        argument, and PKCE exists for PUBLIC clients that cannot make it;
      * redirect_uri must match byte for byte, at both steps, what is
        registered in the app's console — see oauth_service.redirect_uri and
        settings.api_public_base_url;
      * the state row, which is the whole security surface of the callback and
        is unaffected by any of this. See models.OAuthState.

    The verifier is still minted, stored and unused, which costs one short
    string in a row that is discarded within ten minutes. Removing it for this
    provider would mean making the state row's shape depend on which platform
    it is for, which is a worse trade than an unused column.
    """

    platform = "facebook"

    def __init__(self, app_id: str, app_secret: str, version: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.version = version

    # -- the handshake -----------------------------------------------------

    def authorize_url(self, state: str, code_verifier: str, redirect_uri: str) -> str:
        """The consent screen, on www.facebook.com.

        `code_verifier` is accepted and NOT USED — see the class docstring for
        the whole argument. The signature keeps it because the protocol offers
        it, not because anything here wants it.
        """
        params = {
            "client_id": self.app_id,
            # Byte for byte the same string exchange_code will send, because
            # both take it from oauth_service.redirect_uri. Meta compares them
            # and answers redirect_uri_mismatch, which names neither of them.
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(META_SCOPES),
        }
        return f"{META_AUTHORIZE_HOST}/{self.version}/dialog/oauth?{urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        """Trade the callback's code for a LONG-LIVED user token.

        TWO CALLS, AND THE SECOND ONE IS THE ENTIRE POINT OF THIS METHOD.
        Meta's token endpoint answers an authorization code with a SHORT-LIVED
        user token, which Meta's own documentation describes as expiring "in
        hours". Storing that is a connection that dies before the creator has
        finished onboarding, and it fails in the worst available way: nothing
        here would know anything had gone wrong, because the exchange
        succeeded. So the short-lived token never leaves this method and never
        reaches oauth_service.save_tokens — it exists only long enough to be
        spent on the fb_exchange_token call that turns it into the ~60 day one.

        test_meta_oauth.py asserts exactly that: the string that ends up in the
        database is the long-lived token and is not the short-lived one.
        """
        short_lived = self._graph(
            "oauth/access_token",
            {
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                # No code_verifier. See the class docstring.
            },
        )
        short_token = short_lived.get("access_token")
        if not short_token:
            raise MetaOAuthError("the token endpoint returned no access_token")

        long_lived = self._graph(
            "oauth/access_token",
            {
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_token,
            },
        )
        access_token = long_lived.get("access_token")
        if not access_token:
            raise MetaOAuthError("fb_exchange_token returned no access_token")

        return TokenSet(
            access_token=access_token,
            # NOT AN OVERSIGHT, NOT A TODO, AND NOT SOMETHING A LATER PR FILLS
            # IN. Meta issues no refresh token. save_tokens reads None as
            # "unchanged" rather than "revoked", so returning it blanks
            # nothing; see refresh() below for what renewal would have to be.
            refresh_token=None,
            access_expires_in=(
                _int_at_least(long_lived.get("expires_in"), 1)
                or META_LONG_LIVED_FALLBACK_SECONDS
            ),
            refresh_expires_in=None,
            # NOTHING IS CLAIMED ABOUT SCOPE, and None is the honest answer
            # rather than a gap. Meta's token response carries no scope at all,
            # so the only string available here is the one we ASKED for — and
            # SocialToken.scope is documented as "the scopes the platform
            # actually granted, which is not always what was asked for". Writing
            # the request into a column that means the grant would turn a
            # question into an answer, and it is the exact question somebody
            # will need honestly answered the first time a creator unticks a
            # permission on the consent screen. What was granted is readable
            # from /me/permissions, and belongs with the code that has to tell
            # "they declined it" from "the integration is broken" — which is
            # read_audience below, and which can already tell, because a
            # declined pages_show_list returns no Pages.
            scope=None,
            provider_user_id=self._me_id(access_token),
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        """THERE IS NO REFRESH TOKEN. Not for this grant — for Meta, at all.

        This is the one place in the subsystem where the protocol and a real
        platform genuinely do not fit, so here is the whole argument.

        WHAT META ACTUALLY OFFERS. Renewal is calling fb_exchange_token again
        with the CURRENT LONG-LIVED ACCESS TOKEN, which resets its ~60 days. So
        the credential Meta renews from is the access token, not a refresh
        token, and `refresh(refresh_token)` is handed the one thing that does
        not exist.

        WHY THIS RAISES RATHER THAN WORKING ANYWAY. Two designs would have made
        it work, and both were rejected:

          * store the long-lived access token in refresh_token_ciphertext too,
            so refresh() receives it. It works, and it puts a second encrypted
            copy of a live bearer credential in a second column, doubling the
            surface of the one secret in this codebase whose leak means acting
            AS a creator on a platform we do not run. Paying that to save a
            creator one button every 60 days is the wrong way round.
          * widen the protocol so refresh() can see the access token. That is a
            change to the interface every future provider implements, and to
            the FakeProvider that pins the mechanism in test_social_oauth.py,
            made to accommodate one platform's quirk. A protocol should be
            widened by a second implementation that needs it, not by the first.

        SO THE CONNECTION SIMPLY LAPSES, and the creator reconnects — which is
        what load_access_token already says: `oauth_token_expired`, "Reconnect
        it from your profile." Note that this method is UNREACHABLE through
        that path today and would be even if it were implemented: a Meta
        TokenSet carries refresh_token=None, the column stays null, and
        load_access_token refuses on a null refresh column several lines before
        it looks up a provider. Raising here is therefore documentation with
        teeth rather than a live code path — it makes the fact discoverable at
        the one place somebody would go looking, and it makes wiring Meta into
        a renewal loop fail loudly instead of silently doing nothing.

        WHAT TO DO INSTEAD, WHEN THERE IS A REASON TO. Nothing re-reads a Meta
        audience today — _apply_audience runs once, at connection. When
        something does, the credential it should hold is not a renewable user
        token at all: PAGE ACCESS TOKENS, fetched from {user-id}/accounts with
        a long-lived user token, DO NOT EXPIRE under normal conditions. A
        re-fetch loop should persist the Page token and read with that, which
        makes the 60-day question disappear rather than answering it. Teaching
        the user token to renew would be buying renewal for the wrong secret.
        """
        raise NotImplementedError(
            "Meta issues no refresh token; a lapsed connection is reconnected by the creator."
        )

    # -- what can be read once connected -----------------------------------

    def read_audience(self, tokens: TokenSet) -> AudienceSnapshot | None:
        """The creator's Pages, and a follower count only if there is exactly one.

        ONE PAGE IS A FACT. NO PAGES AND SEVERAL PAGES ARE BOTH QUESTIONS, and
        this refuses to answer a question by guessing.

        A creator who manages three Pages — a restaurant, a side project and a
        client's account they administer — has not told us which one is the
        audience they are selling, and nothing in the response says either. The
        two tempting rules are both wrong. "The first one" is ordered by Meta
        for Meta's reasons and can change between calls, so the same creator
        would get a different number on a reconnection with nothing having
        happened. "The biggest one" is us deciding which of somebody's
        businesses is their identity, and it is precisely the wrong answer for
        the creator whose largest Page is a client's.

        So: zero or several Pages records NO NUMBER AT ALL — follower_count
        stays null and, per #161's rule, so does its provenance, because a null
        count with a source attached would claim a report nobody made. The
        connection still succeeds, the tokens are still stored, and the creator
        picks their Page in the UI that comes with the follow-up PR. That the
        count is missing is visible on their own profile, which is a better
        prompt than any sentence this code could return.

        NEVER RAISES — see AudienceReader. Every failure is a log line and a
        None, because the account is already connected by the time this runs.
        """
        if not tokens.provider_user_id:
            return None
        try:
            body = self._graph(
                # The verified spelling: {user-id}/accounts, read with the
                # long-lived USER token. `me` would resolve to the same node,
                # but the id is already in hand and an explicit node is one
                # less thing that depends on which token was passed.
                f"{tokens.provider_user_id}/accounts",
                {
                    "fields": "id,name,followers_count,fan_count",
                    "access_token": tokens.access_token,
                },
            )
        except Exception as exc:
            _log.warning("Meta Pages lookup failed: %s", exc)
            return None

        pages = body.get("data")
        if not isinstance(pages, list):
            _log.warning("Meta Pages lookup returned no data array")
            return None
        if len(pages) != 1:
            # INFO, not WARNING: nothing is wrong. Zero Pages is a creator who
            # has not made one, or who declined pages_show_list on the consent
            # screen — which is their right and is exactly the case
            # SocialToken.scope's docstring worries about being misread as a
            # broken integration.
            _log.info(
                "Meta connection manages %d Pages, so no follower count was recorded",
                len(pages),
            )
            return None

        page = pages[0]
        # followers_count is the number to show. fan_count is Page likes and is
        # kept only as a fallback for Pages that still report the two
        # separately — the same order, and the same reason, as
        # enrichment.FacebookEnricher.
        followers = page.get("followers_count")
        if followers is None:
            followers = page.get("fan_count")
        name = page.get("name")
        snapshot = AudienceSnapshot(
            handle=name.strip() if isinstance(name, str) and name.strip() else None,
            follower_count=_int_at_least(followers, 0),
        )
        # Nothing usable came back. Returning None rather than an empty
        # snapshot keeps "we read nothing" and "we read that there is nothing"
        # from looking the same to the caller.
        if snapshot.handle is None and snapshot.follower_count is None:
            return None
        return snapshot

    # -- HTTP --------------------------------------------------------------

    def _graph(self, path: str, params: dict) -> dict:
        """One GET against the Graph API, or MetaOAuthError.

        RAISES RATHER THAN RETURNING None, unlike enrichment._graph_get which
        does the reverse. The difference is the caller: enrichment's failure
        leaves a field empty, and this one's failure means there is no
        connection, so it has to be impossible to mistake for a successful call
        that happened to return nothing.
        """
        url = f"{META_GRAPH_HOST}/{self.version}/{path}"
        try:
            res = httpx.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
        except Exception as exc:  # DNS, connect, read timeout
            raise MetaOAuthError(f"{path}: {type(exc).__name__}: {exc}") from exc
        if res.status_code >= 400:
            raise MetaOAuthError(f"{path}: HTTP {res.status_code}: {self._error_of(res)}")
        try:
            body = res.json()
        except Exception as exc:
            raise MetaOAuthError(f"{path}: response was not JSON") from exc
        if not isinstance(body, dict):
            raise MetaOAuthError(f"{path}: response was not a JSON object")
        return body

    @staticmethod
    def _error_of(res) -> str:
        """Meta's error envelope, reduced to the four fields worth logging.

        `{"error": {"message", "type", "code", "fbtrace_id"}}`. Read by name
        rather than logged whole: fbtrace_id is what Meta support asks for, and
        a body dumped verbatim is unbounded and routinely quotes its own input
        back — which, at a token endpoint, is a token.
        """
        try:
            error = (res.json() or {}).get("error") or {}
        except Exception:
            return "(unreadable body)"
        if not isinstance(error, dict):
            return "(no error envelope)"
        parts = [
            f"{key}={error[key]}"
            for key in ("code", "type", "message", "fbtrace_id")
            if error.get(key)
        ]
        return " ".join(parts) or "(no error envelope)"

    def _me_id(self, access_token: str) -> str | None:
        """Meta's own id for the person who just authorised us.

        APP-SCOPED, which is what makes it the right thing to key an account
        on: it is stable for this app forever, and it is NOT the creator's
        Facebook profile id, so it identifies them here and cannot be used to
        look them up anywhere else. oauth_service._account_for matches a
        re-authorisation against it, which is why reconnecting updates one row
        instead of quietly creating a second.

        A failure here is fatal to the exchange, deliberately. Without an id
        every reconnection makes a new SocialAccount and the creator's profile
        fills up with duplicates of one Page — worse, and much harder to undo,
        than being asked to try the connection again.
        """
        return self._graph("me", {"fields": "id", "access_token": access_token}).get("id")


def build_default_providers() -> dict[str, OAuthProvider]:
    """The providers this deployment can actually use, keyed by platform.

    GATED ON CREDENTIALS, exactly as build_default_enricher() gates on
    settings.youtube_api_key. A deployment with no Meta app id and no secret
    gets the same empty registry #162 shipped, and every platform — Facebook
    included — still answers `oauth_platform_unsupported`. That is what makes
    this change inert until somebody deliberately configures it, and it is why
    test_social_oauth.py's `test_no_provider_is_configured_by_default` is
    unchanged and still passes.

    BOTH CREDENTIALS, NOT EITHER. An app id with no secret cannot complete a
    token exchange, so registering on the id alone would move the failure from
    a sentence the creator reads BEFORE the handshake to a 502 at the end of
    one — after they have already granted permissions on Meta's consent screen,
    which is the worst moment available to discover that a server is
    misconfigured.

    TikTok's provider is added here beside its own `if settings.<...>` guard
    once its Login Kit application is approved.
    """
    providers: dict[str, OAuthProvider] = {}
    if settings.meta_app_id and settings.meta_app_secret:
        providers[MetaOAuthProvider.platform] = MetaOAuthProvider(
            settings.meta_app_id,
            settings.meta_app_secret,
            # The same pinned version the enrichers read, and pinned for the
            # same perishable reason — see config.meta_graph_version. A retired
            # version does not fail loudly here either: the dialog and the
            # token endpoint simply stop answering.
            settings.meta_graph_version,
        )
    return providers


default_providers: dict[str, OAuthProvider] = build_default_providers()
