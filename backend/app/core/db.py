"""Database engine, session, and declarative base.

ALEMBIC IS THE ONLY THING THAT BUILDS SCHEMA OUTSIDE THE TEST SUITE. init_db
used to also call Base.metadata.create_all on every boot, and the container
command runs `alembic upgrade head && uvicorn`, so create_all ran last and any
table a migration had forgotten was silently conjured from model metadata
instead. A missing migration could therefore never be noticed on a running
deployment, which is the exact failure mode a migration tool exists to prevent,
and c9a4e7b21f36 hit it: otp_challenges and password_reset_tokens were absent
from the baseline for weeks with nothing broken to show for it. That revision's
own docstring says the real fix is here.

VERIFIED BEFORE REMOVING IT, because create_all silently covering a gap and
create_all being load-bearing look identical from the outside: all 37 tables in
this registry are created by a migration under alembic/versions, and the
difference in both directions is empty. Two migration docstrings assert that
`notifications` is owned by no migration and exists only through create_all;
both are wrong, the baseline 5f3a9c80d26f creates it, and their inspector guards
are harmless either way.

The test suite still builds its schema with create_all, directly, because it has
no migration step and wants none. That is why import_all_models stays shared:
the registry has one definition, whether it is read by create_all in a fixture
or by Alembic's autogenerate.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def import_all_models() -> None:
    """Import every module's models so they register on Base.metadata.

    Used by init_db, by the test fixtures that call create_all, and by the
    Alembic env so autogenerate and migrations see the full schema.

    A MODULE MISSING FROM THIS LIST IS A TABLE THAT EXISTS IN PRODUCTION AND
    NOT IN TESTS. The suite builds its schema with create_all, so a model
    nobody imports here simply is not there when a test runs, and the failure
    surfaces as a confusing "no such table" in whichever test first touches it,
    long after the model was written. payments.gateway_models is listed
    separately from payments.models for that reason: it is a second models
    module in one package and the easiest kind to forget.

    IT IS ALSO A TABLE ALEMBIC CANNOT SEE. The Alembic env imports this same
    function, so a model absent from this list is absent from autogenerate too,
    and now that nothing calls create_all outside tests, absent from every
    deployed database. A new model module goes in this list in the same commit.
    """
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.profiles import models as profile_models  # noqa: F401
    from app.modules.admin import models as admin_models  # noqa: F401
    from app.modules.discovery import models as discovery_models  # noqa: F401
    from app.modules.notifications import models as notification_models  # noqa: F401
    from app.modules.campaigns import models as campaign_models  # noqa: F401
    from app.modules.contracts import models as contract_models  # noqa: F401
    from app.modules.messaging import models as messaging_models  # noqa: F401
    from app.modules.payments import models as payment_models  # noqa: F401
    from app.modules.payments import gateway_models as payment_gateway_models  # noqa: F401
    from app.modules.deliverables import models as deliverable_models  # noqa: F401
    from app.modules.trust_safety import models as trust_safety_models  # noqa: F401
    from app.modules.config import models as config_models  # noqa: F401


def init_db() -> None:
    """Runtime setup that is NOT schema. Called once from the app's lifespan.

    Whatever is added here has to be safe to run on every boot of every
    replica, because it does.
    """
    # Still imported, so that every mapper is configured before the first
    # request rather than on whichever request first touches a lazy
    # relationship, and so Base.metadata is complete for anything that reads it.
    import_all_models()
    # Seed the country table once so config reads have data from first boot.
    from app.modules.config.service import seed_countries

    db = SessionLocal()
    try:
        seed_countries(db)
    finally:
        db.close()
