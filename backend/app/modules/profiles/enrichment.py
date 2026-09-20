"""Social profile enrichment.

Auto filling a creator profile from their social account is what makes onboarding
one click. Doing it legitimately means the official platform APIs, not scraping,
which is fragile and generally against platform terms.

What each platform needs:
- YouTube: a Google Cloud API key for YouTube Data API v3. Public channel data
  (title, avatar, subscriber count) needs only the key, no OAuth and no app
  review, so it works as soon as YOUTUBE_API_KEY is set.
- Instagram: the Instagram Graph API's Business Discovery, which returns a
  creator's public stats BY HANDLE — but only to a caller that is itself a
  Business/Creator account, and only for targets that are Business or Creator
  too. So it needs META_GRAPH_TOKEN plus the querying account's id in
  INSTAGRAM_BUSINESS_ACCOUNT_ID. The creator being read authorises nothing; the
  app reads public data through its own business account.
- Facebook: the Page node on the same Graph API — name, follower count and
  picture for a Page the token can read. Shares META_GRAPH_TOKEN with Instagram,
  and needs no separate business-account id of its own.
- TikTok: Login Kit OAuth plus the user.info.stats scope, which requires an
  approved TikTok for Developers app. Not yet wired.

Enrichers are selected at import time from configured credentials. With none
configured nothing is filled and the creator types their own details.
"""
import logging
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.core.redaction import redact
from app.core.urls import is_public_host, normalized_public_url

_log = logging.getLogger("kolabo.profiles.enrichment")

TIMEOUT_SECONDS = 6.0

# The most of an avatar this process will ever hold in memory. Real ones are
# tens of kilobytes, so five megabytes is generous for the thing we want and
# still small enough that a url pointing at a video file, or at an endpoint
# that streams for as long as somebody keeps writing to it, cannot turn one
# profile import into an out-of-memory kill. Counted as bytes ARRIVE rather
# than read off a header, for the reason fetch_image gives.
MAX_FETCHED_IMAGE_BYTES = 5 * 1024 * 1024


def _safe_error(exc: Exception, *secrets: str | None) -> str:
    """What an upstream failure is allowed to say in a log line.

    NEVER LOG THE EXCEPTION OBJECT FROM ONE OF THESE CALLS. Every API read in
    this module takes its credential as a query parameter, so the credential is
    part of the request url, and httpx puts the whole url, query string
    included, inside the message of the HTTPStatusError it raises. Logging that
    object therefore writes YOUTUBE_API_KEY or META_GRAPH_TOKEN into the
    application log in clear text, once per failed request, for anyone who can
    read the container's output. Measured against the pinned httpx 0.27.2
    rather than assumed, and pinned by a test that asserts the raw exception
    really does carry the credential before asserting the log does not.

    So the line is rebuilt here out of parts that cannot carry a credential,
    and then every secret the caller names is struck out of the result as a
    second layer, because this function cannot know what a future exception
    type will choose to put in its own message.

    THE STRIKING ITSELF NOW LIVES IN app.core.redaction, because KOL-108 gave
    profiles/oauth.py a use for the same last line of defence, over the Meta
    app secret. Nothing about the behaviour here changed and the three tests at
    the bottom of test_enrichment.py still pin it; what moved is only where the
    loop is written, so that the two callers cannot drift apart.

    The rebuild says MORE than the line it replaces, not less. A failure that
    got as far as a response carries the provider's own error object, whose
    code and message are the difference between "enrichment returned nothing"
    and "that field name no longer exists". Before this, an expired token, a
    quota refusal and a dead network all read identically in the log.
    """
    response = getattr(exc, "response", None)
    if response is None:
        detail = f"{type(exc).__name__}: {exc}"
    else:
        detail = f"{type(exc).__name__}: HTTP {getattr(response, 'status_code', '?')}"
        try:
            body = response.json()
        except Exception:
            body = None
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            named = ", ".join(
                f"{key}={error[key]}"
                for key in ("code", "error_subcode", "type", "message")
                if error.get(key) not in (None, "")
            )
            if named:
                detail = f"{detail}, {named}"
    return redact(detail, *secrets)


class EnrichedProfile(dict):
    """Keys, all optional: display_name, avatar_image_url, follower_count, bio."""


class SocialEnricher(Protocol):
    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        """Return public profile data for a handle, or None if unavailable."""
        ...


class NoopEnricher:
    """Used when no credentials are configured. Never guesses."""

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        return None


