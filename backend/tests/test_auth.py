"""Tests for Epic A (KOL-1): auth registration, verification, login, reset.

Account settings and the reset flow's own rules live in test_account.py. What
stays here is the pair of reset tests that were always here — the rate limit
and the happy path — kept so a regression shows up in both files.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.rewards import REFERRAL_CREDIT
from app.modules.auth import models, service
from app.modules.auth.router import router as auth_router

PHONE = "+22990000001"
PASSWORD = "strongpass1"


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # Account deletion touches models from most modules (contracts, escrows,
    # profiles, ...), so every table has to exist, not just auth's.
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
    # The REAL error handler, because the rate limit test below asserts on the
    # `code` in the body and AppError subclasses HTTPException — without this,
    # FastAPI's own handler renders {"detail": ...} alone and the assertion
    # fails on a missing key rather than on a wrong answer. `detail` keeps its
    # name, its position and its type either way, so every existing assertion
    # in this file reads the same response it always did. Same reason and same
    # registration as tests/test_admin_auth.py.
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router, prefix="/auth")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


class _RecordingSender:
    """Stands in for the SMS sender and counts what it was asked to send.

    A rate limit on a send endpoint is about MONEY, not about status codes, so
    the assertion that matters is that the refused request put nothing on the
    wire. Swapped onto the service the same way test_bio_ai.py swaps the bio
    generator: a module level name, reassigned for the duration of one test.
    """

    def __init__(self):
        self.sent = []

    def send(self, phone, message):
        self.sent.append((phone, message))


@pytest.fixture()
def sender(monkeypatch):
    spy = _RecordingSender()
    monkeypatch.setattr(service, "_sender", spy)
    return spy


def _register(client, phone=PHONE, country="BJ", role="influencer", password=PASSWORD, **extra):
    return client.post(
        "/auth/register",
        json={"phone": phone, "password": password, "country_code": country, "role": role, **extra},
    )


def _latest_code(client, phone=PHONE):
    db = client.session_factory()
    try:
        user = db.query(models.User).filter(models.User.phone == phone).first()
        challenge = (
            db.query(models.OtpChallenge)
            .filter(models.OtpChallenge.user_id == user.id)
            .order_by(models.OtpChallenge.created_at.desc())
            .first()
        )
        return challenge.code
    finally:
        db.close()


def _verified_token(client, phone=PHONE, role="influencer"):
    """Register, verify, and log in; returns a real bearer token."""
    _register(client, phone=phone, role=role)
    code = _latest_code(client, phone=phone)
    client.post("/auth/verify-otp", json={"phone": phone, "code": code})
    resp = client.post("/auth/login", json={"phone": phone, "password": PASSWORD})
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _user_id(client, phone=PHONE):
    db = client.session_factory()
    try:
        return db.query(models.User).filter(models.User.phone == phone).first().id
    finally:
        db.close()


def test_register_creates_unverified_account_and_blocks_login(client):
    assert _register(client).status_code == 201
    resp = client.post("/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert resp.status_code == 403


def test_all_seven_pilot_countries_can_register(client):
    # Product decision: registration is open in every pilot market, including
    # the five that launched disabled.
    for i, country in enumerate(["BJ", "TG", "CI", "GH", "SN", "CM", "NG"]):
        resp = _register(client, phone=f"+2299000010{i}", country=country)
        assert resp.status_code == 201, resp.text


def test_disabled_country_still_rejected(client, monkeypatch):
    """All seven countries are open now, so disable one artificially: the
    config gate is the mechanism that closes a market again, and it must
    keep rejecting registrations the day it is flipped back."""
    from app.core import country_config
    monkeypatch.setitem(
        country_config.COUNTRY_CONFIG,
        "NG",
        {**country_config.COUNTRY_CONFIG["NG"], "enabled": False},
    )
    resp = _register(client, country="NG")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Country is not available yet"


def test_invalid_role_rejected(client):
    assert _register(client, role="astronaut").status_code == 400


def test_verify_then_login_returns_token(client):
    _register(client)
    code = _latest_code(client)
    resp = client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    resp = client.post("/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_returns_stored_role_for_agency(client):
    """Regression for the Agence bug: an agency signed up, logged out, logged
    back in, and the app treated the account as a creator. The backend
    accepted and stored the "agency" role all along, but the token response
    never said which role the account had, so a fresh login had nothing to
    restore it from. Both token grants must echo the stored role."""
    _register(client, role="agency")
    code = _latest_code(client)
    verify = client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    assert verify.status_code == 200
    assert verify.json()["role"] == "agency"
    login = client.post("/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["role"] == "agency"


def test_wrong_otp_rejected(client):
    _register(client)
    resp = client.post("/auth/verify-otp", json={"phone": PHONE, "code": "000000"})
    assert resp.status_code == 401


def test_duplicate_verified_phone_blocked(client):
    _register(client)
    code = _latest_code(client)
    client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    assert _register(client).status_code == 409


def test_delete_account_with_wrong_password_403(client):
    """A bearer token is not enough to destroy an account: a stolen session
    must not be able to erase someone's livelihood."""
    token = _verified_token(client)
    r = client.request("DELETE", "/auth/me", json={"password": "not-the-password"}, headers=_auth_headers(token))
    assert r.status_code == 403
    db = client.session_factory()
    try:
        assert db.query(models.User).filter(models.User.phone == PHONE).first() is not None
    finally:
        db.close()


