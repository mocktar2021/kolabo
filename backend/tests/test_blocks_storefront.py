"""The public storefront, which is the last of the eleven surfaces blocks.py
names and the only one that CONCEALS instead of refusing.

WHY IT IS DIFFERENT FROM EVERY OTHER GUARD IN THIS SUITE. A write path answers
403 and names which way round the block went, because the two people on it may
be bound by a contract and a silent failure would leave one of them believing
they had answered when they had not. This page is reached by anybody with a
link, including people who are not signed in at all, so a 403 naming the block
would turn a URL into a way to test whether a particular person has blocked
you, learned without ever contacting them and therefore without them ever
finding out. It answers 404 instead, with the code a missing profile already
uses.

SO THE CENTRAL ASSERTION IS AN EQUALITY, not a status code. A blocked reader
and a reader asking about a creator who does not exist must get the same
refusal, because anything that distinguishes them is the disclosure this is
built to avoid. test_the_refusal_is_indistinguishable_from_a_missing_profile is
the one to keep if the rest are ever trimmed.

A CONTROL ON EVERY REFUSAL, as in tests/test_blocks_write_paths.py: a test that
only proves the page is gone passes just as happily against a page that is
gone for everybody, which is exactly the regression this guard could cause.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, import_all_models
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.profiles import models as pmodels
from app.modules.profiles import service as profiles_service
from app.modules.trust_safety.models import Block


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _user(db, suffix, role):
    user = User(
        phone=f"+2299008{suffix}",
        email=f"sf{suffix}@kolabo.test",
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


def _refusal(excinfo):
    return excinfo.value.status_code, excinfo.value.code


# ---- the page still works, which is most of the point ----

def test_a_signed_out_visitor_sees_the_storefront(db):
    """The default and the common case. This page is public because a brand has
    to be able to look at the roster before it has an account, so a request
    with no viewer must cost nothing and change nothing."""
    creator = _creator(db, "20001")
    page = profiles_service.get_public_profile(db, creator)
    assert page["user_id"] == creator
    assert page["display_name"] == "Creator 20001"


def test_a_signed_in_stranger_sees_the_storefront(db):
    """The control for every refusal below: a viewer who is simply not blocked
    gets the same page a visitor gets."""
    biz, creator = _business(db, "20011"), _creator(db, "20012")
    page = profiles_service.get_public_profile(db, creator, viewer_id=biz)
    assert page["user_id"] == creator


def test_a_creator_still_sees_their_own_page(db):
    """A row where both columns hold the same id should not exist: block_user
    refuses a self block. The guard skips the lookup when the viewer IS the
    owner anyway, because a helper that could hide somebody's own storefront
    from them if such a row ever appeared is a helper that fails in a way
    nobody would guess. blocks.blocked_pair_ids discards the caller for the
    same reason, so this is the matching defence on the read path."""
    creator = _creator(db, "20021")
    _block(db, creator, creator)
    assert profiles_service.get_public_profile(db, creator, viewer_id=creator)["user_id"] == creator


def test_a_block_between_two_other_people_hides_nothing(db):
    biz, creator = _business(db, "20031"), _creator(db, "20032")
    stranger = _creator(db, "20033")
    _block(db, biz, stranger)
    assert profiles_service.get_public_profile(db, creator, viewer_id=biz)["user_id"] == creator


# ---- and it disappears, in both directions ----

def test_the_page_is_gone_for_a_brand_that_blocked_the_creator(db):
    biz, creator = _business(db, "20101"), _creator(db, "20102")
    assert profiles_service.get_public_profile(db, creator, viewer_id=biz)["user_id"] == creator

    _block(db, biz, creator)
    with pytest.raises(AppError) as excinfo:
        profiles_service.get_public_profile(db, creator, viewer_id=biz)
    assert _refusal(excinfo) == (404, "profile_not_found")


def test_the_page_is_gone_for_a_brand_the_creator_blocked(db):
    """The direction that would be missed by a guard reading the row instead of
    the pair, and the more important of the two: this is the reader who has
    been blocked and still has the URL."""
    biz, creator = _business(db, "20111"), _creator(db, "20112")
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        profiles_service.get_public_profile(db, creator, viewer_id=biz)
    assert _refusal(excinfo) == (404, "profile_not_found")


def test_it_is_still_gone_when_both_have_blocked_each_other(db):
    biz, creator = _business(db, "20121"), _creator(db, "20122")
    _block(db, biz, creator)
    _block(db, creator, biz)
    with pytest.raises(AppError) as excinfo:
        profiles_service.get_public_profile(db, creator, viewer_id=biz)
    assert _refusal(excinfo) == (404, "profile_not_found")


# ---- the assertion the whole design rests on ----

def test_the_refusal_is_indistinguishable_from_a_missing_profile(db):
    """THE POINT OF THE WHOLE GUARD. If these two refusals differed in any
    respect a client can see, the page would be a block oracle: ask about
    somebody, compare the answer, learn whether they blocked you without ever
    contacting them.

    Compared field by field rather than just on the code, because a status, a
    code and an interpolation value are all things a client reads, and a
    `values` dict quietly carrying a user id would leak just as much as a
    different code would."""
    biz, creator = _business(db, "20201"), _creator(db, "20202")
    _block(db, creator, biz)

    with pytest.raises(AppError) as blocked:
        profiles_service.get_public_profile(db, creator, viewer_id=biz)
    with pytest.raises(AppError) as absent:
        profiles_service.get_public_profile(db, "no-such-creator", viewer_id=biz)

    assert blocked.value.status_code == absent.value.status_code
    assert blocked.value.code == absent.value.code
    assert blocked.value.detail == absent.value.detail
    assert getattr(blocked.value, "values", None) == getattr(absent.value, "values", None)


def test_a_blocked_reader_is_refused_even_when_the_profile_is_complete(db):
    """A profile that is searchable is as present as a profile gets, so this
    rules out the refusal coming from completeness rather than from the block.
    Three active packages is what makes a profile go live, per
    app/core/pricing.py."""
    biz, creator = _business(db, "20211"), _creator(db, "20212")
    for index in range(3):
        db.add(
            pmodels.Package(
                user_id=creator,
                platform="instagram",
                deliverable_type="post",
                title=f"Package {index}",
                price_amount=30000,
                currency="XOF",
                is_active=True,
            )
        )
    db.commit()
    assert profiles_service.get_public_profile(db, creator, viewer_id=biz)["is_searchable"] is True

    _block(db, biz, creator)
    with pytest.raises(AppError) as excinfo:
        profiles_service.get_public_profile(db, creator, viewer_id=biz)
    assert _refusal(excinfo) == (404, "profile_not_found")


def test_an_anonymous_reader_is_never_refused_by_a_block(db):
    """Signing out must not become a way around a block, and it is not, but it
    is also not a way INTO one: there is no viewer to be blocked, so the page
    answers. The block hides the creator from one named account, which is all a
    block has ever claimed to do, and the lists behave the same way."""
    biz, creator = _business(db, "20221"), _creator(db, "20222")
    _block(db, biz, creator)
    _block(db, creator, biz)
    assert profiles_service.get_public_profile(db, creator, viewer_id=None)["user_id"] == creator