class YouTubeEnricher:
    """Public channel data via YouTube Data API v3, keyed by handle.

    Only needs an API key, so this is the one platform that can enrich without
    an OAuth handshake or app review.
    """

    API_URL = "https://www.googleapis.com/youtube/v3/channels"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        if platform != "youtube" or not self.api_key:
            return None
        params = {
            "part": "snippet,statistics",
            "forHandle": handle if handle.startswith("@") else f"@{handle}",
            "key": self.api_key,
        }
        try:
            res = httpx.get(self.API_URL, params=params, timeout=TIMEOUT_SECONDS)
            res.raise_for_status()
            items = res.json().get("items") or []
        except Exception as exc:  # network, quota, or malformed response
            _log.warning(
                "YouTube enrichment failed for %s: %s",
                handle,
                _safe_error(exc, self.api_key),
            )
            return None
        if not items:
            return None

        snippet = items[0].get("snippet", {})
        stats = items[0].get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})
        thumb = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}

        out = EnrichedProfile()
        if snippet.get("title"):
            out["display_name"] = snippet["title"]
        if snippet.get("description"):
            # Channel descriptions run long; keep a usable bio length.
            out["bio"] = snippet["description"][:500].strip()
        if thumb.get("url"):
            out["avatar_image_url"] = thumb["url"]
        subs = stats.get("subscriberCount")
        if subs is not None:
            try:
                out["follower_count"] = int(subs)
            except (TypeError, ValueError):
                pass
        return out or None


GRAPH_HOST = "https://graph.facebook.com"


def _graph_get(version: str, node: str, params: dict) -> dict | None:
    """One GET against the Meta Graph API, returning parsed JSON or None.

    Shared by the Instagram and Facebook enrichers because both read the same
    host under the same rule: an outage, a rate limit, an expired token or a
    malformed body must return None and never break account connection — the
    contract YouTubeEnricher keeps, stated once for the two that reuse it.
    """
    url = f"{GRAPH_HOST}/{version}/{node}"
    try:
        res = httpx.get(url, params=params, timeout=TIMEOUT_SECONDS)
        res.raise_for_status()
        return res.json()
    except Exception as exc:  # network, quota, expired token, or malformed body
        # The token is read back out of params rather than passed in, so this
        # keeps working whoever calls it. IF THE TOKEN EVER STOPS BEING A QUERY
        # PARAMETER, this line must move with it or the redaction goes quiet.
        _log.warning(
            "Meta Graph request failed for %s: %s",
            node,
            _safe_error(exc, params.get("access_token")),
        )
        return None


class InstagramEnricher:
    """Public creator stats via the Instagram Graph API's Business Discovery.

    Business Discovery is the one Instagram surface that returns ANOTHER
    account's public data BY HANDLE — username, name, biography, follower count
    and avatar — which is exactly what enrichment needs. Two requirements the
    config carries, not the handle: the account being read must be a Business or
    Creator account (personal accounts are invisible to it), and the call must
    be made THROUGH the platform's own Business account
    (instagram_business_account_id), because Meta only answers Business
    Discovery for a business that is asking.
    """

    def __init__(self, token: str, business_account_id: str, version: str):
        self.token = token
        self.business_account_id = business_account_id
        self.version = version

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        if platform != "instagram" or not (self.token and self.business_account_id):
            return None
        # A handle is written @name in the UI; Business Discovery wants the bare
        # username inside the field expression.
        username = handle[1:] if handle.startswith("@") else handle
        fields = (
            f"business_discovery.username({username})"
            "{username,name,biography,followers_count,profile_picture_url}"
        )
        data = _graph_get(
            self.version,
            self.business_account_id,
            {"fields": fields, "access_token": self.token},
        )
        if not data:
            return None
        # An unknown handle, or one on a personal account, comes back with no
        # business_discovery block rather than an error.
        bd = data.get("business_discovery")
        if not bd:
            return None

        out = EnrichedProfile()
        # The creator's chosen name, falling back to the handle when they left
        # the name field blank — a handle beats an empty display name.
        if bd.get("name"):
            out["display_name"] = bd["name"]
        elif bd.get("username"):
            out["display_name"] = bd["username"]
        if bd.get("biography"):
            out["bio"] = bd["biography"][:500].strip()
        if bd.get("profile_picture_url"):
            out["avatar_image_url"] = bd["profile_picture_url"]
        followers = bd.get("followers_count")
        if followers is not None:
            try:
                out["follower_count"] = int(followers)
            except (TypeError, ValueError):
                pass
        return out or None


class FacebookEnricher:
    """Public Page data via the Facebook Graph API, keyed by page handle or id.

    A creator's Facebook presence is a Page, and the Page node answers name,
    follower count and picture to a token that can read it. followers_count is
    the number to show; fan_count (likes) is kept only as a fallback for Pages
    that still report the two separately.
    """

    def __init__(self, token: str, version: str):
        self.token = token
        self.version = version

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        if platform != "facebook" or not self.token:
            return None
        node = handle[1:] if handle.startswith("@") else handle
        data = _graph_get(
            self.version,
            node,
            {
                "fields": "name,followers_count,fan_count,about,picture.type(large){url}",
                "access_token": self.token,
            },
        )
        # No name means the node did not resolve to a readable Page — an
        # unknown vanity, or one the token cannot see.
        if not data or not data.get("name"):
            return None

        out = EnrichedProfile()
        out["display_name"] = data["name"]
        if data.get("about"):
            out["bio"] = data["about"][:500].strip()
        # picture comes back nested as {"data": {"url": ...}}.
        pic = (data.get("picture") or {}).get("data") or {}
        if pic.get("url"):
            out["avatar_image_url"] = pic["url"]
        followers = data.get("followers_count")
        if followers is None:
            followers = data.get("fan_count")
        if followers is not None:
            try:
                out["follower_count"] = int(followers)
            except (TypeError, ValueError):
                pass
        return out or None


