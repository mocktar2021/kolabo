"""Whose image is it? The ownership check on every media id a profile accepts.

WHAT WAS WRONG. profiles.service took a `media_id` out of a request body,
checked that the row EXISTED, and attached it — to a portfolio, or, through the
blind `setattr` loop in upsert_influencer_profile, to an avatar. Neither path
ever compared the asset's `owner_user_id` to the caller. PR #151 made the
router take the profile owner from the bearer token instead of the path, which
settled WHOSE profile a write lands on; it could not see one layer down to WHAT
that profile points at.

AND NO ENUMERATION WAS NEEDED, which is what makes it cheap rather than
theoretical. `_portfolio_out` returns `media_id`, and both
GET /profiles/{user_id}/portfolio and GET /profiles/influencer/{user_id}/public
are unauthenticated. So the attack is three steps with no guessing in any of
them: read the victim's own public page, copy the ids out of it, post them to
your own profile. TestTheAttackEndToEnd walks exactly those three steps.

THE FIXTURE IS CALLED `auth_client`, NOT `client`, AND THAT IS LOAD-BEARING —
the same reason test_profiles_auth.py gives, and it bites harder here. The
autouse `profile_owner_from_path` fixture in backend/conftest.py keys on a
fixture named `client` and resolves the profile owner to the id in the URL.
Under that override this attack is not merely stubbed, it is INEXPRESSIBLE:
posting Alice's media to /profiles/{alice}/portfolio would make Alice the
owner of the write as well as of the image, which is a creator using her own
photograph — legitimate, and the guard would rightly not fire. Only a real
token lets the caller be Bob while the media belongs to Alice, which is the
actual shape of the theft. Rename the fixture and every test below goes green
for the wrong reason.

The real AppError handler is registered on the throwaway app, which
test_profiles_auth.py does not need to do. AppError subclasses HTTPException,
so without it FastAPI's default handler still answers with the right STATUS but
drops `code` from the body — and the code is half of what is being asserted
here, because reusing an existing translated code rather than inventing a new
one was the deliberate decision in this fix.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router

# The code both refusals reuse. It already exists in French and English in
# web/src/lib/errorMessages.ts and mobile/src/lib/errorMessages.ts — it is the
# code add_portfolio_item already raised for an id that did not resolve — so
# this fix adds no untranslated string and cannot trip test_error_codes.py or
# its frontend mirror. Written down here so that a future rename has to change
# the assertion deliberately rather than by accident.
NOT_FOUND = "profile_image_not_found"

# A one pixel JPEG header. The bytes never matter; only who owns them does.
IMAGE = b"\xff\xd8\xff"


@pytest.fixture()
def auth_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models

    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(profiles_router, prefix="/profiles")
    # The real handler, imported rather than re-declared, for the reason
    # test_error_codes.py gives: a handler that merely resembles the production
    # one is a test that stays green while the wiring is wrong. app/main.py
    # registers this same pair.
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, role="influencer"):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _media(client, user_id):
    """Upload an image AS `user_id` and hand back its id.

    Through the real endpoint rather than an INSERT, so the id under attack is
    one the platform actually minted, owner column and all. An id conjured
    straight into the table could be owned by nobody, and a guard that only
    refuses ownerless rows is not the guard this file is about.
    """
    r = client.post(
        f"/profiles/{user_id}/media",
        files={"file": ("shot.jpg", IMAGE, "image/jpeg")},
        headers=_headers(user_id),
    )
    assert r.status_code == 201
    return r.json()["id"]


class TestPortfolio:
    """The portfolio IS the sales asset on this marketplace. A creator's
    reputation is the work shown on their page, so pinning somebody else's
    work to your own storefront is not a data defect — it is the product
    working for the wrong person."""

    def test_another_creators_media_cannot_be_pinned_to_your_portfolio(self, auth_client):
        """THE ONE THAT MATTERS. Bob, holding Alice's media id, gets nothing."""
        alice = _user(auth_client, "+22990002001")
        bob = _user(auth_client, "+22990002002")
        stolen = _media(auth_client, alice)

        r = auth_client.post(
            f"/profiles/{bob}/portfolio", json={"media_id": stolen}, headers=_headers(bob)
        )
        assert r.status_code == 404
        assert r.json()["code"] == NOT_FOUND

        # Asserted on the storefront, not on the response: what matters is that
        # the image never appears on Bob's public page.
        assert auth_client.get(f"/profiles/{bob}/portfolio").json() == []

    def test_your_own_media_can_still_be_added_to_your_portfolio(self, auth_client):
        """The other half of the guard. A check that refuses everything is not
        a fix, it is an outage — creators upload their own work all day."""
        alice = _user(auth_client, "+22990002003")
        mine = _media(auth_client, alice)

        r = auth_client.post(
            f"/profiles/{alice}/portfolio", json={"media_id": mine}, headers=_headers(alice)
        )
        assert r.status_code == 201
        assert r.json()["media_id"] == mine

        listed = auth_client.get(f"/profiles/{alice}/portfolio").json()
        assert [item["media_id"] for item in listed] == [mine]

    def test_a_media_id_that_never_existed_is_still_refused(self, auth_client):
        """The EXISTENCE half of the guard, which the ownership check now shares
        a branch with. Folding the two together must not lose either one: a
        made-up id has no asset to read an owner off, and this is the test that
        goes red if that branch is dropped."""
        alice = _user(auth_client, "+22990002004")

        r = auth_client.post(
            f"/profiles/{alice}/portfolio",
            json={"media_id": "11111111-1111-1111-1111-111111111111"},
            headers=_headers(alice),
        )
        assert r.status_code == 404
        assert r.json()["code"] == NOT_FOUND


