"""gateway fee columns

Revision ID: b2e6d90a3f14
Revises: a1c5e8b30f7d
Create Date: 2026-08-29

Two nullable columns, so that "what did we actually keep" is a query.

Kolabo takes its commission on the GROSS escrow amount, and the gateway takes
its own cut on each movement of that money — once on the way in, once on the
way out. Only the first of those three numbers was written anywhere the
platform can read. The gateway's cut existed solely inside the raw webhook
body on gateway_events.payload, which is a JSON blob kept for forensics and is
not something anyone should be asked to aggregate. The honest answer to "how
much did we net last month" was therefore a manual reconciliation against the
gateway's own dashboard. These columns replace that with SQL.

ADDITIVE AND NULLABLE. Nothing is altered, nothing is backfilled, and the
reverse drops exactly what was added.

NULL IS NOT ZERO HERE, and the column is nullable for precisely that reason
rather than for convenience. Null means the gateway did not report a fee for
that movement — which is the true state of every row written before this
migration, and remains the true state of any future row whose gateway stays
silent. A zero default would have claimed those movements were free, which is
a claim we cannot support and one that only ever errs in our own favour. There
is no backfill for the historical rows because there is no honest value to put
in them; they stay null, and a report that needs them can say so.

WRITTEN OFF 4423dba6754c, RE-PARENTED ONTO a1c5e8b30f7d. This revision and the
OTP attempt counters in a1c5e8b30f7d were authored against the same parent, on
branches open at the same time that could not see each other. Two revisions
sharing a parent are two heads once both are on main, and `upgrade head` then
refuses to run at all — which is a failure that appears on main and on nobody's
branch. a1c5e8b30f7d merged first, so this is the file that moves.

The order asserted here is arbitrary and that is the honest description of it.
The two migrations touch disjoint tables — otp_challenges and
password_reset_tokens there, payment_intents and payouts here — so they commute,
and nothing in this file depends on anything in that one. Alembic needs a total
order; this is one, not a dependency.
"""
import sqlalchemy as sa
from alembic import op

revision = "b2e6d90a3f14"
down_revision = "a1c5e8b30f7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_intents", sa.Column("gateway_fee", sa.Integer(), nullable=True))
    op.add_column("payouts", sa.Column("gateway_fee", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("payouts", "gateway_fee")
    op.drop_column("payment_intents", "gateway_fee")
