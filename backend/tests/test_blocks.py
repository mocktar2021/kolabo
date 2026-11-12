"""The blocks foundation: the table's one constraint, the two read helpers,
and the dependency that lets a public endpoint know who is asking.

Nothing here goes through a router, because at this point nothing creates a
block or honours one. These are the questions the enforcement layer will ask,
tested before anything depends on the answers.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, import_all_models
from app.core.security import create_access_token
from app.modules.auth.deps import get_optional_user_id
from app.modules.trust_safety import blocks
from app.modules.trust_safety.models import Block

ALICE = "u-alice"
BOB = "u-bob"
CARLA = "u-carla"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    # The whole metadata, for the reason test_trust_safety.py gives: a file
    # that only registers the models its own imports reached passes in a full
    # run and fails on its own.
    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _block(db, blocker, blocked, reason_code=None):
    row = Block(blocker_user_id=blocker, blocked_user_id=blocked, reason_code=reason_code)
    db.add(row)
    db.commit()
    return row


# ---- blocked_pair_ids ----

def test_one_row_hides_each_of_them_from_the_other(db):
    """The row has a direction. What it does does not.

    If this ever returns the blocked id to the blocker and not the other way
    round, the person who pressed block keeps seeing the face they blocked in
    their own search results.
    """
    _block(db, ALICE, BOB)
    assert blocks.blocked_pair_ids(db, ALICE) == {BOB}
    assert blocks.blocked_pair_ids(db, BOB) == {ALICE}


def test_somebody_uninvolved_sees_nothing(db):
    _block(db, ALICE, BOB)
    assert blocks.blocked_pair_ids(db, CARLA) == set()


def test_no_blocks_is_an_empty_set_and_not_an_error(db):
    assert blocks.blocked_pair_ids(db, ALICE) == set()


def test_several_blocks_collapse_into_one_set(db):
    _block(db, ALICE, BOB)
    _block(db, CARLA, ALICE)
    assert blocks.blocked_pair_ids(db, ALICE) == {BOB, CARLA}


def test_the_caller_is_never_in_their_own_set(db):
    """A self block should be impossible at the endpoint. If one ever gets in,
    it must not hide somebody from their own listings."""
    _block(db, ALICE, ALICE)
    assert blocks.blocked_pair_ids(db, ALICE) == set()


# ---- the pair constraint ----

def test_the_same_pair_cannot_be_blocked_twice(db):
    _block(db, ALICE, BOB)
    with pytest.raises(IntegrityError):
        _block(db, ALICE, BOB)
    db.rollback()


def test_the_opposite_direction_is_a_separate_row(db):
    """Mutual blocking is two decisions, and unblocking undoes only yours."""
    _block(db, ALICE, BOB)
    _block(db, BOB, ALICE)
    assert db.query(Block).count() == 2
    assert blocks.blocked_pair_ids(db, ALICE) == {BOB}


# ---- block_between and is_blocked_pair ----

def test_is_blocked_pair_does_not_care_who_pressed_the_button(db):
    _block(db, ALICE, BOB)
    assert blocks.is_blocked_pair(db, ALICE, BOB) is True
    assert blocks.is_blocked_pair(db, BOB, ALICE) is True
    assert blocks.is_blocked_pair(db, ALICE, CARLA) is False


def test_block_between_keeps_the_direction_for_the_refusal_sentence(db):
    """The one caller that needs to know which way round it was gets it here."""
    _block(db, ALICE, BOB)
    row = blocks.block_between(db, BOB, ALICE)
    assert row is not None
    assert row.blocker_user_id == ALICE
    assert row.blocked_user_id == BOB


def test_block_between_is_none_for_strangers(db):
    assert blocks.block_between(db, ALICE, CARLA) is None


def test_reason_code_is_optional_and_kept_when_given(db):
    _block(db, ALICE, BOB, reason_code="harassment")
    _block(db, CARLA, BOB)
    rows = {r.blocker_user_id: r.reason_code for r in db.query(Block).all()}
    assert rows[ALICE] == "harassment"
    assert rows[CARLA] is None


# ---- get_optional_user_id ----

def test_a_valid_token_identifies_the_caller():
    assert get_optional_user_id(f"Bearer {create_access_token(ALICE)}") == ALICE


def test_no_header_is_a_visitor_and_not_a_refusal():
    assert get_optional_user_id(None) is None


def test_a_header_that_is_not_a_bearer_token_is_a_visitor():
    assert get_optional_user_id("Basic abc") is None


def test_a_broken_token_reads_as_anonymous_rather_than_raising():
    """The surprising half, and the deliberate one.

    These endpoints are public. A session that quietly expired in another tab
    should see the landing page, not a blank screen, because there is nothing
    behind these routes to defend. Everything that does hold something still
    uses get_current_user_id.
    """
    assert get_optional_user_id("Bearer not-a-jwt") is None


def test_the_scheme_is_matched_case_insensitively():
    assert get_optional_user_id(f"bearer {create_access_token(BOB)}") == BOB
