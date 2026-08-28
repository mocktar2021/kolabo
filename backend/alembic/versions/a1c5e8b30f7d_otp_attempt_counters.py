"""otp and reset code attempt counters

Revision ID: a1c5e8b30f7d
Revises: 4423dba6754c
Create Date: 2026-08-28

The column that stops a six digit code from being guessable at leisure.

Until now a wrong OTP guess incremented nothing and consumed nothing, and
there is no rate limiting anywhere in the application, so a code could be
attacked for the whole of its ten minute life in parallel and for free. The
same table backs password reset, which turns that from a nuisance into
account takeover.

NOT NULL with a server default of 0, so every existing row starts with a full
allowance — the only safe direction, since the alternative would retire codes
that are legitimately in flight the moment this deploys. The default is
dropped immediately afterwards so new rows take the model's value instead.

The inspector guard is the convention these two tables specifically need:
otp_challenges and password_reset_tokens are also created by create_all at app
startup, which runs after `alembic upgrade head`, so a deployment that has
started once already may present the column before this migration reaches it.
See c9a4e7b21f36, which created these tables with the same guard and for the
same reason.
"""
import sqlalchemy as sa
from alembic import op

revision = "a1c5e8b30f7d"
down_revision = "4423dba6754c"
branch_labels = None
depends_on = None

TABLES = ("otp_challenges", "password_reset_tokens")


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    for table in TABLES:
        if "attempts" in _columns(table):
            continue
        op.add_column(
            table,
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
        # The default existed only to fill existing rows; new rows get their
        # value from the model.
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("attempts", server_default=None)


def downgrade() -> None:
    for table in TABLES:
        if "attempts" not in _columns(table):
            continue
        op.drop_column(table, "attempts")
