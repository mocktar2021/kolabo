"""Identity fields on the creator profile: birth date behind the 18+ gate,
gender, and languages.

Product decisions under test: creators must be adults (legal register,
child-safety item); the date of birth and gender are never public; languages
are the one public field of the three.
"""
from datetime import date, timedelta

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


def _user(client, phone="+22990000400"):
    db = client.session_factory()
    try:
        u = User(phone=phone, email=f"{phone.lstrip('+')}@kolabo.test", password_hash="x", country_code="BJ", role="influencer", is_verified=True)
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def _birthday_years_ago(years: int) -> date:
    """A birth date whose birthday falls exactly today, `years` ago."""
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # born February 29, and this year has no February 29
        return today.replace(year=today.year - years, day=28)


def _add_packages(client, uid, n=3):
    """Enough active packages to satisfy the pricing requirement, at prices
    comfortably above any floor."""
    types = ["post", "reel", "story"]
    for i in range(n):
        r = client.post(f"/profiles/{uid}/packages", json={
            "platform": "instagram", "deliverable_type": types[i % len(types)],
            "title": f"IG {types[i % len(types)]} #{i + 1}",
            "price_amount": 30000, "currency": "XOF",
        })
        assert r.status_code == 201, r.text


def test_under_18_is_rejected(client):
    uid = _user(client)
    r = client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "birth_date": _birthday_years_ago(17).isoformat(),
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "You must be at least 18 to create a creator profile."


def test_exactly_18_today_is_accepted(client):
    """A person is 18 on their 18th birthday, not the day after."""
    uid = _user(client, "+22990000401")
    dob = _birthday_years_ago(18)
    r = client.put(f"/profiles/influencer/{uid}", json={"birth_date": dob.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["birth_date"] == dob.isoformat()


def test_18_years_minus_a_day_is_still_17(client):
    """The not-yet-had-their-birthday-this-year case: the 18th birthday is
    tomorrow, so today the creator is 17 and the gate must hold."""
    uid = _user(client, "+22990000402")
    dob = _birthday_years_ago(18) + timedelta(days=1)
    assert client.put(f"/profiles/influencer/{uid}", json={"birth_date": dob.isoformat()}).status_code == 400


def test_resubmitting_cannot_bypass_a_stored_birth_date(client):
    """The gate runs on every write the field appears in: an under-18 date is
    rejected regardless of what is already stored, and the stored value
    survives the rejected write."""
    uid = _user(client, "+22990000403")
    adult = _birthday_years_ago(30)
    assert client.put(f"/profiles/influencer/{uid}", json={"birth_date": adult.isoformat()}).status_code == 200
    assert client.put(
        f"/profiles/influencer/{uid}", json={"birth_date": _birthday_years_ago(15).isoformat()}
    ).status_code == 400
    assert client.get(f"/profiles/influencer/{uid}").json()["birth_date"] == adult.isoformat()


def test_gender_is_validated_to_a_closed_set(client):
    uid = _user(client, "+22990000404")
    for value in ("female", "male", "other", "prefer_not_to_say"):
        assert client.put(f"/profiles/influencer/{uid}", json={"gender": value}).status_code == 200
    assert client.put(f"/profiles/influencer/{uid}", json={"gender": "unknown"}).status_code == 422


def test_public_payload_has_languages_but_never_birth_date_or_gender(client):
    uid = _user(client, "+22990000405")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
        "birth_date": "1995-05-14", "gender": "female", "languages": ["fr", "en"],
    })
    pub = client.get(f"/profiles/influencer/{uid}/public").json()
    assert pub["languages"] == ["fr", "en"]
    # Private means the keys do not exist on the payload at all, not that they
    # arrive null or hidden behind a flag.
    assert "birth_date" not in pub
    assert "gender" not in pub
    # The owner-facing profile still returns both, so the edit form prefills.
    own = client.get(f"/profiles/influencer/{uid}").json()
    assert own["birth_date"] == "1995-05-14"
    assert own["gender"] == "female"


def test_profile_is_not_live_without_a_birth_date(client):
    uid = _user(client, "+22990000406")
    client.put(f"/profiles/influencer/{uid}", json={"bio": "Hi", "categories": ["fashion"]})
    _add_packages(client, uid)
    s = client.get(f"/profiles/{uid}/onboarding-status").json()
    assert s["has_birth_date"] is False
    assert s["is_live"] is False
    # The birth date is the last missing piece.
    client.put(f"/profiles/influencer/{uid}", json={"birth_date": "1990-01-15"})
    s = client.get(f"/profiles/{uid}/onboarding-status").json()
    assert s["has_birth_date"] is True
    assert s["is_live"] is True
