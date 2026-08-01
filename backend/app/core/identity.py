"""Who a creator is, in one shape, for every list that shows one.

A business used to read three different answers to "who is this person" on a
single screen: the favourites list gave a name and a photo, the proposals list
gave a name and a photo of its own, and the invitations list gave a bare user
id ("Créateur e66cf36a"). Identity is not a per-list decision, so it is
resolved once, here, and every list spends the same four fields.

Why this sits in core rather than in one of the feature modules: campaigns and
discovery are siblings that do not import each other, and making one depend on
the other just to reach a display helper would invent a dependency for the
sake of a read model. campaigns.service is also already the bottom of an
existing import chain (contracts -> campaigns.service), so hanging discovery
underneath it would widen that chain for nothing. core/ is where the
cross-module facts both sides have to agree on already live — the platform
catalog, the price floors — and this is another one.

A phone number is never part of an identity. It is the only human-readable
column on the users table, and handing it to the other side of a deal is how a
negotiation leaves the platform, which is the thing contracts, escrow and
dispute resolution exist to prevent. A creator with no profile therefore comes
back as a row of nulls rather than as a fallback assembled from user data.
"""
from sqlalchemy.orm import Session

from app.core.platforms import PLATFORMS_WITH_AUDIENCE
from app.modules.profiles.models import InfluencerProfile, SocialAccount

# The fields a creator-facing row carries, in the order the schemas declare
# them. Named so a caller can spread an identity into a payload without
# knowing which keys it holds.
IDENTITY_FIELDS = ("display_name", "avatar_url", "top_platform", "top_follower_count")


def blank_identity() -> dict:
    """The shape with nothing in it.

    Returned for a creator who has not written a profile yet — which happens:
    somebody can be favourited or invited the day they sign up. Every caller
    can then build a row without asking whether the keys are there, and an
    empty card is a usable card where a 500 is not.
    """
    return {field: None for field in IDENTITY_FIELDS}


def creator_identities(db: Session, user_ids) -> dict[str, dict]:
    """Name, photo and headline audience number for a set of creators.

    Two queries for the whole list however long it is. The per-row version of
    this is what turns a thirty-proposal campaign page into sixty extra round
    trips, and it is why every caller hands in a list instead of calling once
    per row. Every requested id comes back, present or not.

    top_follower_count is the audience of the single biggest platform and
    never a total across them: the same person following a creator on
    Instagram and on TikTok is one person, and adding the two counts them
    twice. The public profile already presents audience one platform at a
    time for exactly this reason, and the two surfaces must not quote a brand
    different numbers for the same creator.

    Only platforms in PLATFORMS_WITH_AUDIENCE are eligible — WhatsApp Status
    exposes no public metric and Discord counts members, so neither is an
    audience we can put a figure on. Both fields are null when nothing
    qualifies, which is a real answer and not a zero: a creator with no
    connected account has an unknown audience, not an empty one.
    """
    unique_ids = {uid for uid in user_ids if uid}
    if not unique_ids:
        return {}

    profile_rows = (
        db.query(
            InfluencerProfile.user_id,
            InfluencerProfile.display_name,
            InfluencerProfile.avatar_media_id,
        )
        .filter(InfluencerProfile.user_id.in_(unique_ids))
        .all()
    )
    profiles_by_user = {
        user_id: (display_name, avatar_media_id)
        for user_id, display_name, avatar_media_id in profile_rows
    }

    social_rows = (
        db.query(SocialAccount.user_id, SocialAccount.platform, SocialAccount.follower_count)
        .filter(
            SocialAccount.user_id.in_(unique_ids),
            # sorted() only so the emitted SQL is stable between runs; a set
            # would order differently every process and make query logs
            # impossible to diff.
            SocialAccount.platform.in_(sorted(PLATFORMS_WITH_AUDIENCE)),
            SocialAccount.follower_count.isnot(None),
        )
        .all()
    )
    top_by_user: dict = {}
    for user_id, platform, follower_count in social_rows:
        current = top_by_user.get(user_id)
        if current is None or follower_count > current[1]:
            top_by_user[user_id] = (platform, follower_count)

    identities = {}
    for user_id in unique_ids:
        identity = blank_identity()
        profile = profiles_by_user.get(user_id)
        if profile is not None:
            display_name, avatar_media_id = profile
            identity["display_name"] = display_name
            # The same URL shape profiles.service._media_url builds, so one
            # media route serves every list that shows a face.
            identity["avatar_url"] = (
                f"/profiles/media/{avatar_media_id}" if avatar_media_id else None
            )
        top = top_by_user.get(user_id)
        if top is not None:
            identity["top_platform"], identity["top_follower_count"] = top
        identities[user_id] = identity
    return identities
