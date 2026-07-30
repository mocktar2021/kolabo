"""Social platforms and what can be sold on each.

One source of truth shared by profile validation, package creation, and the UI,
so a deliverable can never be offered on a platform where it does not exist.

Notes on accuracy:
- TikTok's core unit is a video; Stories and photo posts exist but are secondary.
- Snapchat has Snaps, Stories, and Spotlight, not generic "posts".
- On X a thread is a distinct deliverable from a single post.
- WhatsApp Status has no public metrics, so it cannot be verified or measured;
  it is offered but never counted as audience.
- Discord counts members rather than followers, and posting happens in a server.
- UGC is platform agnostic: content produced for the brand to run as its own
  ads, never posted on the creator's account.
"""

# platform id -> deliverable type ids
PLATFORM_DELIVERABLES: dict[str, list[str]] = {
    "instagram": ["reel", "post", "story", "carousel", "live"],
    "tiktok": ["video", "photo_post", "story", "live"],
    "facebook": ["reel", "post", "story", "live"],
    "youtube": ["video", "short", "live", "community_post"],
    "snapchat": ["snap", "story", "spotlight"],
    "x": ["post", "thread", "video"],
    "threads": ["post", "video"],
    "linkedin": ["post", "article", "video"],
    "whatsapp": ["status"],
    "discord": ["server_post"],
    "ugc": ["ugc_video", "ugc_photo"],
}

SOCIAL_PLATFORMS = set(PLATFORM_DELIVERABLES)

# Platforms that expose a public audience number we can display and, in time,
# verify. WhatsApp Status has no public metric; Discord counts members and UGC
# has no audience of its own.
PLATFORMS_WITH_AUDIENCE = {
    "instagram", "tiktok", "facebook", "youtube", "snapchat", "x", "threads", "linkedin",
}

DELIVERABLE_TYPES = {d for ds in PLATFORM_DELIVERABLES.values() for d in ds}


def is_valid_pair(platform: str, deliverable_type: str) -> bool:
    return deliverable_type in PLATFORM_DELIVERABLES.get(platform, [])
