"""AI drafted bios: guardrails, rate limit, and the bilingual split.

The generator is stubbed throughout. These tests are about the rules around
generation, not the model's prose, which cannot be asserted on.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.db import Base, get_db
from app.modules.auth.models import User
from app.modules.profiles import bio_ai, service
from app.modules.profiles.router import router as profiles_router


class StubGenerator:
    """Records what it was asked for and returns a fixed draft."""

    available = True

    def __init__(self, text="Je filme la cuisine beninoise chez moi a Cotonou."):
        self.text = text
        self.calls = []

    def generate(self, facts, language):
        self.calls.append((facts, language))
        return self.text


class FailingGenerator:
    available = True

    def generate(self, facts, language):
        return None


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
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


@pytest.fixture(autouse=True)
def restore_generator():
    original = service.bio_generator
    yield
    service.bio_generator = original


def _user(client, phone="+22990000900", country="BJ"):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code=country, role="influencer", is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def _profile(client, uid, categories=("food",), **extra):
    payload = {"display_name": "Ama", "categories": list(categories), "rate_card": {}, **extra}
    r = client.put(f"/profiles/influencer/{uid}", json=payload)
    assert r.status_code == 200, r.text


def _add_packages(client, uid, n=3):
    """Enough active packages for searchability, at floor-respecting prices."""
    types = ["post", "reel", "story"]
    for i in range(n):
        r = client.post(f"/profiles/{uid}/packages", json={
            "platform": "instagram", "deliverable_type": types[i % len(types)],
            "title": f"IG {types[i % len(types)]} #{i + 1}",
            "price_amount": 30000, "currency": "XOF",
        })
        assert r.status_code == 201, r.text


def test_generated_bio_is_a_draft_and_is_not_saved(client):
    service.bio_generator = StubGenerator()
    uid = _user(client)
    _profile(client, uid)

    r = client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"})
    assert r.status_code == 200, r.text
    assert r.json()["saved"] is False
    assert r.json()["bio"]

    # The profile itself is untouched until the creator saves it.
    assert client.get(f"/profiles/influencer/{uid}").json()["bio_fr"] is None


def test_generation_needs_categories(client):
    """A bio built from a name alone describes any creator, not this one."""
    service.bio_generator = StubGenerator()
    uid = _user(client, "+22990000901")
    _profile(client, uid, categories=())

    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 400


def test_generation_is_unavailable_without_credentials(client):
    service.bio_generator = bio_ai.NoopBioGenerator()
    uid = _user(client, "+22990000902")
    _profile(client, uid)

    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 503


def test_provider_failure_does_not_block_onboarding(client):
    service.bio_generator = FailingGenerator()
    uid = _user(client, "+22990000903")
    _profile(client, uid)

    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 502
    # And the creator can still write their own.
    _profile(client, uid, bio_fr="Ecrit a la main.")
    assert client.get(f"/profiles/influencer/{uid}").json()["bio_fr"] == "Ecrit a la main."


def test_failed_generation_is_not_counted_against_the_limit(client):
    service.bio_generator = FailingGenerator()
    uid = _user(client, "+22990000904")
    _profile(client, uid)
    client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"})

    service.bio_generator = StubGenerator()
    r = client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"})
    assert r.json()["generations_remaining"] == settings.bio_generation_limit - 1


def test_regeneration_is_capped(client, monkeypatch):
    monkeypatch.setattr(settings, "bio_generation_limit", 2)
    service.bio_generator = StubGenerator()
    uid = _user(client, "+22990000905")
    _profile(client, uid)

    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 200
    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 200
    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "fr"}).status_code == 429


def test_language_must_be_fr_or_en(client):
    service.bio_generator = StubGenerator()
    uid = _user(client, "+22990000906")
    _profile(client, uid)

    assert client.post(f"/profiles/{uid}/bio/generate", json={"language": "es"}).status_code == 422


def test_only_known_facts_reach_the_model(client):
    """Whatever the model does with them, it may only ever see these keys."""
    stub = StubGenerator()
    service.bio_generator = stub
    uid = _user(client, "+22990000907")
    _profile(client, uid, location="Cotonou")

    client.post(f"/profiles/{uid}/bio/generate", json={"language": "en"})
    facts, language = stub.calls[0]
    assert language == "en"
    assert set(facts) <= {"display_name", "location", "categories", "platforms", "recent_titles"}


def test_public_profile_prefers_the_viewers_language(client):
    uid = _user(client, "+22990000908")
    _profile(client, uid, rate_card={"post": 1}, bio_fr="Bonjour", bio_en="Hello")

    assert client.get(f"/profiles/influencer/{uid}/public?language=en").json()["bio"] == "Hello"
    assert client.get(f"/profiles/influencer/{uid}/public?language=fr").json()["bio"] == "Bonjour"


def test_public_profile_falls_back_to_the_other_language(client):
    """Showing a French bio to an English viewer beats showing nothing."""
    uid = _user(client, "+22990000909")
    _profile(client, uid, rate_card={"post": 1}, bio_fr="Bonjour")

    assert client.get(f"/profiles/influencer/{uid}/public?language=en").json()["bio"] == "Bonjour"


def test_either_language_completes_the_profile(client):
    uid = _user(client, "+22990000910")
    _profile(client, uid, bio_en="Hello")
    # Searchable now also takes the package storefront; the bio in a single
    # language must still count as "has a bio".
    _add_packages(client, uid)

    assert client.get(f"/profiles/influencer/{uid}").json()["is_searchable"] is True


def test_prompt_forbids_numbers_and_invented_brands():
    """The two failure modes that matter are pinned to the prompt itself, so
    nobody edits them away without a test turning red."""
    prompt = bio_ai.SYSTEM_PROMPT.lower()
    assert "invent nothing" in prompt
    assert "never state follower counts" in prompt
    assert "collaboration unless it appears" in prompt


def test_has_enough_facts_requires_more_than_a_name():
    assert bio_ai.has_enough_facts({"display_name": "Ama"}) is False
    assert bio_ai.has_enough_facts({"categories": ["food"]}) is True
