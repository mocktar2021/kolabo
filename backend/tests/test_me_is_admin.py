"""/auth/me says whether the caller is an admin.

Tested against account.get_me rather than through the router: the field is
assembled in _me_out and nothing about HTTP changes what it contains.

WHY THE FIELD EXISTS. Admin is not a role in this system — it is a flag beside
one, so that every existing role check keeps working and an admin is also an
ordinary marketplace user. Which meant the frontend had no way to ask the
question: getStoredRole answers "influencer | business | agency" and nothing
else. That is why /admin/disputes is declared in App.tsx with no guard on it,
and why the page was reachable by anyone and simply rendered empty while every
request on it 403'd.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.modules.auth import account
from app.modules.auth.models import User
from app.modules.auth.schemas import AccountPatch, MeOut


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


def _user(db, phone, is_admin=False):
    user = User(
        phone=phone,
        password_hash="x",
        country_code="BJ",
        role="business",
        is_verified=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_an_ordinary_account_is_not_an_admin(db):
    user = _user(db, "+22990002001")
    assert account.get_me(db, user.id)["is_admin"] is False


def test_an_admin_account_says_so(db):
    user = _user(db, "+22990002002", is_admin=True)
    assert account.get_me(db, user.id)["is_admin"] is True


def test_the_field_survives_the_response_model(db):
    """MeOut is what the router serialises through; a field the schema drops
    would leave the frontend exactly as blind as it was before."""
    user = _user(db, "+22990002003", is_admin=True)
    assert MeOut(**account.get_me(db, user.id)).is_admin is True


def test_admin_is_not_settable_through_the_account_patch(db):
    """THE RULE THAT MATTERS MORE THAN THE FIELD.

    A grant endpoint is deliberately absent — auth.admins reconciles the flag
    from deployment configuration on every boot, because that is the one
    channel an attacker who has reached the API does not automatically have.
    Pydantic ignores unknown keys rather than refusing them, so a client
    posting is_admin gets a 200 and no privilege; asserted here so that a
    later change to model_config cannot quietly open a door.
    """
    patch = AccountPatch.model_validate(
        {"current_password": "whatever", "is_admin": True}
    )
    assert not hasattr(patch, "is_admin")
    assert "is_admin" not in patch.model_dump(exclude_unset=True)
