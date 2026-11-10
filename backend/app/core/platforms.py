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


# WHAT A GENERATED CONTRACT PRINTS, in both languages.
#
# The ids above are a machine vocabulary. A contract is a document somebody
# signs, and until this table existed a French one read "1 x video on tiktok":
# an English connector and two raw slugs, on the single line that says what is
# actually being bought.
#
# HERE RATHER THAN IN contracts/service.py, because adding a row to
# PLATFORM_DELIVERABLES above is the moment a label is owed, and a table kept
# in another module is a table somebody forgets. test_contracts.py asserts both
# maps cover every id, so a deliverable added without a label fails CI instead
# of printing a slug onto a signed document.
#
# THE CLIENTS KEEP THEIR OWN LABELS, and that is not duplication worth
# removing. They render a picker, this renders a document, and only one of the
# two is signed.
PLATFORM_LABELS: dict[str, str] = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "facebook": "Facebook",
    "youtube": "YouTube",
    "snapchat": "Snapchat",
    "x": "X",
    "threads": "Threads",
    "linkedin": "LinkedIn",
    "whatsapp": "WhatsApp",
    "discord": "Discord",
    "ugc": "UGC",
}

# Platform names are proper nouns and do not change with the language. The
# deliverables do, and the ones that stay English below stay English because
# that is the word French creators actually use for them: a Reel is a Reel, a
# Story is a Story. The rest are translated.
DELIVERABLE_LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "reel": "Reel",
        "post": "Publication",
        "story": "Story",
        "carousel": "Carrousel",
        "live": "Live",
        "video": "Vidéo",
        "photo_post": "Publication photo",
        "short": "Short",
        "community_post": "Publication communauté",
        "snap": "Snap",
        "spotlight": "Spotlight",
        "thread": "Fil",
        "article": "Article",
        "status": "Statut",
        "server_post": "Publication serveur",
        "ugc_video": "Vidéo UGC",
        "ugc_photo": "Photo UGC",
    },
    "en": {
        "reel": "Reel",
        "post": "Post",
        "story": "Story",
        "carousel": "Carousel",
        "live": "Live",
        "video": "Video",
        "photo_post": "Photo post",
        "short": "Short",
        "community_post": "Community post",
        "snap": "Snap",
        "spotlight": "Spotlight",
        "thread": "Thread",
        "article": "Article",
        "status": "Status",
        "server_post": "Server post",
        "ugc_video": "UGC video",
        "ugc_photo": "UGC photo",
    },
}

# "2 x Vidéo SUR TikTok" against "2 x Video ON TikTok".
_DELIVERABLE_ON = {"fr": "sur", "en": "on"}

# The one entry in PLATFORM_DELIVERABLES that is not a place content is posted.
UGC_PLATFORM = "ugc"


def _prettified(value: str) -> str:
    """A slug read as a label of last resort: "photo_post" -> "Photo post"."""
    cleaned = value.replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def deliverable_phrase(
    language: str,
    quantity: object,
    deliverable_type: object,
    platform: object,
) -> str:
    """One deliverable as a contract prints it: "2 x Vidéo sur TikTok".

    NEVER RAISES ON AN UNKNOWN ID, which is the whole reason this is a function
    and not two dictionary lookups at the call site. Contract generation runs
    when the CREATOR presses Accept, so a KeyError here would be a 500 landing
    on the one person who cannot fix it, over a label. An id with no entry falls
    back to its prettified self, which is wrong only for that one word and
    leaves the rest of the line correct.

    A MISSING QUANTITY DROPS THE COUNT rather than printing it. "None x Vidéo"
    is the output this function was written to end, and a deliverable whose
    quantity nobody stated reads better as an unspecified item than as a count
    of nothing.

    AN UNKNOWN LANGUAGE FALLS BACK TO ENGLISH rather than to the ids. Every
    caller passes the contract's own language, which is validated upstream, so
    this is the belt to that braces.
    """
    labels = DELIVERABLE_LABELS.get(language) or DELIVERABLE_LABELS["en"]
    type_label = labels.get(deliverable_type) or _prettified(str(deliverable_type or ""))
    platform_label = PLATFORM_LABELS.get(platform) or _prettified(str(platform or ""))

    parts: list[str] = []
    # bool is an int in Python, and True would read as "True x". Excluded here
    # rather than trusted not to arrive, because this value comes off a JSON
    # column that nothing in the database constrains.
    if isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0:
        parts.append(f"{quantity} x")
    if type_label:
        parts.append(type_label)
    # UGC NAMES NO PLATFORM, because it has none. The docstring at the top of
    # this file is the reason: UGC is content the brand runs as its own advert
    # and is never posted on the creator's account, so "Vidéo UGC sur UGC"
    # states a place that does not exist. The type label already carries the
    # word.
    if platform_label and platform != UGC_PLATFORM:
        parts.append(f"{_DELIVERABLE_ON.get(language, 'on')} {platform_label}")
    return " ".join(parts)
