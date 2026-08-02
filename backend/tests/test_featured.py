"""Tests for GET /discovery/featured: the landing page strip.

Three things it has to get right:

  1. Only searchable creators appear — the SAME rule search uses, not a
     second one. A half-finished profile on the landing page is the worst
     first impression the platform can make, and a creator visible here but
     missing from search is a bug nobody reports because each screen looks
     fine on its own.
  2. The limit is respected.
  3. It actually varies. That is the whole reason the endpoint exists.

HOW THE RANDOMNESS IS TESTED WITHOUT A FLAKY TEST. Observing randomness is
inherently probabilistic, so the load-bearing assertion is not made against
random output at all: _random_order is a named function returning the ordering
expression, and the test swaps it for a FIXED ordering and asserts the results
come back in that order. If the query ever stopped using it — an accidental
ORDER BY created_at, a shuffle moved into Python, an ordering dropped
altogether — that test fails every single time, deterministically. The
sampling test below it is a second opinion with its false-failure probability
written down, not the primary evidence.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.auth.models import User
from app.modules.discovery import featured
from app.modules.discovery.router import router as discovery_router
from app.modules.profiles import models as pmodels


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(discovery_router, prefix="/discovery")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = testing_session
    return c


def _ig_packages(user_id, prices=(30000, 40000, 50000)):
    """Three active Instagram packages: the storefront a profile needs to be
    searchable (MIN_LIVE_PACKAGES), same as in test_discovery."""
    deliverables = ("post", "reel", "story")
    return [
        pmodels.Package(
            user_id=user_id, platform="instagram", deliverable_type=deliverables[i % 3],
            title=f"1 IG {deliverables[i % 3]}", price_amount=price, currency="XOF", is_active=True,
        )
        for i, price in enumerate(prices)
    ]


def _creator(client, phone, display_name, searchable=True, categories=("fashion",)):
    """A creator who is on the board, or one who is deliberately not.

    An unsearchable one here is missing its packages, which is the commonest
    real shape of a half-finished profile.
    """
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code="BJ",
                    role="influencer", is_verified=True)
        db.add(user); db.commit(); db.refresh(user)
        db.add(pmodels.InfluencerProfile(
            user_id=user.id, bio="Creator", categories=list(categories),
            rate_card={}, follower_count=5000, display_name=display_name,
        ))
        if searchable:
            db.add_all(_ig_packages(user.id))
        db.commit()
        return user.id
    finally:
        db.close()


def _names(rows):
    return [row["display_name"] for row in rows]


def test_only_searchable_creators_appear(client):
    """The same rule search runs on, called rather than restated: a profile
    with no storefront is not ready to be the first thing a brand sees."""
    _creator(client, "+22990070001", "Ready")
    _creator(client, "+22990070002", "No packages", searchable=False)

    rows = client.get("/discovery/featured").json()
    assert _names(rows) == ["Ready"]


def test_a_profile_with_no_bio_or_no_category_is_not_featured(client):
    """The other two halves of the same rule."""
    uid = _creator(client, "+22990070010", "No bio")
    db = client.session_factory()
    prof = db.query(pmodels.InfluencerProfile).filter(
        pmodels.InfluencerProfile.user_id == uid
    ).first()
    prof.bio = None
    db.commit(); db.close()
    assert client.get("/discovery/featured").json() == []

    other = _creator(client, "+22990070011", "No category")
    db = client.session_factory()
    prof = db.query(pmodels.InfluencerProfile).filter(
        pmodels.InfluencerProfile.user_id == other
    ).first()
    prof.categories = []
    db.commit(); db.close()
    assert client.get("/discovery/featured").json() == []


def test_the_limit_is_respected(client):
    for i in range(6):
        _creator(client, f"+2299007010{i}", f"Creator {i}")

    assert len(client.get("/discovery/featured", params={"limit": 3}).json()) == 3
    # And the default is the strip size, not everything.
    assert len(client.get("/discovery/featured").json()) == 6


def test_the_default_limit_is_the_strip_size(client):
    for i in range(10):
        _creator(client, f"+2299007020{i}", f"Creator {i}")
    rows = client.get("/discovery/featured").json()
    assert len(rows) == featured.DEFAULT_FEATURED_LIMIT


def test_an_absurd_limit_is_clamped_rather_than_refused(client):
    """A stale client asking for a thousand gets the cap, not an error page
    where the creators were supposed to be."""
    for i in range(3):
        _creator(client, f"+2299007030{i}", f"Creator {i}")
    r = client.get("/discovery/featured", params={"limit": 100000})
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_fewer_creators_than_the_limit_is_not_an_error(client):
    _creator(client, "+22990070400", "Only one")
    assert len(client.get("/discovery/featured", params={"limit": 8}).json()) == 1


def test_an_empty_roster_returns_an_empty_list(client):
    assert client.get("/discovery/featured").json() == []


def test_the_ordering_comes_from_the_named_random_helper(client, monkeypatch):
    """THE DETERMINISTIC ASSERTION, and the one that matters.

    _random_order is swapped for a FIXED ordering — by display name — and the
    results must come back in exactly that order. Nothing here observes
    randomness, so nothing here can flake: if the query ever stopped taking
    its ordering from that function (an accidental ORDER BY created_at, a
    shuffle moved into Python, an ordering dropped entirely) this fails on
    every run rather than one in a hundred.

    The call counter is part of it: the expression has to be asked for once
    per request, which is what proves the ordering is applied by the database
    on every call rather than computed once at import and reused.
    """
    for name, phone in (("Charlie", "+22990070501"), ("Alice", "+22990070502"),
                        ("Bob", "+22990070503")):
        _creator(client, phone, name)

    calls = []

    def fixed_order():
        calls.append(1)
        return pmodels.InfluencerProfile.display_name.asc()

    monkeypatch.setattr(featured, "_random_order", fixed_order)

    rows = client.get("/discovery/featured").json()
    assert _names(rows) == ["Alice", "Bob", "Charlie"]
    assert len(calls) == 1

    client.get("/discovery/featured")
    assert len(calls) == 2


def test_the_selection_is_not_always_identical(client):
    """The second opinion: with the real ordering in place, the strip changes.

    Twelve creators, four at a time, twenty calls. If the ordering were
    deterministic every call would return the same four in the same order and
    this fails immediately. If it is genuinely random, the chance of twenty
    identical results is roughly (1/11880) ** 19 — there are 12*11*10*9 =
    11880 ordered selections of four from twelve — which is a number with
    about eighty zeros after the decimal point. It is not a probability worth
    calling flaky, and the test above is what actually pins the behaviour
    down; this one is here because it exercises the real func.random() path
    that the deterministic test necessarily replaces.
    """
    for i in range(12):
        _creator(client, f"+229900706{i:02d}", f"Creator {i:02d}")

    seen = {
        tuple(_names(client.get("/discovery/featured", params={"limit": 4}).json()))
        for _ in range(20)
    }
    assert len(seen) > 1
    # Every call still returned a full, valid strip — varying must not mean
    # sometimes returning fewer.
    assert all(len(selection) == 4 for selection in seen)


def test_the_card_is_the_same_shape_as_a_search_result(client):
    """Reused rather than copied. A copy is how a field gets added to search
    and quietly goes missing from the landing page."""
    uid = _creator(client, "+22990070700", "Ama K.")
    db = client.session_factory()
    db.add(pmodels.SocialAccount(
        user_id=uid, platform="tiktok", handle="ama", method="oauth",
        status="verified", follower_count=9000,
    ))
    db.commit(); db.close()

    featured_row = client.get("/discovery/featured").json()[0]
    search_row = client.get("/discovery/search").json()[0]
    assert featured_row.keys() == search_row.keys()
    assert featured_row == search_row
    # The card is populated, not a shell: the strip is where a brand forms
    # its first impression of the roster.
    assert featured_row["display_name"] == "Ama K."
    assert featured_row["starting_price_amount"] == 30000
    assert featured_row["socials"][0]["platform"] == "tiktok"


def test_featured_is_public(client):
    """Same as search: a creator's storefront exists to be found, and a
    landing page behind a login would mean a brand has to sign up before it
    can see whether anybody is on the platform."""
    _creator(client, "+22990070800", "Ama K.")
    r = client.get("/discovery/featured")
    assert r.status_code == 200
    assert len(r.json()) == 1
