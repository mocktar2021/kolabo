"""Social profile enrichment.

Auto filling a creator profile from their social account is what makes onboarding
one click. Doing it legitimately means the official platform APIs, not scraping,
which is fragile and generally against platform terms.

What each platform needs:
- YouTube: a Google Cloud API key for YouTube Data API v3. Public channel data
  (title, avatar, subscriber count) needs only the key, no OAuth and no app
  review, so it works as soon as YOUTUBE_API_KEY is set.
- TikTok: Login Kit OAuth plus the user.info.stats scope, which requires an
  approved TikTok for Developers app.
- Instagram: Instagram Graph API with App Review and a Business or Creator
  account.

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
    # TikTok and Instagram enrichers are added here once their OAuth apps are
    # approved and credentials are configured.
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
