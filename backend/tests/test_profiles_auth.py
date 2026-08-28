"""The profiles router's guard: who a write actually lands on.

WHY THIS FILE EXISTS SEPARATELY. Every other test of this router is about what
a profile DOES — packages, portfolios, onboarding readiness, enrichment — and
each of those runs with `profile_owner` overridden to the id in the path (see
backend/conftest.py). This file is the one place the real dependency runs, and
the only thing it asks about is identity.

THE FIXTURE IS CALLED `auth_client`, NOT `client`, AND THAT IS LOAD-BEARING.
The autouse override in conftest keys on a fixture named `client`; naming this
one differently is what lets the guard actually fire here. Rename it and every
test below passes for the wrong reason, which is the worst kind of green.

What was wrong before: seventeen endpoints, no authentication of any kind. An
anonymous request could rewrite any creator's profile and their PACKAGE PRICES
— the number a brand pays at checkout — and could file an identity document
against somebody else's account.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


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
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, role="influencer"):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


PROFILE = {"bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100}}
PACKAGE = {
    "platform": "instagram",
    "deliverable_type": "post",
    "title": "1 IG post",
    "price_amount": 30000,
    "currency": "XOF",
}


class TestNoTokenIsRefused:
    def test_profile_write_is_refused(self, auth_client):
        uid = _user(auth_client, "+22990001001")
        assert auth_client.put(f"/profiles/influencer/{uid}", json=PROFILE).status_code == 401

    def test_package_create_is_refused(self, auth_client):
        """THE ONE THAT MATTERS. A package price is what a brand pays."""
        uid = _user(auth_client, "+22990001002")
        assert auth_client.post(f"/profiles/{uid}/packages", json=PACKAGE).status_code == 401

    def test_verification_document_upload_is_refused(self, auth_client):
        uid = _user(auth_client, "+22990001003")
        r = auth_client.post(
            f"/profiles/{uid}/verification-documents",
            data={"doc_type": "id_card"},
            files={"file": ("id.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        assert r.status_code == 401

    def test_social_connect_is_refused(self, auth_client):
        uid = _user(auth_client, "+22990001004")
        r = auth_client.post(
            f"/profiles/{uid}/social-accounts",
            json={"platform": "tiktok", "handle": "ama", "method": "manual", "proof_url": "https://p"},
        )
        assert r.status_code == 401

    def test_a_garbage_token_is_refused_too(self, auth_client):
        """401 for an unreadable token, not 500 and not a silent pass."""
        uid = _user(auth_client, "+22990001005")
        r = auth_client.put(
            f"/profiles/influencer/{uid}",
            json=PROFILE,
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert r.status_code == 401


class TestTheTokenDecidesWhoIsWrittenTo:
    def test_the_path_id_is_ignored_entirely(self, auth_client):
        """Bob, posting at Alice's URL, edits BOB.

        This is the whole design: cross-user writes are not refused, they are
        unrepresentable. A comparison can be forgotten on a new endpoint; an id
        that is never read cannot be spoofed on any of them.
        """
        alice = _user(auth_client, "+22990001010")
        bob = _user(auth_client, "+22990001011")

        r = auth_client.put(
            f"/profiles/influencer/{alice}",
            json={"bio": "Bob was here", "categories": [], "rate_card": {}},
            headers=_headers(bob),
        )
        assert r.status_code == 200

        # Alice is untouched. Read each profile as its owner.
        alice_bio = auth_client.get(f"/profiles/influencer/{alice}", headers=_headers(alice)).json()["bio"]
        bob_bio = auth_client.get(f"/profiles/influencer/{bob}", headers=_headers(bob)).json()["bio"]
        assert alice_bio != "Bob was here"
        assert bob_bio == "Bob was here"

    def test_a_creator_cannot_reprice_another_creators_package(self, auth_client):
        """The money case, end to end.

        Alice lists a package at 30,000. Bob tries to move it. The service's
        own ownership check answers, because the id it receives is Bob's.
        """
        alice = _user(auth_client, "+22990001012")
        bob = _user(auth_client, "+22990001013")
        created = auth_client.post(
            f"/profiles/{alice}/packages", json=PACKAGE, headers=_headers(alice)
        )
        assert created.status_code == 201
        package_id = created.json()["id"]

        attack = auth_client.put(
            f"/profiles/{alice}/packages/{package_id}",
            json={**PACKAGE, "price_amount": 1},
            headers=_headers(bob),
        )
        assert attack.status_code == 403

        still = auth_client.get(f"/profiles/{alice}/packages").json()
        assert still[0]["price_amount"] == 30000

    def test_a_document_lands_on_the_uploaders_account(self, auth_client):
        """Filing an ID against somebody else was the worst of the old holes."""
        alice = _user(auth_client, "+22990001014")
        bob = _user(auth_client, "+22990001015")
        r = auth_client.post(
            f"/profiles/{alice}/verification-documents",
            data={"doc_type": "id_card"},
            files={"file": ("id.jpg", b"\xff\xd8\xff", "image/jpeg")},
            headers=_headers(bob),
        )
        assert r.status_code == 201

        # Asserted against the row, not the response body: what matters is
        # whose account the document is filed under, and the output schema is
        # not the authority on that.
        from app.modules.profiles.models import VerificationDocument

        db = auth_client.session_factory()
        try:
            docs = db.query(VerificationDocument).all()
            assert len(docs) == 1
            assert docs[0].user_id == bob
        finally:
            db.close()


class TestWhatStaysPublic:
    """The storefront. A token here would mean a brand had to sign up before it
    could look at anybody, which is the opposite of the funnel."""

    def test_public_profile_needs_no_token(self, auth_client):
        uid = _user(auth_client, "+22990001020")
        auth_client.put(f"/profiles/influencer/{uid}", json=PROFILE, headers=_headers(uid))
        assert auth_client.get(f"/profiles/influencer/{uid}/public").status_code == 200

    def test_package_list_needs_no_token(self, auth_client):
        uid = _user(auth_client, "+22990001021")
        auth_client.post(f"/profiles/{uid}/packages", json=PACKAGE, headers=_headers(uid))
        listed = auth_client.get(f"/profiles/{uid}/packages")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

    def test_portfolio_and_socials_need_no_token(self, auth_client):
        uid = _user(auth_client, "+22990001022")
        assert auth_client.get(f"/profiles/{uid}/portfolio").status_code == 200
        assert auth_client.get(f"/profiles/{uid}/social-accounts").status_code == 200

    def test_onboarding_status_is_not_public(self, auth_client):
        """The exception among the reads: a private checklist about an account,
        not something a visitor is shown."""
        uid = _user(auth_client, "+22990001023")
        assert auth_client.get(f"/profiles/{uid}/onboarding-status").status_code == 401
        assert auth_client.get(
            f"/profiles/{uid}/onboarding-status", headers=_headers(uid)
        ).status_code == 200
