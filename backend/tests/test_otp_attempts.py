"""The guess allowance on six digit codes.

Tested against the service functions rather than through the router, on
purpose: what changed is the arithmetic of a wrong guess, and going through
HTTP would drag in registration, country config and the OTP delivery stub
without testing one extra thing about the allowance.

WHAT WAS WRONG. A wrong code raised and did nothing else — it did not count,
and it did not consume the challenge. There is no rate limiting anywhere in
this application (main.py adds exactly one middleware and it is CORS), so a
script could spend the whole ten minute life of a code guessing it, in
parallel, for free. Six digits is a million values; ten minutes of unmetered
parallel guessing is not a million values. The same machinery backs password
reset, where spending a code changes the password — takeover, not nuisance.
"""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.errors import AppError
from app.modules.auth import account, otp
from app.modules.auth import service as auth_service
from app.modules.auth.models import OtpChallenge, PasswordResetToken, User, utcnow
from app.modules.auth.schemas import PasswordResetConfirm, VerifyOtpRequest

PHONE = "+22990009001"
GOOD = "123456"
BAD = "000000"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models

    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _user(db, phone=PHONE):
    user = User(
        phone=phone, password_hash="x", country_code="BJ", role="influencer", is_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _challenge(db, user, code=GOOD, minutes=10):
    row = OtpChallenge(
        user_id=user.id, code=code, expires_at=utcnow() + timedelta(minutes=minutes)
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _reset_token(db, user, code=GOOD, minutes=15):
    row = PasswordResetToken(
        user_id=user.id, token=code, expires_at=utcnow() + timedelta(minutes=minutes)
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _guess(db, phone=PHONE, code=BAD):
    with pytest.raises(AppError) as exc:
        auth_service.verify_otp(db, VerifyOtpRequest(phone=phone, code=code))
    return getattr(exc.value, "code", None)


def _reset_guess(db, phone=PHONE, code=BAD):
    with pytest.raises(AppError) as exc:
        account.confirm_password_reset(
            db, PasswordResetConfirm(phone=phone, code=code, new_password="newpassword1")
        )
    return getattr(exc.value, "code", None)


class TestVerificationAllowance:
    def test_a_wrong_guess_is_counted(self, db):
        user = _user(db)
        challenge = _challenge(db, user)
        assert _guess(db) == "auth_code_invalid"
        db.refresh(challenge)
        assert challenge.attempts == 1
        assert challenge.consumed is False

    def test_the_allowance_runs_out_and_spends_the_code(self, db):
        user = _user(db)
        challenge = _challenge(db, user)
        for _ in range(otp.MAX_ATTEMPTS):
            assert _guess(db) == "auth_code_invalid"
        db.refresh(challenge)
        assert challenge.attempts == otp.MAX_ATTEMPTS
        assert challenge.consumed is True

    def test_the_real_code_stops_working_once_the_allowance_is_gone(self, db):
        """The point of the whole change: a spent challenge is spent."""
        user = _user(db)
        _challenge(db, user)
        for _ in range(otp.MAX_ATTEMPTS):
            _guess(db)
        # No live challenge left, so the caller is told to ask for a new code —
        # which is the honest instruction, and reveals nothing about why.
        assert _guess(db, code=GOOD) == "auth_code_expired"
        db.refresh(user)
        assert user.is_verified is False

    def test_a_near_miss_still_lets_the_real_code_through(self, db):
        """Four fumbles must not lock out somebody reading off a lock screen."""
        user = _user(db)
        _challenge(db, user)
        for _ in range(otp.MAX_ATTEMPTS - 1):
            _guess(db)
        result = auth_service.verify_otp(db, VerifyOtpRequest(phone=PHONE, code=GOOD))
        assert result["access_token"]
        db.refresh(user)
        assert user.is_verified is True

    def test_guesses_are_charged_across_every_live_code(self, db):
        """THE LOOPHOLE THIS CLOSES.

        verify_otp always resolves against the NEWEST unconsumed challenge, and
        the per-hour cap positively allows several in flight. Counting only the
        row being tried would mean the allowance reset every time an older code
        became current again — three codes would buy three times the guesses.
        """
        user = _user(db)
        older = _challenge(db, user, code="111111")
        newer = _challenge(db, user, code="222222")
        for _ in range(otp.MAX_ATTEMPTS):
            _guess(db)
        db.refresh(older)
        db.refresh(newer)
        assert older.consumed is True and newer.consumed is True
        # And the older one is genuinely dead, not merely shadowed.
        assert _guess(db, code="111111") == "auth_code_expired"


class TestResetAllowance:
    def test_a_wrong_reset_guess_is_counted(self, db):
        user = _user(db)
        token = _reset_token(db, user)
        assert _reset_guess(db) == "auth_reset_code_invalid"
        db.refresh(token)
        assert token.attempts == 1
        assert token.consumed is False

    def test_the_allowance_runs_out_and_spends_the_reset_code(self, db):
        user = _user(db)
        token = _reset_token(db, user)
        for _ in range(otp.MAX_ATTEMPTS):
            assert _reset_guess(db) == "auth_reset_code_invalid"
        db.refresh(token)
        assert token.consumed is True

    def test_the_real_reset_code_stops_working_once_spent(self, db):
        """Higher stakes than the OTP: this one changes the password."""
        user = _user(db)
        _reset_token(db, user)
        before = user.password_hash
        for _ in range(otp.MAX_ATTEMPTS):
            _reset_guess(db)
        assert _reset_guess(db, code=GOOD) == "auth_reset_code_invalid"
        db.refresh(user)
        assert user.password_hash == before

    def test_a_near_miss_still_lets_the_real_reset_code_through(self, db):
        user = _user(db)
        _reset_token(db, user)
        before = user.password_hash
        for _ in range(otp.MAX_ATTEMPTS - 1):
            _reset_guess(db)
        result = account.confirm_password_reset(
            db, PasswordResetConfirm(phone=PHONE, code=GOOD, new_password="newpassword1")
        )
        assert result["message"]
        db.refresh(user)
        assert user.password_hash != before

    def test_reset_guesses_are_charged_across_every_live_token(self, db):
        user = _user(db)
        a = _reset_token(db, user, code="111111")
        b = _reset_token(db, user, code="222222")
        for _ in range(otp.MAX_ATTEMPTS):
            _reset_guess(db)
        db.refresh(a)
        db.refresh(b)
        assert a.consumed is True and b.consumed is True


class TestSpendAttempt:
    """The helper on its own, including the case neither caller reaches."""

    def test_it_charges_a_row_the_live_query_missed(self, db):
        user = _user(db)
        challenge = _challenge(db, user)
        assert otp.spend_attempt([], challenge) is False
        assert challenge.attempts == 1

    def test_it_reports_the_allowance_is_gone(self, db):
        user = _user(db)
        challenge = _challenge(db, user)
        challenge.attempts = otp.MAX_ATTEMPTS - 1
        assert otp.spend_attempt([challenge], challenge) is True

    def test_a_row_is_never_charged_twice_for_one_guess(self, db):
        user = _user(db)
        challenge = _challenge(db, user)
        otp.spend_attempt([challenge], challenge)
        assert challenge.attempts == 1
