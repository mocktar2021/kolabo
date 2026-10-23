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


def test_seed_populates_seven_markets(client, admin_headers):
    # Seven ROWS, four of them open. A closed market keeps its row so that
    # reopening it is a config write rather than research into what its
    # currency and calling code were.
    r = client.get("/admin/countries", headers=admin_headers)
    assert r.status_code == 200
    countries = r.json()
    assert len(countries) == 7
    codes = {c["code"] for c in countries}
    assert {"BJ", "TG", "CI", "GH", "SN", "CM", "NG"} == codes


def test_four_markets_enabled_by_default(client, admin_headers):
    # The four where the payment provider can actually move money. Ghana,
    # Cameroon and Nigeria are seeded disabled because GHS, XAF and NGN sit
    # outside the XOF area the gateway's licence covers, so they were never
    # payable and offering them produced a signup that ends at a payout form
    # which cannot pay.
    #
    # The flag is kept rather than the rows being dropped, because closing and
    # reopening a market must stay a config write. See
    # test_enable_and_disable_market for the mechanism.
    enabled = client.get("/admin/countries?enabled_only=true", headers=admin_headers).json()
    assert {c["code"] for c in enabled} == {"BJ", "TG", "CI", "SN"}

    disabled = [c for c in client.get("/admin/countries", headers=admin_headers).json() if not c["enabled"]]
    assert {c["code"] for c in disabled} == {"GH", "CM", "NG"}


def test_core_config_and_seed_agree_on_open_markets():
    """app.core.country_config and this module's SEED are two independent
    country lists with nothing deriving one from the other. That is how both
    came to advertise seven open markets while the payment provider served
    four, for a month, with nothing failing. This is the guard that makes the
    next divergence fail here instead of on a signup form."""
    from app.core.country_config import get_enabled_countries
    from app.modules.config.service import SEED

    seeded_open = {row["code"] for row in SEED if row["enabled"]}
    assert seeded_open == set(get_enabled_countries())


def test_add_new_country_without_deploy(client, admin_headers):
    payload = {
        "code": "ke", "name": "Kenya", "currency": "kes",
        "phone_prefix": "+254", "mobile_money_provider": "mpesa", "enabled": True,
    }
    r = client.post("/admin/countries", json=payload, headers=admin_headers)
    assert r.status_code == 201
    body = r.json()
    # Code and currency are normalized to upper case.
    assert body["code"] == "KE" and body["currency"] == "KES"
    assert body["mobile_money_provider"] == "mpesa"
    # The four seeded open markets, plus the new one.
    assert client.get("/admin/countries?enabled_only=true", headers=admin_headers).json().__len__() == 5


def test_upsert_edits_existing_country(client, admin_headers):
    r = client.post(
        "/admin/countries",
        json={"code": "GH", "name": "Ghana", "currency": "GHS", "phone_prefix": "+233", "mobile_money_provider": "mtn_momo"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert client.get("/admin/countries", headers=admin_headers).json().__len__() == 7  # still 7, updated not added
    gh = [c for c in client.get("/admin/countries", headers=admin_headers).json() if c["code"] == "GH"][0]
    assert gh["mobile_money_provider"] == "mtn_momo"


def test_enable_and_disable_market(client, admin_headers):
    # The rollout gate is how a market is closed again, and reopened, without
    # a deploy. Ghana seeds disabled, so this walks it the other way first.
    assert client.post("/admin/countries/GH/enabled", json={"enabled": True}, headers=admin_headers).json()["enabled"] is True
    assert client.post("/admin/countries/GH/enabled", json={"enabled": False}, headers=admin_headers).json()["enabled"] is False


def test_enable_unknown_country_404(client, admin_headers):
    assert client.post("/admin/countries/ZZ/enabled", json={"enabled": True}, headers=admin_headers).status_code == 404


def test_config_writes_are_logged(client, admin_headers):
    client.post(
        "/admin/countries",
        json={"code": "KE", "name": "Kenya", "currency": "KES", "phone_prefix": "+254"},
        headers=admin_headers,
    )
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).filter(AdminActionLog.target_id == "KE").first()
    db.close()
    assert log is not None and log.action == "country_added"


def test_country_config_requires_admin(client):
    assert client.get("/admin/countries").status_code == 401
    assert client.post("/admin/countries", json={"code": "KE", "name": "K", "currency": "KES", "phone_prefix": "+254"}).status_code == 401
