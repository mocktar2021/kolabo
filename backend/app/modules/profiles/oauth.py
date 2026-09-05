"""OAuth against the social platforms: the mechanism, and deliberately no provider.

WHY THIS EXISTS BEFORE ANY PROVIDER DOES. Connecting a social account is the
one claim on this platform a creator cannot settle by typing. Today every
connection is a handle plus a screenshot link that an admin reads by hand
(admin.service.decide_social), because there has never been an authorization
URL, a callback, a token exchange or a stored token anywhere in this repo.

The platform that matters most in the launch markets is the one that needs this
first. TikTok's /v2/user/info/ answers ONLY for a token belonging to the creator
being read: there is no public handle lookup of the kind YouTube's `forHandle`
or Instagram's Business Discovery gives us — see enrichment.py, where TikTok is
the single entry that reads "Not yet wired". So a token is not an optimisation
for TikTok, it is the precondition. The same is true of YouTube Analytics later:
the API key buys public subscriber counts and nothing whatever about watch time,
retention or audience.

WHAT IS HERE AND WHAT IS NOT. This module is the shape of a provider and the
registry that holds them. There is no TikTok, Google or Meta implementation in
it, and that is the point of the split: the first real provider is then a small
diff about one platform's endpoints, scopes and quirks, reviewed on its own,
rather than a change that has to get state handling, encryption and refresh
rules right at the same time. The mechanism is proved instead against a fake
provider in backend/tests/test_social_oauth.py, which needs no network, no
developer account and no app review to run in CI.

THE SHAPE MIRRORS enrichment.py DELIBERATELY. A Protocol, concrete providers
chosen at import time from configured credentials, and a default that does
nothing when nothing is configured. build_default_providers() returns an EMPTY
registry, exactly as build_default_enricher returns a NoopEnricher: a feature
with no credentials reports itself unavailable rather than half working, and
`oauth_platform_unsupported` is the sentence a creator gets today.
"""
import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol

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
    was sent to it.
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
        """
        ...


def build_default_providers() -> dict[str, OAuthProvider]:
    """The providers this deployment can actually use, keyed by platform.

    EMPTY TODAY, and that is a statement rather than a stub. No platform in
    this repo has an OAuth client id, a client secret or an approved developer
    app — TikTok's Login Kit needs a reviewed application before it will issue
    either — so there is nothing here that could honestly be registered, and
    the honest answer to "connect my TikTok" is `oauth_platform_unsupported`
    rather than a redirect to a URL that will bounce.

    The same arrangement as build_default_enricher(), which returns a
    NoopEnricher when no credentials are set. A provider is added here beside a
    `if settings.<platform>_client_id:` guard, so a deployment without the
    credentials keeps reporting the feature unavailable instead of half
    offering it.
    """
    return {}


default_providers: dict[str, OAuthProvider] = build_default_providers()
