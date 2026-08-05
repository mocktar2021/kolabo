"""users.is_admin

Revision ID: e4a92c17b6d3
Revises: c7d41e0b8a92
Create Date: 2026-08-05

The column that turns an admin from a header value into an account.

NOT NULL with a server default of false, so every existing row is a
non-admin — which is the only safe direction for a privilege column. Nothing
is granted here: app.modules.auth.admins.sync_admins does that at boot from
the configured phone list, and it does it on every boot so the list stays the
single source of truth.

A server_default rather than only a Python-side default, because the existing
rows are filled by the database during the ALTER and nothing in the app is
running to supply a value for them.
"""
import sqlalchemy as sa
from alembic import op

revision = "e4a92c17b6d3"
down_revision = "c7d41e0b8a92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
