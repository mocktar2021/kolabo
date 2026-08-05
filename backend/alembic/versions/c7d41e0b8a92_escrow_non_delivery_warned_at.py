"""escrow non_delivery_warned_at

Revision ID: c7d41e0b8a92
Revises: a3f8b1c47d20
Create Date: 2026-08-05

One nullable column, and the reason it is the only one.

The non-delivery sweep needs two facts: when the delivery was promised, and
whether the parties have already been warned that it passed. Only the second
is stored.

THE DEADLINE IS DERIVED, NOT STORED — held_at + contract.timeline_days. Both
halves are immutable once the contract is signed, so the derivation cannot
drift, and deriving it means every escrow funded BEFORE this migration is
covered by the sweep the moment it ships. Those are exactly the escrows the
feature exists for: the ones already sitting held with nothing delivered
against them and no ending in sight. A stored column would have needed a
backfill joining contracts inside a migration to reach them, which is more
risk for less coverage.

The warning, by contrast, is an EVENT rather than a fact about the contract.
Nothing else records that it happened, and without a stamp a sweep run twice
a day would send the same warning twice a day.

Null means "not warned yet", which is the correct state for every existing
row, so there is nothing to backfill here either.
"""
import sqlalchemy as sa
from alembic import op

revision = "c7d41e0b8a92"
down_revision = "a3f8b1c47d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrows", sa.Column("non_delivery_warned_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("escrows", "non_delivery_warned_at")
