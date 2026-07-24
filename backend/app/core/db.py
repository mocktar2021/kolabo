"""Database engine, session, and declarative base.

Schema is managed two ways during the pilot. Alembic migrations are the source
of truth for production (introduced in Epic I, KOL-34). For tests and local dev
init_db creates tables directly from model metadata, which is faster and needs
no migration step. import_all_models is shared by both so the model registry has
a single definition.
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

    Used by init_db (create_all) and by the Alembic env so autogenerate and
    migrations see the full schema.
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
    from app.modules.trust_safety import models as trust_safety_models  # noqa: F401
    from app.modules.config import models as config_models  # noqa: F401


def init_db() -> None:
    import_all_models()
    Base.metadata.create_all(bind=engine)
    # Seed the country table once so config reads have data from first boot.
    from app.modules.config.service import seed_countries

    db = SessionLocal()
    try:
        seed_countries(db)
    finally:
        db.close()
