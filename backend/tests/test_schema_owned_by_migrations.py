"""Every model table must be created by a migration.

THIS TEST IS THE REASON init_db CAN STOP CALLING create_all. Until #196 the app
ran `alembic upgrade head` and then create_all, in that order, on every boot. Any
table a migration had forgotten was conjured from model metadata a moment after
Alembic reported success, so a missing migration was invisible on a running
deployment and only surfaced somewhere it hurt: c9a4e7b21f36 found otp_challenges
and password_reset_tokens missing from the baseline after weeks of everything
apparently working.

With create_all gone, a forgotten migration is a missing table on a fresh
database, and the first request that touches it fails. That is the correct
behaviour and a much worse thing to discover on a production box than in CI, so
the invariant that made the removal safe is asserted here rather than left as a
one-time check somebody did once and wrote down.

WHAT IT READS AND WHY NOT A DATABASE. It compares Base.metadata against the
create_table calls in the migration files as TEXT. Actually running the
migrations would be a stronger check and it needs a database the suite does not
have; parsing is exact enough for the one question being asked, which is whether
a table name appears in a migration at all, and it cannot fail for any
environmental reason.

IF THIS FAILS AFTER YOU ADDED A MODEL, you owe it a migration. If it fails
because a migration creates a table by a name this parser cannot see (a constant,
an f-string), extend TABLE_RE: a false failure here is cheap and a false pass is
the bug this file exists to prevent.
"""
import re
from pathlib import Path

from app.core.db import Base, import_all_models

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"

# op.create_table('name', ...) and the black-formatted form with the name on the
# following line. Nothing in this repository builds a table name any other way.
TABLE_RE = re.compile(r"""create_table\(\s*(?:\n\s*)?["']([a-zA-Z_0-9]+)["']""")


def _migration_tables() -> set[str]:
    files = sorted(VERSIONS_DIR.glob("*.py"))
    assert files, f"no migrations found under {VERSIONS_DIR}"
    tables: set[str] = set()
    for path in files:
        tables.update(TABLE_RE.findall(path.read_text(encoding="utf-8")))
    return tables


def test_every_model_table_is_created_by_a_migration():
    import_all_models()
    model_tables = set(Base.metadata.tables)
    missing = sorted(model_tables - _migration_tables())
    assert not missing, (
        "These tables exist in the model registry and no migration creates them, "
        "so a fresh database will not have them and nothing builds them at boot "
        "any more: " + ", ".join(missing)
    )


def test_no_migration_creates_a_table_no_model_describes():
    """The other direction, which is a weaker claim and still worth holding.

    A table created by a migration with no model behind it is either a leftover
    from a dropped feature or a model that fell out of import_all_models, and the
    second one is indistinguishable from the first until somebody goes looking.
    """
    import_all_models()
    orphans = sorted(_migration_tables() - set(Base.metadata.tables))
    assert not orphans, (
        "These tables are created by a migration and no model describes them. "
        "Either the model is missing from import_all_models in app/core/db.py, "
        "or the table is a leftover that needs a migration to drop it: "
        + ", ".join(orphans)
    )
