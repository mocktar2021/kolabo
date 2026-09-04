"""follower provenance on social accounts

Revision ID: c4a1e8d73b25
Revises: b2e6d90a3f14
Create Date: 2026-09-04

Two nullable columns, so that a follower number can say where it came from.

social_accounts.follower_count is a number a brand reads before it decides
what to spend, and nothing recorded who supplied it. A figure the creator
typed into a form and a figure the platform's own API stated about its own
account were the same column with the same weight, so no page could tell a
buyer which of the two it was showing — and an inflated claim was
indistinguishable from a checked one. That is the whole defect: not that the
number might be wrong, but that a correct one and a wrong one looked
identical.

follower_source holds one of the values in
app.modules.profiles.models.FOLLOWER_SOURCES — "self_reported" or
"platform_api". follower_verified_at is stamped only when a platform stated
the number, so a client can say "verified on <date>" rather than making an
undated claim that ages silently.

NOT THE SAME QUESTION AS social_accounts.status, and kept in its own column
for exactly that reason. `status` is about the HANDLE — whether the creator
controls the account — which is what an admin decides in
admin.service.decide_social from a proof link. Nobody counts followers in
that review. A verified handle whose follower number is still self-reported
is a real and common state, and today it is the normal one; it now has
somewhere to be recorded instead of being flattened into the badge.

ADDITIVE AND NULLABLE. Nothing is altered, nothing is backfilled, and the
reverse drops exactly what was added.

NO BACKFILL, AND NULL IS NOT self_reported. Every row written before this
migration stays null, because there is no honest value to put in it: those
counts may have been typed by the creator, or filled by enrichment from a
platform response, and the code kept no record either way. We do not know.
Stamping them "self_reported" would be a guess wearing the clothes of a fact,
and "platform_api" would be the same guess in the direction that flatters the
number. Null means "no provenance recorded", and a client that reads one says
nothing about where the figure came from — which is precisely the truth.

THE INSPECTOR GUARD, following a1c5e8b30f7d and c9a4e7b21f36. social_accounts
is also created by create_all at app startup, which runs after
`alembic upgrade head`, so a deployment that has already started once may
present these columns before this migration reaches them; without the guard
that is a crash on deploy rather than a no-op. Its absence from b2e6d90a3f14
was flagged as a defect, and this file does not repeat it.
"""
import sqlalchemy as sa
from alembic import op

revision = "c4a1e8d73b25"
down_revision = "b2e6d90a3f14"
branch_labels = None
depends_on = None

TABLE = "social_accounts"


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    existing = _columns(TABLE)
    if "follower_source" not in existing:
        op.add_column(TABLE, sa.Column("follower_source", sa.String(), nullable=True))
    if "follower_verified_at" not in existing:
        op.add_column(TABLE, sa.Column("follower_verified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Dropped in the reverse of the order they were added, and only what this
    # revision put there.
    existing = _columns(TABLE)
    if "follower_verified_at" in existing:
        op.drop_column(TABLE, "follower_verified_at")
    if "follower_source" in existing:
        op.drop_column(TABLE, "follower_source")