class TestAvatar:
    """The avatar is the face a brand believes it is hiring. It reached the
    column through `for field, value in data.items(): setattr(...)`, which is
    to say through nothing at all."""

    def test_another_creators_media_cannot_become_your_avatar(self, auth_client):
        alice = _user(auth_client, "+22990002010")
        bob = _user(auth_client, "+22990002011")
        stolen = _media(auth_client, alice)
        mine = _media(auth_client, bob)

        # Bob has a real profile with his own face on it first, so "unchanged"
        # below is something this test can actually read back rather than a
        # 404 for a creator who never had a profile.
        assert auth_client.put(
            f"/profiles/influencer/{bob}",
            json={"headline": "Bob", "avatar_media_id": mine},
            headers=_headers(bob),
        ).status_code == 200

        r = auth_client.put(
            f"/profiles/influencer/{bob}",
            json={"headline": "Alice", "avatar_media_id": stolen},
            headers=_headers(bob),
        )
        assert r.status_code == 404
        assert r.json()["code"] == NOT_FOUND

        # The headline rides the SAME setattr loop and was sent in the same
        # payload, so asserting it too is what proves the guard runs BEFORE any
        # of the write lands, rather than half-applying the request and then
        # refusing.
        after = auth_client.get(f"/profiles/influencer/{bob}", headers=_headers(bob)).json()
        assert after["avatar_media_id"] == mine
        assert after["headline"] == "Bob"

    def test_your_own_media_can_still_become_your_avatar(self, auth_client):
        alice = _user(auth_client, "+22990002012")
        mine = _media(auth_client, alice)

        r = auth_client.put(
            f"/profiles/influencer/{alice}",
            json={"avatar_media_id": mine},
            headers=_headers(alice),
        )
        assert r.status_code == 200
        assert r.json()["avatar_media_id"] == mine

    def test_removing_your_avatar_is_still_allowed(self, auth_client):
        """An explicit null is how a creator DELETES their photo — the upsert's
        exclude_unset contract draws its line at omission, not at emptiness.

        So the new check asks `is not None` rather than `in data`, and this is
        the test that says so. Tightened to `in data`, the guard would look up
        a media asset with id None, find nothing, and answer 404 to a creator
        trying to take their own face off their own page.
        """
        alice = _user(auth_client, "+22990002013")
        mine = _media(auth_client, alice)
        auth_client.put(
            f"/profiles/influencer/{alice}",
            json={"avatar_media_id": mine},
            headers=_headers(alice),
        )

        r = auth_client.put(
            f"/profiles/influencer/{alice}",
            json={"avatar_media_id": None},
            headers=_headers(alice),
        )
        assert r.status_code == 200
        assert r.json()["avatar_media_id"] is None


class TestTheAttackEndToEnd:
    """No token of the victim's, no enumeration, no guesswork."""

    def test_the_public_page_is_no_longer_a_shopping_list(self, auth_client):
        alice = _user(auth_client, "+22990002020")
        bob = _user(auth_client, "+22990002021")
        mine = _media(auth_client, alice)
        auth_client.put(
            f"/profiles/influencer/{alice}",
            json={"bio": "Creator", "categories": ["fashion"]},
            headers=_headers(alice),
        )
        auth_client.post(
            f"/profiles/{alice}/portfolio", json={"media_id": mine}, headers=_headers(alice)
        )

        # Step one: read the victim's storefront. Anonymous, and it stays that
        # way on purpose — a page that needs a login is not a storefront.
        page = auth_client.get(f"/profiles/influencer/{alice}/public")
        assert page.status_code == 200

        # Step two: the ids are right there in the payload. This assertion is
        # not a bug report; it is the deliberate, unchanged contract that makes
        # step three the only place a guard could ever have gone.
        harvested = [item["media_id"] for item in page.json()["portfolio"]]
        assert harvested == [mine]

        # Step three, and the only step that now fails.
        r = auth_client.post(
            f"/profiles/{bob}/portfolio",
            json={"media_id": harvested[0]},
            headers=_headers(bob),
        )
        assert r.status_code == 404
        assert r.json()["code"] == NOT_FOUND
        assert auth_client.get(f"/profiles/{bob}/portfolio").json() == []
