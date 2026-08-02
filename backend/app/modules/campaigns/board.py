"""The open board: briefs a creator can find without being invited.

WHY THERE IS A BOARD AT ALL, which is the reason this module exists and the
reason the query below is shaped the way it is. Until now a campaign reached
exactly the people the brand had already met: it was published, and then the
buyer invited specific creators off its favourites list. A creator nobody had
ever favourited had nothing to open — no list of live briefs, no way to put
themselves in front of a budget — and a brand's reach was capped at the people
it already knew. That is the cold start problem in both directions at once:
demand cannot find supply it has not already met, and supply stops opening a
page that never has anything on it. Everything here exists to close that loop.
Nothing here changes how an invited creator works; invitations, proposals and
contracts are untouched.

TARGETING IS A SOFT FILTER. THIS IS THE DESIGN DECISION IN THIS FILE.
A brand can say which categories, which countries and which audience size it
is after. A creator who matches sees that brief ranked FIRST — but ANY
signed-in creator may apply to ANY open brief, and targeting never removes a
row from anybody's board.

  Why not the hard filter every brand asks for. With a pilot roster of a few
  hundred creators, a hard filter shows most of them an empty board, and a
  board that is empty twice is a board nobody opens a third time — we would
  have built the cold start problem into the fix for it. The asymmetry
  settles it: a brand can decline an application it did not want, and that
  costs it one click; a brand can never receive the application it never saw,
  and that costs it the creator. So the targeting fields buy ranking, not
  exclusion.

WHO MAY READ THE BOARD. Signed-in creators, and nobody else — not the public,
and not the buying side. A brief carries a budget, a deadline and the shape of
a brand's plans for the quarter, which is competitive information: discovery
search is public because a creator's storefront is meant to be seen, and this
is the opposite of that. A business or agency calling it gets a 403 rather
than an empty list, because an empty list reads as "there are no open briefs"
and sends them to support.

A separate module from service.py for the reason editing.py and withdrawals.py
are: service.py is already long and is about creating campaigns and running
the negotiation on them. The dependency runs one way — router -> board ->
service, models. PROPOSAL CREATION IS NOT DUPLICATED HERE: applying calls
service.submit_proposal, which stays the one place a proposal row is written,
numbered and notified. The only thing this module tells it is that the bid was
unsolicited, which changes the wording of that notification and nothing else.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.campaigns import models, schemas, service
from app.modules.profiles.models import BusinessProfile, InfluencerProfile

# What each dimension of a match is worth. Fixed weights rather than tuned
# ones: this is a ranking hint over a few dozen briefs, not a recommender, and
# a number nobody can explain is a number nobody can defend to a brand asking
# why its brief is not being seen.
#
# Category is worth most because it is what a brief is actually about — a
# beauty brand wants beauty creators before it wants anything else. Country is
# worth less but is worth something: it is a hard commercial fact (payout
# rails, shipping, the language the audience speaks) rather than a taste.
# Audience band is worth least because it is the weakest signal we hold — the
# follower count is self-reported until platform analytics land.
CATEGORY_WEIGHT = 3
COUNTRY_WEIGHT = 2
FOLLOWER_WEIGHT = 1
MAX_MATCH_SCORE = CATEGORY_WEIGHT + COUNTRY_WEIGHT + FOLLOWER_WEIGHT

# How many briefs one board request carries. A creator scrolling a job board
# reads the top of it; past this the page costs more than it returns, and the
# ranking has already put the interesting rows at the top.
BOARD_LIMIT = 50

# Said in full because each has to teach as well as refuse.
NOT_A_CREATOR_DETAIL = (
    "Only creators can browse open briefs. A brief carries a budget and a "
    "brand's plans, so the board stays behind a creator login."
)
NOT_OPEN_DETAIL = (
    "This brief is not open to applications. The brand invites creators to it "
    "directly."
)
DIRECT_ORDER_DETAIL = (
    "This is a direct order addressed to one creator, not an open brief, and "
    "it cannot be applied to."
)
ALREADY_APPLIED_DETAIL = (
    "You already have a live proposal on this brief. Edit it by submitting a "
    "new version instead of applying again."
)


def match_score(
    *,
    target_categories=None,
    target_countries=None,
    target_min_followers: int | None = None,
    target_max_followers: int | None = None,
    creator_categories=None,
    creator_country: str | None = None,
    creator_followers: int | None = None,
) -> int:
    """How well one creator fits one brief, as a small whole number.

    PURE ON PURPOSE: no database, no request, no clock, no models. It takes
    plain values and returns an int, which is what makes the ranking rule
    testable on its own — the board query can then be tested for what it
    filters rather than for what it sorts, and the two failures stay apart.

    Three dimensions, each contributing its fixed weight or nothing:

      category   ANY overlap scores the full weight, deliberately not a
                 proportion. A brief naming three categories and a creator
                 who covers one of them is a match on that one; scaling by
                 how many they share would rank a generalist listing eight
                 categories above the specialist the brand actually wants.
      country    the creator's country is one the brief named.
      followers  the creator's audience falls inside the band, where an
                 unnamed end of the band is simply open.

    A DIMENSION THE BRIEF SAYS NOTHING ABOUT SCORES NOTHING. So a brief that
    targets nothing at all scores 0 for everybody, and that is the decision
    rather than an accident of the arithmetic: it ranks BELOW any deliberate
    match. A brand that named categories and got a creator in one of them is
    looking at somebody it asked for; a brand that named nobody has expressed
    no preference and has no claim on the top of the board. The alternative —
    giving an untargeted brief a middling score so it interleaves — would
    push real matches down the page on behalf of briefs whose author never
    said who they wanted. The untargeted brief still APPEARS, on every
    creator's board, which is the part that matters: it is open to all.

    An unknown follower count scores nothing rather than being read as zero.
    Zero is a claim we cannot make, and making it would sink every creator
    who has not filled the field in to the bottom of every targeted board.
    """
    score = 0

    if target_categories and set(target_categories) & set(creator_categories or []):
        score += CATEGORY_WEIGHT

    if target_countries and creator_country in set(target_countries):
        score += COUNTRY_WEIGHT

    if target_min_followers is not None or target_max_followers is not None:
        if creator_followers is not None:
            # An unnamed end of the band is open, not zero and not infinite.
            low = target_min_followers if target_min_followers is not None else creator_followers
            high = target_max_followers if target_max_followers is not None else creator_followers
            if low <= creator_followers <= high:
                score += FOLLOWER_WEIGHT

    return score


def _require_creator(db: Session, user_id: str) -> User:
    """The board is the selling side's screen, and only the selling side's.

    AUTHOR_EXCLUDED_ROLE is reused rather than restated: the role that may not
    author a brief is precisely the role that may browse and bid on one, the
    same way resolve_negotiated_terms reuses it to decide who can be sent an
    offer. Stating "influencer" again here would give a second place to
    forget the day the roles change.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role != service.AUTHOR_EXCLUDED_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=NOT_A_CREATOR_DETAIL
        )
    return user


