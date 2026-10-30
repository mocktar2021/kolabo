"""OAuth against the social platforms: the mechanism, and the providers.

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

AND NOW IT IS. TikTok's app exists, its Login Kit is configured, and its
provider is below. The order in the paragraph above held: Meta's handshake had
to work before there was anything to film, the film opened Meta's review, and
the same working mechanism is what TikTok's own review is now demonstrated
against. Note what that does NOT mean. TikTok's provider is registered from
credentials and is inert without them, so a deployment that has not been
given a key is exactly as it was.

WHAT IS HERE. The shape of a provider, the registry that holds them, and two
implementations. The mechanism itself is still proved against a FAKE provider
in backend/tests/test_social_oauth.py, which needs no network, no developer
account and no app review to run in CI; each real provider is proved
separately against a fake HTTP layer, in test_meta_oauth.py and
test_tiktok_oauth.py. Keeping those apart is deliberate: a change to one
platform's endpoints must not be able to quietly weaken the state, encryption
and rotation rules, and a change to those rules must fail in a file whose name
says so.

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

THE THREE THINGS ABOUT META THAT ARE NOT LIKE THE OTHER PLATFORMS. They were
written down for the next provider author, and TikTok turned out to be the
opposite of all three: it issues a refresh token, it rotates it, and the token
it first hands back is the one to keep. TikTokOAuthProvider carries the
matching list from its own side. Read both before writing a third.

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
from app.core.redaction import redact

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


@dataclass
class PlatformPage:
    """One Page a creator manages, as the platform describes it right now.

    A DIFFERENT QUESTION FROM AudienceSnapshot, which is why it is a second
    dataclass rather than a reuse of the first. A snapshot is the audience an
    account has settled on, and writing one to a profile is a claim. This is a
    CHOICE ON OFFER: one of several things a creator might be selling, none of
    them yet claimed by anybody. Nothing built out of one of these is stored
    until the creator has said which one they mean.

    `id` is the platform's own id for the Page and is what a creator sends back
    to choose it. Optional, because an entry that arrives without one cannot be
    chosen at all, and carrying that as None is more honest than inventing an
    empty string that would look selectable.

    `name` and `follower_count` are normalised by exactly the code that used to
    normalise them inside read_audience, because they land in exactly the same
    two columns.
    """

    id: str | None
    name: str | None
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


class PageLister(Protocol):
    """The other optional half of a provider: the choices it can offer.

    THE SAME OPT-IN AS AudienceReader, for the same reason. A platform where
    one authorization means exactly one sellable account has nothing to list
    and should not have to grow a method saying so, and the FakeProvider that
    pins the mechanism in test_social_oauth.py must not have to be edited
    because a real provider grew a capability. oauth_service looks for
    `list_pages` with getattr and refuses the two picker endpoints cleanly for
    a provider that has none.

    RETURNS None RATHER THAN RAISING for the failures it can name, because
    read_audience calls it and read_audience must never raise. A caller that
    wants to tell a creator something about the failure reads the None and
    decides for itself what to say.

    AN EMPTY LIST IS NOT None. [] is "we asked, and there are none", which is
    an ordinary answer. None is "we could not ask". Collapsing the two would
    let a network blip tell a creator they manage no Pages.
    """

    def list_pages(self, tokens: TokenSet) -> list[PlatformPage] | None:
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

# The Graph parameters whose VALUE is a credential, and which therefore must
# never survive into a MetaOAuthError, a log line, or anything a creator sees.
#
# READ BACK OUT OF `params` RATHER THAN PASSED IN, the same way
# enrichment._graph_get reads its token back, and for the same reason: _graph
# is one function serving four different calls that carry four different
# secrets. Naming them here means a fifth call is covered by adding its
# parameter to this tuple, at the one place somebody would think to look.
#
#   client_secret      THE APP SECRET, and the worst of the four. It acts as
#                      the whole Kolabo app rather than as one creator, and
#                      rotating it breaks every live connection at once.
#   access_token       a creator's own long-lived token, sent on /me and on
#                      {user-id}/accounts.
#   fb_exchange_token  the short-lived token, on its way to being exchanged.
#   code               the authorization code, which is still spendable at the
#                      moment the first token call fails.
META_CREDENTIAL_PARAMS = ("client_secret", "access_token", "fb_exchange_token", "code")


def _without_credentials(message: str, params: dict) -> str:
    """`message`, with every credential that was in `params` struck out of it."""
    return redact(message, *(params.get(name) for name in META_CREDENTIAL_PARAMS))


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
        picks their Page through oauth_service.list_pages and select_page,
        which read the same list this does. That the count is missing is
        visible on their own profile, which is a better prompt than any
        sentence this code could return.

        NEVER RAISES — see AudienceReader. Every failure is a log line and a
        None, because the account is already connected by the time this runs.

        THE LOOKUP ITSELF MOVED TO list_pages BELOW and nothing else changed.
        This method still asks the same question of the same endpoint, still
        applies the exactly-one rule, still logs the same two lines, and still
        answers None in every case it answered None in before. The split buys
        one thing only: a second caller can now read the same list for a
        different purpose, which is what the picker endpoints do.
        """
        pages = self.list_pages(tokens)
        if pages is None:
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
        snapshot = AudienceSnapshot(handle=page.name, follower_count=page.follower_count)
        # Nothing usable came back. Returning None rather than an empty
        # snapshot keeps "we read nothing" and "we read that there is nothing"
        # from looking the same to the caller.
        if snapshot.handle is None and snapshot.follower_count is None:
            return None
        return snapshot

    def list_pages(self, tokens: TokenSet) -> list[PlatformPage] | None:
        """Every Page this creator manages, or None when we could not ask.

        THE ONE-PAGE RULE IS NOT HERE, DELIBERATELY. This reports what Meta
        said. read_audience above decides what may be recorded from it, and
        oauth_service.select_page decides what the creator may choose out of
        it. Keeping the lookup and the rule apart is the whole point of the
        split: two callers want the same facts and want very different things
        done with them.

        None AND [] ARE DIFFERENT ANSWERS. None means we could not ask: no
        provider id to ask about, a Graph that refused or could not be reached,
        a body that was not shaped like a list. [] means we asked and this
        creator manages no Pages, which is ordinary for somebody who has not
        made one or who declined pages_show_list on the consent screen. A
        caller that treats the two alike will one day tell a creator they have
        no Pages because a socket timed out.

        DOES NOT RAISE FOR EITHER OF THOSE, because read_audience calls it and
        read_audience may never raise. Every entry that came back is carried
        through, including one with no usable id: dropping those here would
        change the COUNT read_audience sees, and the count is what decides
        whether a creator is treated as ambiguous.
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
        return [self._page_of(page) for page in pages]

    @staticmethod
    def _page_of(page) -> PlatformPage:
        """One entry of {user-id}/accounts, normalised.

        Exactly the normalisation read_audience used to do inline, moved with
        its comment so the two paths cannot drift apart: whatever a creator
        sees in the picker is the same name and the same number that a
        single-Page connection would have recorded on its own.
        """
        # followers_count is the number to show. fan_count is Page likes and is
        # kept only as a fallback for Pages that still report the two
        # separately — the same order, and the same reason, as
        # enrichment.FacebookEnricher.
        followers = page.get("followers_count")
        if followers is None:
            followers = page.get("fan_count")
        name = page.get("name")
        page_id = page.get("id")
        return PlatformPage(
            id=page_id if isinstance(page_id, str) and page_id else None,
            name=name.strip() if isinstance(name, str) and name.strip() else None,
            follower_count=_int_at_least(followers, 0),
        )

    # -- HTTP --------------------------------------------------------------

    def _graph(self, path: str, params: dict) -> dict:
        """One GET against the Graph API, or MetaOAuthError.

        RAISES RATHER THAN RETURNING None, unlike enrichment._graph_get which
        does the reverse. The difference is the caller: enrichment's failure
        leaves a field empty, and this one's failure means there is no
        connection, so it has to be impossible to mistake for a successful call
        that happened to return nothing.

        WHAT KOL-108 ASKED AND WHAT WAS MEASURED, written here so that nobody
        has to audit it again from scratch. `params` carries client_secret on
        both token calls, so the app secret is part of the request url, which
        is exactly the shape that leaked in #183. It does NOT leak the same
        way, and both halves of that were MEASURED against the pinned
        httpx 0.27.2 rather than reasoned about:

          * THE TRANSPORT BRANCH IS CLEAN. Every exception httpx maps out of a
            GET (ConnectError, ConnectTimeout, ReadTimeout, WriteTimeout,
            PoolTimeout, ReadError, WriteError, NetworkError,
            RemoteProtocolError, LocalProtocolError, ProxyError,
            UnsupportedProtocol and the rest) carries nothing of the url in
            either str(exc) or repr(exc). The url is attached to the object as
            `.request`, and is never rendered into the message.
          * THE ONLY PLACE httpx 0.27.2 PUTS A URL INTO AN EXCEPTION MESSAGE
            is Response.raise_for_status(), which composes HTTPStatusError. So
            the #183 mechanism is absent here for one specific reason: this
            method never calls raise_for_status(). It reads status_code itself
            and builds its own sentence, which is what the 400 branch below is.

        THE REDACTION IS STILL HERE, AND IT IS NOT DECORATION, for two reasons
        that the measurement does not cover. _error_of reads Meta's `message`
        field, and whether Meta can echo a request parameter back inside it is
        NOT established by Meta's documentation, so it is treated as unverified
        rather than as safe. And a measurement pins one version of one library:
        a bump that moved the url into a transport message would reopen #183
        here, silently, in the one place holding the app secret. Striking the
        credentials out makes the property hold by construction rather than by
        a dependency's undocumented behaviour.
        """
        url = f"{META_GRAPH_HOST}/{self.version}/{path}"
        try:
            res = httpx.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
        except Exception as exc:  # DNS, connect, read timeout
            raise MetaOAuthError(
                _without_credentials(f"{path}: {type(exc).__name__}: {exc}", params)
            ) from exc
        if res.status_code >= 400:
            raise MetaOAuthError(
                _without_credentials(
                    f"{path}: HTTP {res.status_code}: {self._error_of(res)}", params
                )
            )
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

        READING BY NAME IS NOT ITSELF THE GUARANTEE, and KOL-108 is the reason
        that is now written down rather than assumed. `message` is precisely
        the field that quotes input back, and nothing in Meta's documentation
        establishes that it cannot contain a request parameter. Treat that as
        unverified, not as safe: the caller strikes the credentials out of
        whatever this returns. See _graph, which is the only caller, and which
        wraps this in _without_credentials.
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


# ---------------------------------------------------------------------------
# TikTok (Login Kit)
# ---------------------------------------------------------------------------

# TWO HOSTS, SPLITTING THE SAME WAY META'S DO AND FOR THE SAME REASON. The
# consent screen is served from www.tiktok.com; the token endpoint and every
# data call go to open.tiktokapis.com. Pointing the dialog at the API host
# does not error, it serves something that is not a consent screen.
TIKTOK_AUTHORIZE_HOST = "https://www.tiktok.com"
TIKTOK_API_HOST = "https://open.tiktokapis.com"

# What a creator is asked for, and nothing beyond it. TikTok's App Review
# guidelines are explicit that a scope left selected and not demonstrated in
# the submitted video delays the result, so an unused entry here is not a
# harmless extra, it is a slower review.
#
#   user.info.basic    open_id and display_name. Included in Login Kit itself
#                      and not separately addable in the portal.
#   user.info.profile  username, which is the @handle a creator recognises.
#                      display_name is a changeable label; the username is
#                      what their audience types.
#   user.info.stats    follower_count, and the entire reason this provider
#                      exists. See the module docstring: TikTok publishes no
#                      handle lookup, so a token is not an optimisation here,
#                      it is the only way to learn the number at all.
#
# COMMA SEPARATED, which is TikTok's spelling and not OAuth 2.0's space, the
# same trap Meta sets one host over. A space-joined string is not rejected;
# it is read as one scope with a strange name, granted to nobody, and the
# handshake then succeeds carrying no permissions.
TIKTOK_SCOPES = ("user.info.basic", "user.info.profile", "user.info.stats")

# The fields read back once connected, each one paid for by a scope above.
# Asking for a field whose scope was not granted does not fail the call, it
# omits the field, which is why read_audience treats a missing value as None
# rather than as an error.
TIKTOK_AUDIENCE_FIELDS = ("username", "display_name", "follower_count")

# What a token is assumed to be worth when TikTok does not say. Both numbers
# are TikTok's own documented lifetimes rather than guesses, and they are only
# the floor under a response that omits the field. Erring short is the safe
# direction for the same reason it is for Meta: understating costs a creator
# an early reconnection, overstating produces a connection that reports itself
# healthy while every call it makes is refused.
TIKTOK_ACCESS_FALLBACK_SECONDS = 24 * 60 * 60
TIKTOK_REFRESH_FALLBACK_SECONDS = 365 * 24 * 60 * 60

# The request fields whose VALUE is a credential, struck out of anything that
# becomes an exception message or a log line.
#
# A DIFFERENT LEAK SURFACE FROM META'S, and worth saying why the same defence
# is here anyway. Meta's calls are GETs, so its secrets ride in the url, which
# is the exact shape that leaked in #183. These are POSTs with a form body, so
# no credential is ever part of a url and the #183 mechanism cannot apply. The
# redaction stays because the other half of that argument does: TikTok's
# `error_description` is free text and nothing in TikTok's documentation
# establishes that it cannot quote a request parameter back. Unverified, not
# safe.
#
#   client_secret  acts as the whole Kolabo app rather than as one creator.
#   code           the authorization code, still spendable at the moment a
#                  first token call fails.
#   refresh_token  a 365 day credential, and the longest lived secret this
#                  subsystem handles.
#   access_token   a creator's own bearer token, sent on the user info call.
TIKTOK_CREDENTIAL_PARAMS = ("client_secret", "code", "refresh_token", "access_token")


def _without_tiktok_credentials(message: str, params: dict) -> str:
    """`message`, with every credential that was in `params` struck out of it."""
    return redact(message, *(params.get(name) for name in TIKTOK_CREDENTIAL_PARAMS))


class TikTokOAuthError(RuntimeError):
    """A refusal from TikTok, reduced to the parts worth logging.

    Its own class for the same reason MetaOAuthError is: `log_id` is the one
    string TikTok support will ask for, and a body logged whole is unbounded
    and routinely quotes its own input back, which at a token endpoint is a
    token.

    NEVER REACHES A CREATOR. oauth_service turns every exception out of a
    provider into `oauth_exchange_failed` and logs this beside it.
    """


class TikTokOAuthProvider:
    """TikTok's half of the handshake, over Login Kit v2.

    THE THREE THINGS ABOUT TIKTOK THAT ARE NOT LIKE META, stated here because
    the previous provider in this file sets every one of the opposite habits:

      * THE ACCESS TOKEN LIVES 24 HOURS, not 60 days, and there IS a refresh
        token, which lives 365 days. So refresh() is a real code path here
        rather than the documented refusal it is for Meta, and it is load
        bearing: a connection made today is dead tomorrow morning without it.
      * THE REFRESH TOKEN ROTATES. Every refresh may return a different one,
        and the old one stops working. Persisting whatever comes back is not
        an optimisation, it is the difference between a connection that lasts
        a year and one that dies on its second day. oauth_service.save_tokens
        already carries that rule; this is the provider that finally exercises
        it.
      * THE TOKEN RESPONSE STATES THE GRANTED SCOPE. Meta's does not, which is
        why MetaOAuthProvider writes scope=None rather than echoing back what
        it asked for. TikTok sends `scope` as the comma separated list of what
        the creator actually agreed to, so SocialToken.scope can hold the
        answer to its own question for the first time.

    NO PKCE, AND THAT IS TIKTOK'S RULE RATHER THAN A CHOICE MADE HERE.
    TikTok's token documentation marks `code_verifier` as required only for
    mobile and desktop apps; the web authorization request documents no
    `code_challenge` parameter at all. This app is registered Web only. So the
    verifier is accepted and forwarded nowhere, exactly as it is for Meta, and
    for the same reason: a challenge an endpoint ignores is a claim of
    protection that is not there. What actually protects this flow is the
    client secret on a server-side exchange and the state row, which is the
    whole security surface of the callback.

    IF THE ANDROID OR IOS PLATFORM IS EVER ADDED TO THE APP, this changes. A
    native client cannot hold the secret, PKCE becomes required rather than
    optional, and `code_verifier` has to start being sent. The verifier is
    already minted and stored for every handshake, so that day is a change to
    this class alone.

    ONE AUTHORIZATION IS ONE ACCOUNT, which is why there is no list_pages
    here. Meta needs a picker because a person can administer several Pages
    and nothing in the response says which one they sell; a TikTok creator who
    authorises is the account. Nothing to choose, so nothing to ask.
    """

    platform = "tiktok"

    def __init__(self, client_key: str, client_secret: str):
        self.client_key = client_key
        self.client_secret = client_secret

    # -- the handshake -----------------------------------------------------

    def authorize_url(self, state: str, code_verifier: str, redirect_uri: str) -> str:
        """The consent screen, on www.tiktok.com.

        `code_verifier` is accepted and NOT USED. See the class docstring for
        the whole argument; the signature keeps it because the protocol offers
        it, not because anything here wants it.
        """
        params = {
            "client_key": self.client_key,
            "scope": ",".join(TIKTOK_SCOPES),
            "response_type": "code",
            # Byte for byte the same string exchange_code will send, because
            # both take it from oauth_service.redirect_uri. TikTok compares
            # them and refuses a mismatch without naming either.
            "redirect_uri": redirect_uri,
            "state": state,
            # ALWAYS SHOW THE CONSENT SCREEN, NEVER SKIP IT FOR A SIGNED IN
            # ACCOUNT. TikTok documents disable_auto_auth as 0 meaning the
            # authorization page is skipped for a valid session and 1 meaning
            # it is always shown. The default is not documented, which is
            # reason enough to state it rather than inherit it.
            #
            # TWO SEPARATE ARGUMENTS FOR 1, and the second is the durable one:
            #
            #   * A RECONNECTION SHOULD SHOW WHAT IT GRANTS. A creator coming
            #     back after a year, or reconnecting because something broke,
            #     is granting three permissions over their own audience data.
            #     Silently reusing an old consent to hand us a fresh token
            #     saves one tap and costs them the only moment where they see
            #     what they are agreeing to.
            #   * APP REVIEW NEEDS THE SCREEN ON FILM. TikTok requires every
            #     selected scope to be demonstrated in the demo video, and the
            #     consent screen is where a reviewer sees them named. A
            #     skipped screen means a re-recording, and the only way to get
            #     it back would be revoking Kolabo from inside TikTok's own
            #     settings first, which is a step that will be forgotten
            #     exactly once and will not announce itself.
            "disable_auto_auth": 1,
        }
        return f"{TIKTOK_AUTHORIZE_HOST}/v2/auth/authorize/?{urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        """Trade the callback's code for an access token and a refresh token.

        ONE CALL, unlike Meta's two. There is no short-lived token to launder
        into a long-lived one here: what the code buys is what gets stored.
        """
        body = self._token(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                # No code_verifier. See the class docstring.
            }
        )
        return self._tokens_from(body, "the token endpoint")

    def refresh(self, refresh_token: str) -> TokenSet:
        """Renew an expired access token, and store whatever comes back.

        THE RETURNED REFRESH TOKEN MAY NOT BE THE ONE SENT. TikTok documents
        that it rotates, and that when it differs the new value must be used.
        This method does nothing special about that beyond returning it,
        because the rule lives with the only caller that can honour it:
        oauth_service.save_tokens persists a non-null refresh_token over the
        stored one. The failure mode if that ever stops being true is quiet
        and slow, which is what makes it worth naming twice: the connection
        goes on working until the access token expires, then the next refresh
        presents a retired credential and the creator reads that their TikTok
        disconnected itself, a day or a week after the change that caused it.

        NO redirect_uri AND NO code HERE, which is not an omission. TikTok's
        refresh grant takes exactly four fields and refuses extras.
        """
        body = self._token(
            {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        return self._tokens_from(body, "the refresh endpoint")

    # -- what can be read once connected -----------------------------------

    def read_audience(self, tokens: TokenSet) -> AudienceSnapshot | None:
        """The creator's handle and follower count, or None.

        NEVER RAISES, which is the AudienceReader contract and matters more
        here than anywhere else in this provider: this runs AFTER the tokens
        are stored, so an exception escaping would turn a connection that
        succeeded into one the creator is told failed, over a follower count.

        THE HANDLE IS `username`, NOT `display_name`, and the fallback order
        is deliberate. display_name is a label a creator can change to
        anything and two creators can share; username is the @handle their
        audience types and the platform guarantees unique. A profile card
        showing the display name would be showing the less identifying of the
        two. display_name is used only when username is absent, which happens
        when user.info.profile was not granted.

        A MISSING FIELD IS None AND NOT AN ERROR. TikTok omits the fields
        whose scope was declined rather than refusing the call, so a creator
        who unticks the stats permission on the consent screen reaches here
        with a readable response and no follower_count. None is the honest
        record of that, and it is what keeps the connection standing.
        """
        params = {"fields": ",".join(TIKTOK_AUDIENCE_FIELDS)}
        try:
            res = httpx.get(
                f"{TIKTOK_API_HOST}/v2/user/info/",
                params=params,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            _log.warning(
                "tiktok user/info: %s",
                redact(f"{type(exc).__name__}: {exc}", tokens.access_token),
            )
            return None
        try:
            body = res.json()
        except Exception:
            _log.warning("tiktok user/info: HTTP %s, response was not JSON", res.status_code)
            return None
        if not isinstance(body, dict):
            _log.warning("tiktok user/info: HTTP %s, response was not a JSON object", res.status_code)
            return None

        # A 200 IS NOT A SUCCESS ON THIS ENDPOINT. TikTok answers the user
        # info call with HTTP 200 and an `error` object whose `code` is "ok"
        # when all is well and something else when it is not. Reading only the
        # status here would turn a refused token into an AudienceSnapshot full
        # of Nones, which is indistinguishable from a creator who declined the
        # scopes and would be written to their profile as fact.
        failure = self._user_info_error(body)
        if res.status_code >= 400 or failure:
            _log.warning(
                "tiktok user/info: HTTP %s: %s", res.status_code, failure or "(no error envelope)"
            )
            return None

        user = (body.get("data") or {}).get("user")
        if not isinstance(user, dict):
            _log.warning("tiktok user/info: no user object in the response")
            return None
        handle = user.get("username") or user.get("display_name")
        return AudienceSnapshot(
            handle=str(handle) if handle else None,
            follower_count=_int_at_least(user.get("follower_count"), 0),
        )

    # -- HTTP --------------------------------------------------------------

    def _token(self, data: dict) -> dict:
        """One POST against the token endpoint, or TikTokOAuthError.

        RAISES RATHER THAN RETURNING None, the same way Meta's _graph does and
        for the same reason: a failure here means there is no connection, so
        it must be impossible to mistake for a call that succeeded and
        returned nothing.

        FORM ENCODED, NOT JSON, and this is the one that silently half works.
        TikTok's token endpoint documents application/x-www-form-urlencoded.
        httpx sends that when the body is passed as `data=`; passing the same
        dict as `json=` produces a well formed request that the endpoint
        answers with an error about a missing grant_type, which reads like a
        bug in the parameters rather than in the encoding.

        NO raise_for_status() ANYWHERE, deliberately, which is the habit
        carried over from Meta's _graph: it is the one httpx call that renders
        a url into an exception message, and this request body holds the
        client secret. The status is read and the sentence is built here.
        """
        try:
            res = httpx.post(
                f"{TIKTOK_API_HOST}/v2/oauth/token/",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # DNS, connect, read timeout
            raise TikTokOAuthError(
                _without_tiktok_credentials(f"oauth/token: {type(exc).__name__}: {exc}", data)
            ) from exc
        try:
            body = res.json()
        except Exception as exc:
            raise TikTokOAuthError(f"oauth/token: HTTP {res.status_code}: not JSON") from exc
        if not isinstance(body, dict):
            raise TikTokOAuthError(f"oauth/token: HTTP {res.status_code}: not a JSON object")

        # THE TOKEN ENDPOINT'S ERROR SHAPE IS NOT THE USER INFO ENDPOINT'S,
        # and they are two calls apart in the same file. Here `error` is a
        # STRING beside `error_description` and `log_id`; on /v2/user/info/ it
        # is an OBJECT carrying `code`. Treating either shape as the other
        # reads a failure as a success.
        failure = body.get("error")
        if res.status_code >= 400 or failure:
            parts = [
                f"{key}={body[key]}"
                for key in ("error", "error_description", "log_id")
                if body.get(key)
            ]
            raise TikTokOAuthError(
                _without_tiktok_credentials(
                    f"oauth/token: HTTP {res.status_code}: "
                    + (" ".join(parts) or "(no error envelope)"),
                    data,
                )
            )
        return body

    def _tokens_from(self, body: dict, what: str) -> TokenSet:
        """TikTok's token response, translated into a TokenSet.

        SHARED BY BOTH GRANTS because TikTok documents the same seven fields
        for each. Giving the refresh path its own copy would be two places for
        the rotation rule to be got right and one place for it to be forgotten.
        """
        access_token = body.get("access_token")
        if not access_token:
            raise TikTokOAuthError(f"{what} returned no access_token")
        refresh_token = body.get("refresh_token")
        scope = body.get("scope")
        open_id = body.get("open_id")
        return TokenSet(
            access_token=str(access_token),
            # NOT None WHEN ABSENT ONLY BECAUSE save_tokens READS None AS
            # "unchanged". On the first exchange a missing refresh_token would
            # mean a connection that cannot survive its first day, and on a
            # refresh it means keep the one already stored, which is correct
            # for a provider that chose not to rotate this time.
            refresh_token=str(refresh_token) if refresh_token else None,
            access_expires_in=(
                _int_at_least(body.get("expires_in"), 1) or TIKTOK_ACCESS_FALLBACK_SECONDS
            ),
            refresh_expires_in=(
                _int_at_least(body.get("refresh_expires_in"), 1)
                or TIKTOK_REFRESH_FALLBACK_SECONDS
            ),
            # THE GRANT, NOT THE REQUEST, and TikTok is the first provider
            # here that can tell the difference. See the class docstring.
            scope=str(scope) if scope else None,
            # STRAIGHT OUT OF THE TOKEN RESPONSE, with no second call. Meta
            # needs a /me round trip for this and treats its failure as fatal
            # to the exchange; TikTok states open_id in the same body, so the
            # duplicate-account risk that justified Meta's extra call does not
            # arise.
            provider_user_id=str(open_id) if open_id else None,
        )

    @staticmethod
    def _user_info_error(body: dict) -> str:
        """The user info envelope's failure, as a loggable string, or "".

        `{"error": {"code", "message", "log_id"}}`, where code "ok" means
        there was no failure. Read by name rather than logged whole: log_id is
        what TikTok support asks for, and a body dumped verbatim is unbounded.
        """
        error = body.get("error")
        if not isinstance(error, dict):
            return ""
        code = error.get("code")
        if not code or str(code).lower() == "ok":
            return ""
        parts = [f"{key}={error[key]}" for key in ("code", "message", "log_id") if error.get(key)]
        return " ".join(parts) or "(no error envelope)"


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

    TWO PROVIDERS NOW, AND THEY ARE INDEPENDENT. A box with Meta's pair and
    not TikTok's offers one connect button and refuses the other, which is the
    normal state during either platform's review rather than a misconfigured
    deployment.
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
    if settings.tiktok_client_key and settings.tiktok_client_secret:
        providers[TikTokOAuthProvider.platform] = TikTokOAuthProvider(
            # WHICH PAIR THESE ARE IS INVISIBLE FROM HERE, and that is the
            # design rather than an omission. TikTok requires a first-time app
            # to be demonstrated from a sandbox, and a sandbox carries its own
            # client key and secret beside the production pair on the same
            # app. Both resolve the same registered redirect URI, so the swap
            # from one to the other on approval is an edit to deploy/.env and
            # a restart. Nothing in this file branches on it, and nothing
            # should start to: a code path that knows it is talking to a
            # sandbox is a code path that can behave differently in review
            # from how it behaves in production.
            settings.tiktok_client_key,
            settings.tiktok_client_secret,
        )
    return providers


default_providers: dict[str, OAuthProvider] = build_default_providers()