def test_delete_account_removes_user_and_dependents(client):
    token = _verified_token(client)
    user_id = _user_id(client)
    from app.modules.profiles.models import Package, SocialAccount
    db = client.session_factory()
    try:
        db.add(SocialAccount(user_id=user_id, platform="instagram", handle="ama", method="oauth"))
        db.add(Package(user_id=user_id, platform="instagram", deliverable_type="post",
                       title="1 IG Post", price_amount=30000, currency="XOF"))
        db.commit()
    finally:
        db.close()
    r = client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=_auth_headers(token))
    assert r.status_code == 204
    db = client.session_factory()
    try:
        assert db.query(models.User).filter(models.User.id == user_id).first() is None
        # Spot-check the children: the account leaves nothing behind.
        assert db.query(SocialAccount).filter(SocialAccount.user_id == user_id).first() is None
        assert db.query(Package).filter(Package.user_id == user_id).first() is None
    finally:
        db.close()


def test_delete_account_takes_own_credits_but_spares_the_other_half(client):
    """A credit belongs to whoever earned it. The leaving account's own rows
    go; rows where they were merely the source survive with the pointer
    cleared, because that money was earned by somebody else."""
    token = _verified_token(client)
    user_id = _user_id(client)
    _register(client, phone="+22990000071")
    other_id = _user_id(client, "+22990000071")
    db = client.session_factory()
    try:
        db.add(models.ReferralCredit(user_id=user_id, amount=2000, currency="XOF",
                                     kind="referrer", source_user_id=other_id, contract_id="contract-1"))
        db.add(models.ReferralCredit(user_id=other_id, amount=2000, currency="XOF",
                                     kind="referee", source_user_id=user_id, contract_id="contract-1"))
        db.commit()
    finally:
        db.close()

    r = client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=_auth_headers(token))
    assert r.status_code == 204
    db = client.session_factory()
    try:
        assert db.query(models.ReferralCredit).filter(models.ReferralCredit.user_id == user_id).first() is None
        survivor = db.query(models.ReferralCredit).filter(models.ReferralCredit.user_id == other_id).first()
        assert survivor is not None
        assert survivor.amount == 2000
        assert survivor.source_user_id is None
    finally:
        db.close()


def test_delete_account_with_contract_history_409(client):
    """Once a contract exists the account cannot self-delete: counterparties
    keep their contract and review history, and money trails are never
    erased. Support closes such accounts instead."""
    token = _verified_token(client)
    user_id = _user_id(client)
    from app.modules.contracts.models import Contract
    db = client.session_factory()
    try:
        db.add(Contract(campaign_id="c-1", proposal_id="p-1", business_user_id="someone-else",
                        influencer_user_id=user_id, language="fr", body="terms",
                        rate_amount=50000, rate_currency="XOF", timeline_days=7))
        db.commit()
    finally:
        db.close()
    r = client.request("DELETE", "/auth/me", json={"password": PASSWORD}, headers=_auth_headers(token))
    assert r.status_code == 409
    assert r.json()["detail"] == "Account has transaction history; contact support to close it."
    db = client.session_factory()
    try:
        assert db.query(models.User).filter(models.User.id == user_id).first() is not None
    finally:
        db.close()


