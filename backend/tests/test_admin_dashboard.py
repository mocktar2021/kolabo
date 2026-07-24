"""Tests for the Epic I admin dashboard (KOL-33)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.modules.admin.models import AdminActionLog
from app.modules.payments import models as pay
from app.modules.profiles import models as profiles
from app.modules.trust_safety import models as ts_models
from app.modules.admin.router import router as admin_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

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


def test_dashboard_requires_admin(client):
    assert client.get("/admin/dashboard").status_code == 401


def test_empty_dashboard_is_all_zeros(client):
    d = client.get("/admin/dashboard", headers=ADMIN).json()
    assert d["verification"]["pending_documents"] == 0
    assert d["disputes"]["open"] == 0
    assert d["payouts"]["held"] == 0
    assert d["reports"]["open"] == 0
    assert d["recent_actions"] == []


def test_dashboard_counts_across_queues(client):
    db = client.session_factory()
    # One pending verification document.
    db.add(profiles.VerificationDocument(user_id="u1", doc_type="identity", filename="id.png", ciphertext=b"x", status=profiles.PENDING))
    # One disputed and one held (past due) escrow.
    past = pay.utcnow().replace(year=2020)
    db.add(pay.Escrow(contract_id="c1", campaign_id="camp1", business_user_id="b", influencer_user_id="i",
                      amount=1000, currency="XOF", provider="mock", provider_fund_ref="f", status=pay.DISPUTED,
                      held_at=pay.utcnow(), due_release_at=pay.utcnow()))
    db.add(pay.Escrow(contract_id="c2", campaign_id="camp2", business_user_id="b", influencer_user_id="i",
                      amount=2000, currency="XOF", provider="mock", provider_fund_ref="f2", status=pay.HELD,
                      held_at=pay.utcnow(), due_release_at=past))
    # One open report.
    db.add(ts_models.Report(reporter_user_id="r", target_type="user", target_id="u9", reason_code="fraud", status=ts_models.OPEN))
    # One logged admin action.
    db.add(AdminActionLog(admin_id="admin-1", action="document_approved", target_type="verification_document", target_id="d1", reason=None))
    db.commit(); db.close()

    d = client.get("/admin/dashboard", headers=ADMIN).json()
    assert d["verification"]["pending_documents"] == 1
    assert d["disputes"]["open"] == 1
    assert d["payouts"]["held"] == 1
    assert d["payouts"]["due_for_release"] == 1
    assert d["reports"]["open"] == 1
    assert len(d["recent_actions"]) == 1
    assert d["recent_actions"][0]["action"] == "document_approved"