class CompositeEnricher:
    """Tries each configured enricher and returns the first result."""

    def __init__(self, enrichers: list[SocialEnricher]):
        self.enrichers = enrichers

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        for enricher in self.enrichers:
            data = enricher.fetch(platform, handle)
            if data:
                return data
        return None


def build_default_enricher() -> SocialEnricher:
    enrichers: list[SocialEnricher] = []
    if settings.youtube_api_key:
        enrichers.append(YouTubeEnricher(settings.youtube_api_key))
    # Instagram and Facebook are both read through the Meta Graph API, so they
    # share one token and version. Instagram also needs the Business account it
    # queries THROUGH; without that id its Business Discovery call cannot be
    # made, so it stays off even when the token is present, while Facebook runs
    # on the token alone. The platform guard inside each enricher keeps the
    # order here from mattering.
    if settings.meta_graph_token:
        if settings.instagram_business_account_id:
            enrichers.append(
                InstagramEnricher(
                    settings.meta_graph_token,
                    settings.instagram_business_account_id,
                    settings.meta_graph_version,
                )
            )
        enrichers.append(FacebookEnricher(settings.meta_graph_token, settings.meta_graph_version))
    # TikTok's enricher is added here once its OAuth app is approved.
    return CompositeEnricher(enrichers) if enrichers else NoopEnricher()


default_enricher: SocialEnricher = build_default_enricher()


def fetch_image(url: str) -> tuple[bytes, str] | None:
    """Download an avatar so it can be stored as a media asset.

    THE URL PASSED IN CAME OUT OF A THIRD PARTY'S API RESPONSE. Every caller
    reaches here with an `avatar_image_url` lifted off a Graph or YouTube
    payload, which means the address this process is about to dial was chosen
    by somebody who is not us. That is exactly the class of input that must not
    be handed the process's own network position: from inside the cluster,
    `http://169.254.169.254/...` and `http://10.0.0.5:6379/` answer in a way
    they never would from a creator's browser, and a fetch is a fetch whether
    the url arrived from a stranger or from Meta. The trust we place in the API
    is trust in what it SAYS, not permission for it to aim us.

    So, before any body is read:

    * The url has to be one we would hand to a browser at all (app.core.urls),
      which is what refuses `file://` and anything with a control character
      spliced into it.
    * The host must not be a loopback, private or link-local literal.
    * The content type has to be an image. Checking it after reading the body
      means having already paid for an HTML error page.

    REDIRECTS ARE STILL FOLLOWED, because avatar urls redirect constantly, but
    the address we actually LANDED on is put through both guards again. A
    guard on the first hop only is not a guard: a public url that answers 302
    to the metadata endpoint would otherwise walk the request there for us.

    And the body is streamed into a bounded buffer instead of being buffered
    whole. A declared Content-Length over the ceiling saves us reading a byte,
    but it is a claim rather than a measurement, so the running total of what
    actually arrived is what enforces the limit.
    """
    target = normalized_public_url(url)
    if target is None or not is_public_host(urlsplit(target).hostname):
        _log.warning("Avatar download refused, not a public web url: %s", url)
        return None
    try:
        with httpx.stream(
            "GET", target, timeout=TIMEOUT_SECONDS, follow_redirects=True
        ) as res:
            res.raise_for_status()

            # Where we ended up, which is not necessarily where we aimed.
            landed = normalized_public_url(str(res.url))
            if landed is None or not is_public_host(urlsplit(landed).hostname):
                _log.warning("Avatar download refused, redirected to %s", res.url)
                return None

            content_type = res.headers.get("content-type", "").split(";")[0].strip()
            if not content_type.startswith("image/"):
                return None

            declared = res.headers.get("content-length") or ""
            if declared.isdigit() and int(declared) > MAX_FETCHED_IMAGE_BYTES:
                return None

            body = bytearray()
            for chunk in res.iter_bytes():
                body += chunk
                if len(body) > MAX_FETCHED_IMAGE_BYTES:
                    # Abandoned mid-stream, and the `with` closes the response
                    # on the way out, so the rest of it is never pulled down.
                    _log.warning(
                        "Avatar download over %s bytes, abandoned: %s",
                        MAX_FETCHED_IMAGE_BYTES,
                        url,
                    )
                    return None
            return bytes(body), content_type
    except Exception as exc:
        _log.warning("Avatar download failed for %s: %s", url, exc)
        return None
