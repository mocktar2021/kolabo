"""Tests for Epic I country configuration (KOL-34)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.admin.router import router as admin_router
from app.modules.config.service import seed_countries


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    db = ts()
    seed_countries(db)
    db.close()

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_factory = ts
    return c


ADMIN = {"X-Admin-Id": "admin-1"}


def test_seed_populates_seven_markets(client):
    r = client.get("/admin/countries", headers=ADMIN)
    assert r.status_code == 200
    countries = r.json()
    assert len(countries) == 7
    codes = {c["code"] for c in countries}
    assert {"BJ", "TG", "CI", "GH", "SN", "CM", "NG"} == codes


def test_only_pilot_markets_enabled_by_default(client):
    enabled = client.get("/admin/countries?enabled_only=true", headers=ADMIN).json()
    assert {c["code"] for c in enabled} == {"BJ", "TG"}


def test_add_new_country_without_deploy(client):
    payload = {
        "code": "ke", "name": "Kenya", "currency": "kes",
        "phone_prefix": "+254", "mobile_money_provider": "mpesa", "enabled": True,
    }
    r = client.post("/admin/countries", json=payload, headers=ADMIN)
    assert r.status_code == 201
    body = r.json()
    # Code and currency are normalized to upper case.
    assert body["code"] == "KE" and body["currency"] == "KES"
    assert body["mobile_money_provider"] == "mpesa"
    assert client.get("/admin/countries?enabled_only=true", headers=ADMIN).json().__len__() == 3


def test_upsert_edits_existing_country(client):
    r = client.post(
        "/admin/countries",
        json={"code": "GH", "name": "Ghana", "currency": "GHS", "phone_prefix": "+233", "mobile_money_provider": "mtn_momo"},
        headers=ADMIN,
    )
    assert r.status_code == 201
    assert client.get("/admin/countries", headers=ADMIN).json().__len__() == 7  # still 7, updated not added
    gh = [c for c in client.get("/admin/countries", headers=ADMIN).json() if c["code"] == "GH"][0]
    assert gh["mobile_money_provider"] == "mtn_momo"


def test_enable_and_disable_market(client):
    assert client.post("/admin/countries/GH/enabled", json={"enabled": True}, headers=ADMIN).json()["enabled"] is True
    assert client.post("/admin/countries/GH/enabled", json={"enabled": False}, headers=ADMIN).json()["enabled"] is False


def test_enable_unknown_country_404(client):
    assert client.post("/admin/countries/ZZ/enabled", json={"enabled": True}, headers=ADMIN).status_code == 404


def test_config_writes_are_logged(client):
    client.post(
        "/admin/countries",
        json={"code": "KE", "name": "Kenya", "currency": "KES", "phone_prefix": "+254"},
        headers=ADMIN,
    )
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).filter(AdminActionLog.target_id == "KE").first()
    db.close()
    assert log is not None and log.action == "country_added"


def test_country_config_requires_admin(client):
    assert client.get("/admin/countries").status_code == 401
    assert client.post("/admin/countries", json={"code": "KE", "name": "K", "currency": "KES", "phone_prefix": "+254"}).status_code == 401