def test_registration_otp_is_rate_limited_per_phone(client, sender):
    """Every registration sends an SMS and every SMS costs money.

    Re-registering an unverified number RESENDS the code, so /auth/register is
    the resend endpoint as well — and an uncapped resend is a bill a stranger
    can run up on us in a loop. Same ceiling, and the same shape, as the reset
    limit below.
    """
    for _ in range(3):
        assert _register(client).status_code == 201
    refused = _register(client)
    assert refused.status_code == 429
    assert refused.json()["code"] == "auth_otp_too_many"

    # THE HALF THAT IS ACTUALLY ABOUT THE BILL: the refusal sent nothing, and
    # wrote no fourth challenge either. Both are asserted because a future
    # _issue_otp could write the row without sending, or send without writing.
    assert len(sender.sent) == 3
    db = client.session_factory()
    try:
        assert db.query(models.OtpChallenge).count() == 3
    finally:
        db.close()


def test_a_refused_registration_does_not_rewrite_the_password(client, sender):
    """The cap is checked before the credentials are refreshed.

    Registering a phone that already has an unverified row overwrites its
    password, so a 429 that still wrote would let whoever ran the cap out take
    over a half-finished signup for free. The original password still logs in
    once the account is verified; the one the refused request carried does not.
    """
    for _ in range(3):
        _register(client)
    assert _register(client, password="attackerpass9").status_code == 429

    code = _latest_code(client)
    assert client.post("/auth/verify-otp", json={"phone": PHONE, "code": code}).status_code == 200
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": PASSWORD}
    ).status_code == 200
    assert client.post(
        "/auth/login", json={"phone": PHONE, "password": "attackerpass9"}
    ).status_code == 401


def test_the_otp_cap_is_per_phone_and_not_a_global_ceiling(client, sender):
    """Counting every registration on the platform instead of every
    registration for one number would make a single looping attacker a denial
    of service on everybody else's signup."""
    for _ in range(3):
        _register(client)
    assert _register(client).status_code == 429
    assert _register(client, phone="+22990000042").status_code == 201
    assert len(sender.sent) == 4


def test_password_reset_rate_limited_to_three_per_hour(client):
    _register(client)
    for _ in range(3):
        assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"phone": PHONE}).status_code == 429


def test_password_reset_confirm_updates_password(client):
    """Confirm now takes {phone, code, new_password} rather than a bare token.

    The reset code is a six digit OTP delivered by SMS, exactly like the
    registration code, so it is only ever resolved together with the number it
    was sent to — six digits standing alone would be a lottery anyone could
    enter. It is still read off the same password_reset_tokens row.
    """
    _register(client)
    code = _latest_code(client)
    client.post("/auth/verify-otp", json={"phone": PHONE, "code": code})
    client.post("/auth/password-reset/request", json={"phone": PHONE})

    db = client.session_factory()
    reset_code = db.query(models.PasswordResetToken).first().token
    db.close()

    resp = client.post(
        "/auth/password-reset/confirm",
        json={"phone": PHONE, "code": reset_code, "new_password": "newstrongpass2"},
    )
    assert resp.status_code == 200
    resp = client.post("/auth/login", json={"phone": PHONE, "password": "newstrongpass2"})
    assert resp.status_code == 200


def test_reset_request_for_unknown_phone_is_generic(client):
    resp = client.post("/auth/password-reset/request", json={"phone": "+22999999999"})
    assert resp.status_code == 202