def _company_names(db: Session, business_user_ids) -> dict:
    """Buyer company names for the whole board in ONE query.

    A creator decides whether to spend an evening pricing a brief partly on
    who is asking, so the name has to be on the card. The same brand usually
    has several briefs up, and the per-row version of this lookup is what
    turns a fifty-brief board into fifty extra round trips.

    Null where the buyer has written no profile, and it stays null: the users
    table holds nothing else to fall back on but a phone number, and a phone
    number is never part of a payload handed to the other side of a deal.
    """
    ids = {uid for uid in business_user_ids if uid}
    if not ids:
        return {}
    rows = (
        db.query(BusinessProfile.user_id, BusinessProfile.company_name)
        .filter(BusinessProfile.user_id.in_(ids))
        .all()
    )
    return {user_id: company_name for user_id, company_name in rows}


def _my_state(db: Session, campaign_ids, influencer_user_id: str) -> tuple[set, set]:
    """Which of these briefs the caller has already applied to, or been invited to.

    Two queries for the whole board rather than two per row, for the same
    reason as the names above. Both facts change the card completely: a
    creator must not be invited to apply to something they already bid on,
    and an invited creator is looking at a brief that was addressed to them
    rather than one they found.

    Applied means ANY version, including superseded and withdrawn ones. The
    question the card answers is "have I been here before", and a chain that
    reached version four is four evenings of having been here before.
    """
    ids = set(campaign_ids)
    if not ids:
        return set(), set()
    applied = {
        row[0]
        for row in db.query(models.Proposal.campaign_id)
        .filter(
            models.Proposal.campaign_id.in_(ids),
            models.Proposal.influencer_user_id == influencer_user_id,
        )
        .all()
    }
    invited = {
        row[0]
        for row in db.query(models.CampaignInvitation.campaign_id)
        .filter(
            models.CampaignInvitation.campaign_id.in_(ids),
            models.CampaignInvitation.influencer_user_id == influencer_user_id,
        )
        .all()
    }
    return applied, invited


def _targeting_out(campaign: models.Campaign) -> dict:
    """The targeting a brief carries, so a creator can see why it ranked.

    Shown rather than hidden: a board that silently reorders itself is a board
    creators invent theories about. The fields also tell a creator whether a
    brief they do not match is worth applying to anyway, which — targeting
    being soft — is always allowed and is sometimes exactly right.
    """
    return {
        "is_open": campaign.is_open,
        "target_categories": campaign.target_categories or [],
        "target_countries": campaign.target_countries or [],
        "target_min_followers": campaign.target_min_followers,
        "target_max_followers": campaign.target_max_followers,
    }


