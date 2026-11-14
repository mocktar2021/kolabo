"""Blocks, on the surfaces that WRITE.

The list surfaces filter (tests/test_blocks_discovery.py) and say nothing
about why a row is missing. These ones refuse, out loud, with a code — and
the split is the whole design: a shorter list discloses nothing, while an
action aimed at one named person that silently did nothing would leave its
author believing something happened that did not. See
trust_safety.blocks.require_not_blocked for why the refused party is told
plainly rather than failed silently.

BOTH DIRECTIONS, EVERY TIME, and they are not the same assertion. A block row
has one direction and the refusal has two sentences: blocked_user when the
caller is the one who blocked ("unblock them to continue", which they can
act on), blocked_by_user when they are the one who was blocked (which they
cannot). A guard that read the row's direction instead of the pair would pass
half of these and fail the other half.

EVERY TEST HAS A CONTROL. A refusal test with no control passes just as
happily against a path that is broken for everybody, which is the exact
failure these guards could introduce. So each one establishes that the call
gets through without a block first, or asserts that the unblocked call fails
somewhere LATER for an unrelated reason.

Written against the service functions rather than through the routers. The
guard is a service-layer rule, the routers add nothing to it, and the
campaign, order and contract flows need enough fixture to build that going
through HTTP would test the fixture more than the rule.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, import_all_models
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.campaigns import models as cmodels
from app.modules.campaigns import schemas as cschemas
from app.modules.campaigns import service as campaigns_service
from app.modules.contracts import service as contracts_service
from app.modules.discovery import service as discovery_service
from app.modules.profiles import models as pmodels
from app.modules.trust_safety.models import Block


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    # Before create_all, always: Review has a foreign key to escrows, and a
    # table nothing imported is a table create_all cannot resolve.
    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _user(db, suffix, role):
    user = User(
        phone=f"+2299009{suffix}",
        email=f"{suffix}@kolabo.test",
        password_hash="x",
        country_code="BJ",
        role=role,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


def _business(db, suffix):
    return _user(db, suffix, "business")


def _creator(db, suffix):
    """A creator with a profile, because every one of these paths resolves a
    display name through app.core.identity before it answers. A bare user row
    would make these tests turn on how that helper treats a profile-less id,
    which is not what any of them are about."""
    user_id = _user(db, suffix, "influencer")
    db.add(
        pmodels.InfluencerProfile(
            user_id=user_id,
            bio="Creator",
            categories=["fashion"],
            rate_card={},
            follower_count=5000,
            display_name=f"Creator {suffix}",
        )
    )
    db.commit()
    return user_id


def _block(db, blocker, blocked):
    db.add(Block(blocker_user_id=blocker, blocked_user_id=blocked))
    db.commit()


def _campaign(db, business_user_id, *, is_open=True, is_direct=False, status=None):
    campaign = cmodels.Campaign(
        business_user_id=business_user_id,
        title="A brief",
        budget_amount=100000,
        budget_currency="XOF",
        deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
        deadline=None,
        status=status or cmodels.PUBLISHED,
        is_direct=is_direct,
        is_open=is_open,
        target_categories=[],
        target_countries=[],
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _package(db, creator_user_id):
    package = pmodels.Package(
        user_id=creator_user_id,
        platform="instagram",
        deliverable_type="post",
        title="1 IG post",
        price_amount=30000,
        currency="XOF",
        is_active=True,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


def _offer(creator_user_id):
    """The shape resolve_negotiated_terms reads, with terms that clear every
    rule validate_offer applies, so the only thing left to refuse is the pair."""
    return SimpleNamespace(
        creator_user_id=creator_user_id,
        platform="instagram",
        deliverable_type="post",
        quantity=1,
        rate_amount=30000,
        currency="XOF",
        timeline_days=7,
        note=None,
        licence_terms=None,
    )


def _creator_offer(db, campaign_id, creator_user_id):
    """A live proposal authored by the creator, which is what an acceptance
    signs and what a business reply answers."""
    proposal = cmodels.Proposal(
        campaign_id=campaign_id,
        influencer_user_id=creator_user_id,
        version=1,
        rate_amount=30000,
        rate_currency="XOF",
        timeline_days=7,
        note=None,
        author_role=cmodels.AUTHOR_INFLUENCER,
        status=cmodels.SUBMITTED,
        expires_at=None,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def _refusal(excinfo):
    return excinfo.value.status_code, excinfo.value.code


# ---- the shortlist ----

def test_a_brand_cannot_shortlist_a_creator_it_blocked(db):
    biz, creator = _business(db, "10001"), _creator(db, "10002")
    # The control: it works before the block, so a later refusal is the block.
    assert discovery_service.add_favorite(db, biz, creator)["influencer_user_id"] == creator

    _block(db, biz, creator)
    with pytest.raises(AppError) as excinfo:
        discovery_service.add_favorite(db, biz, creator)
    assert _refusal(excinfo) == (403, "blocked_user")


def test_a_brand_cannot_shortlist_a_creator_who_blocked_it(db):
    biz, creator = _business(db, "10011"), _creator(db, "10012")
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        discovery_service.add_favorite(db, biz, creator)
    assert _refusal(excinfo) == (403, "blocked_by_user")


def test_a_missing_account_is_still_reported_as_missing(db):
    """The guard sits after the 404 on purpose: a block refusal about somebody
    who does not exist would be a sentence about a person who is not there."""
    biz = _business(db, "10021")
    with pytest.raises(AppError) as excinfo:
        discovery_service.add_favorite(db, biz, "no-such-user")
    assert _refusal(excinfo) == (404, "campaign_influencer_not_found")


def test_unshortlisting_still_works_while_blocked(db):
    """remove_favorite is deliberately unguarded. A block must not strand a
    row that list_favorites already hides: invisible AND unremovable is the
    one outcome worse than either."""
    biz, creator = _business(db, "10031"), _creator(db, "10032")
    discovery_service.add_favorite(db, biz, creator)
    _block(db, biz, creator)

    discovery_service.remove_favorite(db, biz, creator)
    assert discovery_service.list_favorites(db, biz) == []


# ---- invitations ----

def test_a_brand_cannot_invite_a_creator_it_blocked(db):
    biz, creator = _business(db, "10101"), _creator(db, "10102")
    campaign = _campaign(db, biz)
    assert campaigns_service.invite_influencer(db, campaign.id, biz, creator)["status"] == cmodels.INVITED

    other = _creator(db, "10103")
    _block(db, biz, other)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.invite_influencer(db, campaign.id, biz, other)
    assert _refusal(excinfo) == (403, "blocked_user")


def test_a_brand_cannot_invite_a_creator_who_blocked_it(db):
    biz, creator = _business(db, "10111"), _creator(db, "10112")
    campaign = _campaign(db, biz)
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.invite_influencer(db, campaign.id, biz, creator)
    assert _refusal(excinfo) == (403, "blocked_by_user")


# ---- orders, both forms, which is also every cart line ----

def test_a_package_cannot_be_ordered_from_a_blocked_creator(db):
    biz, creator = _business(db, "10201"), _creator(db, "10202")
    package = _package(db, creator)
    # The control: the resolver answers before the block exists.
    assert campaigns_service.resolve_package_terms(db, biz, package.id)["creator_user_id"] == creator

    _block(db, biz, creator)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.resolve_package_terms(db, biz, package.id)
    assert _refusal(excinfo) == (403, "blocked_user")


def test_a_package_cannot_be_ordered_from_a_creator_who_blocked_the_buyer(db):
    biz, creator = _business(db, "10211"), _creator(db, "10212")
    package = _package(db, creator)
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.resolve_package_terms(db, biz, package.id)
    assert _refusal(excinfo) == (403, "blocked_by_user")


def test_custom_terms_cannot_be_offered_to_a_blocked_creator(db):
    biz, creator = _business(db, "10221"), _creator(db, "10222")
    assert campaigns_service.resolve_negotiated_terms(db, biz, _offer(creator))["creator_user_id"] == creator

    _block(db, biz, creator)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.resolve_negotiated_terms(db, biz, _offer(creator))
    assert _refusal(excinfo) == (403, "blocked_user")


def test_custom_terms_cannot_be_offered_to_a_creator_who_blocked_the_buyer(db):
    biz, creator = _business(db, "10231"), _creator(db, "10232")
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.resolve_negotiated_terms(db, biz, _offer(creator))
    assert _refusal(excinfo) == (403, "blocked_by_user")


def test_the_basket_is_refused_before_any_of_it_is_written(db):
    """The guard is in the resolvers rather than in _place_order so that a
    cart holding one blocked creator is refused whole. Asserting the shape of
    that: the resolver raises, and no campaign row exists afterwards."""
    biz, creator = _business(db, "10241"), _creator(db, "10242")
    package = _package(db, creator)
    _block(db, biz, creator)

    with pytest.raises(AppError):
        campaigns_service.resolve_package_terms(db, biz, package.id)
    assert db.query(cmodels.Campaign).count() == 0


# ---- proposals, both sides ----

def test_a_creator_cannot_bid_on_a_brief_from_a_brand_they_blocked(db):
    biz, creator = _business(db, "10301"), _creator(db, "10302")
    campaign = _campaign(db, biz)
    payload = cschemas.ProposalIn(rate_amount=30000, rate_currency="XOF", timeline_days=7)
    assert campaigns_service.submit_proposal(db, campaign.id, creator, payload)["version"] == 1

    other = _creator(db, "10303")
    _block(db, other, biz)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.submit_proposal(db, campaign.id, other, payload)
    assert _refusal(excinfo) == (403, "blocked_user")


def test_a_creator_cannot_bid_on_a_brief_from_a_brand_that_blocked_them(db):
    biz, creator = _business(db, "10311"), _creator(db, "10312")
    campaign = _campaign(db, biz)
    _block(db, biz, creator)
    payload = cschemas.ProposalIn(rate_amount=30000, rate_currency="XOF", timeline_days=7)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.submit_proposal(db, campaign.id, creator, payload)
    assert _refusal(excinfo) == (403, "blocked_by_user")


def test_a_brand_cannot_counter_a_blocked_creators_offer(db):
    biz, creator = _business(db, "10321"), _creator(db, "10322")
    campaign = _campaign(db, biz)
    offer = _creator_offer(db, campaign.id, creator)
    _block(db, biz, creator)

    payload = cschemas.ProposalReplyIn(rate_amount=25000)
    with pytest.raises(AppError) as excinfo:
        campaigns_service.reply_to_proposal(db, campaign.id, offer.id, biz, payload)
    assert _refusal(excinfo) == (403, "blocked_user")
    # The refusal leaves the creator's offer standing, which is the reason the
    # guard sits above the supersede rather than below it.
    db.refresh(offer)
    assert offer.status == cmodels.SUBMITTED


def test_a_brand_cannot_counter_an_offer_from_a_creator_who_blocked_it(db):
    biz, creator = _business(db, "10331"), _creator(db, "10332")
    campaign = _campaign(db, biz)
    offer = _creator_offer(db, campaign.id, creator)
    _block(db, creator, biz)

    with pytest.raises(AppError) as excinfo:
        campaigns_service.reply_to_proposal(
            db, campaign.id, offer.id, biz, cschemas.ProposalReplyIn(rate_amount=25000)
        )
    assert _refusal(excinfo) == (403, "blocked_by_user")


# ---- the contract, which is the last gate before money ----

def test_no_contract_is_written_between_blocked_people(db):
    biz, creator = _business(db, "10401"), _creator(db, "10402")
    campaign = _campaign(db, biz)
    offer = _creator_offer(db, campaign.id, creator)
    _block(db, biz, creator)

    with pytest.raises(AppError) as excinfo:
        contracts_service.generate_from_proposal(db, biz, offer.id)
    assert _refusal(excinfo) == (403, "blocked_user")
    # And the chain is untouched: the guard sits with the other refusals,
    # above the line that marks the proposal accepted.
    db.refresh(offer)
    assert offer.status == cmodels.SUBMITTED


def test_no_contract_is_written_when_the_creator_blocked_the_brand(db):
    biz, creator = _business(db, "10411"), _creator(db, "10412")
    campaign = _campaign(db, biz)
    offer = _creator_offer(db, campaign.id, creator)
    _block(db, creator, biz)

    with pytest.raises(AppError) as excinfo:
        contracts_service.generate_from_proposal(db, biz, offer.id)
    assert _refusal(excinfo) == (403, "blocked_by_user")


def test_without_a_block_generation_reaches_the_party_details_gate(db):
    """The control for the two above, and it has to be an indirect one: these
    accounts have no party details, so a successful generation is not
    available to assert. What it proves is that the block guard did NOT fire
    and the function ran on to the next refusal, which is the only thing
    these two tests are about."""
    biz, creator = _business(db, "10421"), _creator(db, "10422")
    campaign = _campaign(db, biz)
    offer = _creator_offer(db, campaign.id, creator)

    with pytest.raises(AppError) as excinfo:
        contracts_service.generate_from_proposal(db, biz, offer.id)
    assert excinfo.value.code == "contract_business_party_missing"


# ---- somebody else's block is not mine ----

def test_a_block_between_two_other_people_refuses_nothing(db):
    biz, creator = _business(db, "10501"), _creator(db, "10502")
    stranger = _creator(db, "10503")
    _block(db, biz, stranger)

    assert discovery_service.add_favorite(db, biz, creator)["influencer_user_id"] == creator
    campaign = _campaign(db, biz)
    assert campaigns_service.invite_influencer(db, campaign.id, biz, creator)["status"] == cmodels.INVITED
