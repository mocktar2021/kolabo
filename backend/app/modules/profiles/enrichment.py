"""Social profile enrichment.

Auto filling a creator profile from their social account is what makes onboarding
one click. Doing it legitimately means the official platform APIs behind OAuth
(YouTube Data API, TikTok Login Kit, Instagram Graph), which prove ownership as
well as returning stats. Scraping public pages is fragile and generally against
platform terms, so it is deliberately not used here.

No provider credentials are configured yet, so the default enricher returns
nothing and the creator fills the fields themselves. Real enrichers drop in per
platform without touching the profile logic or the UI.
"""
from typing import Protocol


class EnrichedProfile(dict):
    """Keys, all optional: display_name, avatar_image_url, follower_count, bio."""


class SocialEnricher(Protocol):
    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        """Return public profile data for a handle, or None if unavailable."""
        ...


class NoopEnricher:
    """Default until platform API credentials exist. Never guesses."""

    supported: set[str] = set()

    def fetch(self, platform: str, handle: str) -> EnrichedProfile | None:
        return None


# Swap for a real enricher (for example YouTubeEnricher) once credentials are
# configured; see docs/social-enrichment.md.
default_enricher: SocialEnricher = NoopEnricher()