def list_open_campaigns(
    db: Session,
    influencer_user_id: str,
    limit: int = BOARD_LIMIT,
    offset: int = 0,
) -> list[dict]:
    """The open board for one creator: every open brief, best fit first.

    THE QUERY IS THE FEATURE, so what it filters on is worth stating. Only
    PUBLISHED (which excludes drafts, and excludes cancelled campaigns because
    cancelled is its own status — a called-off brief must never sit on a board
    collecting bids nobody will read), only is_open, and never is_direct: a
    direct order is a private transaction between two named parties wearing a
    campaign's clothes, and the rule that it stays off any listing somebody
    else can read is older than this module.

    Targeting is NOT in the filter and that is the whole design — see the
    module docstring. It is in the sort.
    """
    user = _require_creator(db, influencer_user_id)
    profile = (
        db.query(InfluencerProfile)
        .filter(InfluencerProfile.user_id == influencer_user_id)
        .first()
    )
    # A creator with no profile yet still gets a board — an empty one would be
    # the worst possible first screen for somebody who just signed up. They
    # simply match nothing, so everything scores 0 and they see the newest
    # briefs first, which is a perfectly good board.
    creator_categories = list(profile.categories or []) if profile is not None else []
    creator_followers = profile.follower_count if profile is not None else None

    campaigns = (
        db.query(models.Campaign)
        .filter(
            models.Campaign.status == models.PUBLISHED,
            models.Campaign.is_open.is_(True),
            models.Campaign.is_direct.is_(False),
        )
        .all()
    )
    if not campaigns:
        return []

    names = _company_names(db, [c.business_user_id for c in campaigns])
    applied, invited = _my_state(db, [c.id for c in campaigns], influencer_user_id)

    scored = [
        (
            campaign,
            match_score(
                target_categories=campaign.target_categories,
                target_countries=campaign.target_countries,
                target_min_followers=campaign.target_min_followers,
                target_max_followers=campaign.target_max_followers,
                creator_categories=creator_categories,
                creator_country=user.country_code,
                creator_followers=creator_followers,
            ),
        )
        for campaign in campaigns
    ]
    # Two stable sorts rather than one composite key, because a datetime
    # cannot be negated the way a score can. Date first, then score: Python's
    # sort is stable, so briefs that tie on score keep the newest-first order
    # the first pass gave them.
    scored.sort(key=lambda item: item[0].created_at, reverse=True)
    scored.sort(key=lambda item: item[1], reverse=True)

    page = scored[offset : offset + limit]
    return [
        {
            **service._to_out(campaign),
            **_targeting_out(campaign),
            "business_company_name": names.get(campaign.business_user_id),
            "match_score": score,
            "has_applied": campaign.id in applied,
            "is_invited": campaign.id in invited,
        }
        for campaign, score in page
    ]


def apply_to_campaign(
    db: Session, campaign_id: str, influencer_user_id: str, payload: schemas.ProposalIn
) -> dict:
    """A creator bids on a brief nobody invited them to.

    THE PROPOSAL ITSELF IS NOT WRITTEN HERE. Everything below is a question
    about whether this creator may bid on this brief at all; the moment the
    answer is yes the work goes to service.submit_proposal, which numbers the
    version, supersedes the previous one, notifies the buyer and commits. An
    application is not a second kind of proposal and must never become one:
    two ways to write that row would be two places for the version chain to
    drift, and the version chain is what a contract is written from. The
    brand consequently sees applications in the ordinary proposals list on
    its campaign page, with no change there at all — get_campaign_detail
    selects every proposal on the campaign and has never filtered by
    invitation.

    is_application=True is the ONE thing this path tells submit_proposal, and
    it changes the notification's wording and nothing else. The row and the
    chain stay identical, which is the point of delegating; but the brand's
    bell has to tell an unsolicited application from an invited creator's
    answer, because those are two different decisions and only one of them was
    expected. Everything downstream still cannot tell them apart, deliberately.

    The published check is submit_proposal's, deliberately not repeated: it
    already refuses a draft or a cancelled brief with a sentence, and a second
    copy of that rule here would be a second thing to update.
    """
    _require_creator(db, influencer_user_id)

    campaign = (
        db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    # Checked before is_open, because a direct order is never open and "this
    # brief is not open" would be a true sentence that explains nothing about
    # what the caller actually found.
    if campaign.is_direct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=DIRECT_ORDER_DETAIL
        )
    if not campaign.is_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NOT_OPEN_DETAIL)

    latest = service.latest_in_chain(db, campaign_id, influencer_user_id)
    if latest is not None and latest.status == models.SUBMITTED:
        # A 409 rather than a silent second version. Applying twice is a
        # double-tapped button or a creator who forgot, and quietly writing a
        # second row would supersede terms the brand may already be reading —
        # changing the offer under them without either side meaning to. A
        # creator who genuinely wants different terms revises the chain
        # through the proposals endpoint, where the intent is explicit.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=ALREADY_APPLIED_DETAIL
        )

    return service.submit_proposal(
        db, campaign_id, influencer_user_id, payload, is_application=True
    )
