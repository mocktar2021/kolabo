"""Epic I: the Alembic baseline migration builds and reverses the whole schema."""
import sqlite3

from alembic import command
from alembic.config import Config


def _config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_builds_schema(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"
    command.upgrade(_config(url), "head")

    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    conn.close()
    # Spot check tables from several epics plus the new country table.
    for expected in ("users", "escrows", "reviews", "reports", "country_configs", "alembic_version"):
        assert expected in tables


def test_downgrade_base_drops_schema(tmp_path):
    db = tmp_path / "m.db"
    url = f"sqlite:///{db}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    conn.close()
    assert "country_configs" not in tables and "users" not in tables