def test_referral_code_stable_and_well_formed(client):
    token = _verified_token(client)
    r1 = client.get("/auth/me/referral", headers=_auth_headers(token))
    assert r1.status_code == 200
    code = r1.json()["code"]
    assert r1.json()["referred_count"] == 0
    # Minted lazily on the first call, then stable: opening the referral
    # screen twice must never hand out two different codes.
    r2 = client.get("/auth/me/referral", headers=_auth_headers(token))
    assert r2.json()["code"] == code
    # 8 chars from the ambiguity-free alphabet: no I, no O, no 0, no 1 —
    # these codes get read aloud and retyped from phone screens.
    assert len(code) == 8
    assert set(code) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


def test_referral_screen_shows_an_honest_zero_before_anything_is_earned(client):
    """A brand new code has earned nothing, and the screen says so in the
    owner's own currency rather than leaving the amount blank."""
    token = _verified_token(client)
    body = client.get("/auth/me/referral", headers=_auth_headers(token)).json()
    assert body["referred_creators"] == 0
    assert body["referred_businesses"] == 0
    assert body["credit_total"] == 0
    assert body["credit_currency"] == "XOF"
    assert body["referrals"] == []


def test_referral_endpoint_requires_auth(client):
    assert client.get("/auth/me/referral").status_code == 401


def test_register_with_valid_referral_code_links_attribution(client):
    token = _verified_token(client)
    referrer_id = _user_id(client)
    code = client.get("/auth/me/referral", headers=_auth_headers(token)).json()["code"]

    resp = _register(client, phone="+22990000055", referral_code=code)
    assert resp.status_code == 201
    db = client.session_factory()
    try:
        newcomer = db.query(models.User).filter(models.User.phone == "+22990000055").first()
        assert newcomer.referred_by_user_id == referrer_id
    finally:
        db.close()
    # The referrer sees the signup in their count.
    r = client.get("/auth/me/referral", headers=_auth_headers(token))
    assert r.json()["referred_count"] == 1


def test_register_with_garbage_referral_code_still_succeeds(client):
    """A mistyped code must never block a signup: attribution is best-effort
    and the account matters more. Well-formed but unknown codes are dropped
    silently — no error, no attribution."""
    resp = _register(client, phone="+22990000056", referral_code="ZZZZ9999")
    assert resp.status_code == 201
    db = client.session_factory()
    try:
        newcomer = db.query(models.User).filter(models.User.phone == "+22990000056").first()
        assert newcomer.referred_by_user_id is None
    finally:
        db.close()


def test_referral_report_splits_counts_and_marks_who_ordered(client):
    """One code brings in creators and buyers alike. The screen tells them
    apart, sums what the code has earned, and marks who actually ordered —
    the only status that ever paid anything."""
    token = _verified_token(client)
    referrer_id = _user_id(client)
    code = client.get("/auth/me/referral", headers=_auth_headers(token)).json()["code"]

    _register(client, phone="+22990000061", role="influencer", referral_code=code)
    _register(client, phone="+22990000062", role="business", referral_code=code)
    creator_id = _user_id(client, "+22990000061")

    # Only the creator has completed an order. The "referee" row is what says
    # so, exactly as the escrow release path writes it.
    db = client.session_factory()
    try:
        db.add(models.ReferralCredit(user_id=creator_id, amount=REFERRAL_CREDIT["XOF"], currency="XOF",
                                     kind="referee", source_user_id=referrer_id, contract_id="contract-1"))
        db.add(models.ReferralCredit(user_id=referrer_id, amount=REFERRAL_CREDIT["XOF"], currency="XOF",
                                     kind="referrer", source_user_id=creator_id, contract_id="contract-1"))
        db.commit()
    finally:
        db.close()

    body = client.get("/auth/me/referral", headers=_auth_headers(token)).json()
    assert body["referred_count"] == 2
    assert body["referred_creators"] == 1
    assert body["referred_businesses"] == 1
    # Only the referrer's own row counts towards their balance.
    assert body["credit_total"] == REFERRAL_CREDIT["XOF"]
    assert body["credit_currency"] == "XOF"
    assert {r["role"]: r["status"] for r in body["referrals"]} == {
        "influencer": "ordered",
        "business": "signed_up",
    }
    # Newest first: the business signed up second.
    assert body["referrals"][0]["role"] == "business"
    assert body["referrals"][0]["joined_at"]
