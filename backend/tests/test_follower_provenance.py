"""Where a follower number came from, and who is allowed to correct it.

social_accounts.follower_count is a number a brand reads before it decides
what to spend, and nothing used to record who supplied it: a figure the
creator typed and a figure the platform's API stated were the same column with
the same weight. Worse, _apply_enrichment refused to touch a count that was
already there, so the platform's real number was fetched over the network and
thrown away — the one path that knows the truth was the only one forbidden
from correcting an inflated claim.

These tests pin both halves: the stamping, and the overwrite that makes the
stamping worth anything. If someone restores the old `is None` guard,
test_enrichment_overwrites_a_self_reported_count_and_stamps_the_platform is
the one that goes red.

NO NETWORK. The enricher is a fake object, the same treatment
test_enrichment.py gives httpx.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


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


def _user(client, phone):
    db = client.session_factory()
    try:
        u = User(phone=phone, password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


class FakeEnricher:
    """A platform that answers, without a socket in sight."""

    def __init__(self, data):
        self.data = data

    def fetch(self, platform, handle):
        return dict(self.data)


def _platform_says(monkeypatch, **data):
    """Point the service's enricher at a canned platform response.

    Patches the module attribute the service reads, exactly as
    test_profiles_onboarding.py does — the enricher is chosen at import time
    from credentials, and the test suite configures none, so without this the
    NoopEnricher answers nothing.
    """
    from app.modules.profiles import service as psvc

    monkeypatch.setattr(psvc, "social_enricher", FakeEnricher(data))


def _connect(client, uid, **overrides):
    """Connect a YouTube account, the platform whose enricher needs only an
    API key and so the one this feature ships behind first."""
    body = {
        "platform": "youtube",
        "handle": "ama",
        "method": "manual",
        "proof_url": "https://youtube.com/@ama",
    }
    body.update(overrides)
    r = client.post(f"/profiles/{uid}/social-accounts", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_connect_with_a_typed_count_is_stamped_self_reported_and_undated(client):
    """A number out of a form is the creator's word and is labelled as such.

    No date, because nothing has verified it: follower_verified_at is reserved
    for the platform, and an undated claim must not be able to borrow the
    appearance of a checked one.
    """
    uid = _user(client, "+22990000070")
    account = _connect(client, uid, follower_count=12000)
    assert account["follower_count"] == 12000
    assert account["follower_source"] == "self_reported"
    assert account["follower_verified_at"] is None


def test_enrichment_overwrites_a_self_reported_count_and_stamps_the_platform(client, monkeypatch):
    """THE REGRESSION GUARD FOR THIS WHOLE CHANGE.

    The creator claims a million followers; YouTube says 4,321. The platform's
    number must land in the column and be stamped platform_api with a date.

    Restore the old `if account is not None and account.follower_count is
    None:` guard in _apply_enrichment and this test fails on the first
    assertion: the inflated claim survives untouched and the provenance still
    reads self_reported, which is precisely the state the old code made
    permanent — the honest path could fetch the truth but never write it.
    """
    _platform_says(monkeypatch, follower_count=4321)
    uid = _user(client, "+22990000071")
    account = _connect(client, uid, follower_count=1000000)

    assert account["follower_count"] == 4321, "the platform's number must replace the creator's claim"
    assert account["follower_source"] == "platform_api"
    assert account["follower_verified_at"] is not None
    # A real timestamp, not a truthy placeholder.
    datetime.fromisoformat(account["follower_verified_at"])
    assert account["enriched"] is True

    # And it is what was stored, not only what the create response said.
    listed = client.get(f"/profiles/{uid}/social-accounts").json()
    assert listed[0]["follower_count"] == 4321
    assert listed[0]["follower_source"] == "platform_api"


def test_enrichment_fills_an_absent_count_and_stamps_the_platform(client, monkeypatch):
    """The case the old guard did allow still works, and now says where the
    number came from. The profile-level total, which was empty, takes it as a
    fallback — see the next test for why that is the only case where it does.
    """
    _platform_says(monkeypatch, follower_count=8800)
    uid = _user(client, "+22990000072")
    account = _connect(client, uid)

    assert account["follower_count"] == 8800
    assert account["follower_source"] == "platform_api"
    assert account["follower_verified_at"] is not None
    # No total was recorded, so the platform's number backfills it.
    assert client.get(f"/profiles/influencer/{uid}").json()["follower_count"] == 8800


def test_editing_the_count_demotes_platform_verification_to_self_reported(client, monkeypatch):
    """A creator may overwrite the platform's number — and loses the badge for
    it. Otherwise the exploit is trivial: connect, collect a genuine
    platform_api stamp, then type a bigger number and keep the verification
    sitting beside it. Mirrors the rule that a changed handle demotes a
    VERIFIED account back to pending.
    """
    _platform_says(monkeypatch, follower_count=4321)
    uid = _user(client, "+22990000073")
    account = _connect(client, uid)
    assert account["follower_source"] == "platform_api"

    r = client.put(f"/profiles/{uid}/social-accounts/{account['id']}", json={"follower_count": 999999})
    assert r.status_code == 200, r.text
    assert r.json()["follower_count"] == 999999
    assert r.json()["follower_source"] == "self_reported", "an edited number is the creator's word again"
    assert r.json()["follower_verified_at"] is None, "the platform never confirmed this figure"


def test_resubmitting_the_same_count_keeps_the_platform_stamp(client, monkeypatch):
    """Only a CHANGE demotes. A form that PUTs every field it renders sends the
    number back unchanged on every save, and the platform's confirmation still
    describes exactly the figure on show, so it survives.
    """
    _platform_says(monkeypatch, follower_count=4321)
    uid = _user(client, "+22990000074")
    account = _connect(client, uid)
    verified_at = account["follower_verified_at"]

    r = client.put(f"/profiles/{uid}/social-accounts/{account['id']}", json={"follower_count": 4321})
    assert r.status_code == 200
    assert r.json()["follower_source"] == "platform_api"
    assert r.json()["follower_verified_at"] == verified_at


def test_profile_total_is_not_overwritten_by_one_platforms_count(client, monkeypatch):
    """influencer_profiles.follower_count is a CROSS-PLATFORM TOTAL and keeps
    its no-overwrite guard on purpose.

    A creator with 250,000 across every platform connects one YouTube channel
    with 4,321 subscribers. Letting that single number win would not correct
    the total, it would delete it — and it would do so differently depending on
    which account happened to enrich last.
    """
    _platform_says(monkeypatch, follower_count=4321)
    uid = _user(client, "+22990000075")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {}, "follower_count": 250000,
    })
    account = _connect(client, uid)

    # The per-platform number is corrected...
    assert account["follower_count"] == 4321
    # ...and the total the creator stated is left exactly alone.
    assert client.get(f"/profiles/influencer/{uid}").json()["follower_count"] == 250000


def test_account_with_no_count_has_no_provenance_at_all(client):
    """Null count, null source: "no number recorded", never "a report of
    nothing". Both the creator who left the field blank and the platform that
    publishes no metric land here — WhatsApp Status has no public audience, so
    a number supplied for it is discarded, and there is then nothing to
    attribute.
    """
    uid = _user(client, "+22990000076")
    blank = _connect(client, uid)
    assert blank["follower_count"] is None
    assert blank["follower_source"] is None
    assert blank["follower_verified_at"] is None

    whatsapp = _connect(
        client, uid, platform="whatsapp", handle="ama", proof_url="https://p", follower_count=5000,
    )
    assert whatsapp["follower_count"] is None
    assert whatsapp["follower_source"] is None, "a discarded number leaves nothing to attribute"
    assert whatsapp["follower_verified_at"] is None


def test_public_profile_carries_the_provenance_with_the_number(client):
    """The storefront is where the number is actually read before money moves,
    so it is the page that most needs to be able to say "self-reported"."""
    uid = _user(client, "+22990000077")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    _connect(client, uid, follower_count=4200)

    social = client.get(f"/profiles/influencer/{uid}/public").json()["social_accounts"]
    assert len(social) == 1
    assert social[0]["follower_count"] == 4200
    assert social[0]["follower_source"] == "self_reported"
    assert social[0]["follower_verified_at"] is None
