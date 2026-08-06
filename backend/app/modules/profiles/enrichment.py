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

import httpx

from app.core.config import settings

_log = logging.getLogger("kolabo.profiles.enrichment")

TIMEOUT_SECONDS = 6.0


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
            _log.warning("YouTube enrichment failed for %s: %s", handle, exc)
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
        _log.warning("Meta Graph request failed for %s: %s", node, exc)
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
    """Download an avatar so it can be stored as a media asset."""
    try:
        res = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        res.raise_for_status()
        content_type = res.headers.get("content-type", "").split(";")[0].strip()
        if not content_type.startswith("image/"):
            return None
        return res.content, content_type
    except Exception as exc:
        _log.warning("Avatar download failed for %s: %s", url, exc)
        return None
