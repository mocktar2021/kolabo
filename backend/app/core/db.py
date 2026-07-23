"""Database engine, session, and declarative base.

Table creation is done here via init_db for now. Alembic migrations replace
this in Epic I (KOL-34); until then init_db creates tables from model metadata.
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


def init_db() -> None:
    # Import all module models so they register on Base.metadata before create_all.
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.profiles import models as profile_models  # noqa: F401
    from app.modules.admin import models as admin_models  # noqa: F401
    from app.modules.discovery import models as discovery_models  # noqa: F401
    from app.modules.notifications import models as notification_models  # noqa: F401
    from app.modules.campaigns import models as campaign_models  # noqa: F401
    from app.modules.contracts import models as contract_models  # noqa: F401
    from app.modules.messaging import models as messaging_models  # noqa: F401
    from app.modules.payments import models as payment_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
