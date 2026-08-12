"""payment gateway tables

Revision ID: 4423dba6754c
Revises: e4a92c17b6d3
Create Date: 2026-08-12

The four tables the FedaPay integration needs. All ADDITIVE — no existing
column is altered and no existing row is touched, so this migration is safe to
run against a populated database and safe to reverse.

payment_intents  one attempt by a brand to fund one contract
payouts          one attempt to push money to one person's wallet
payout_methods   where a creator wants to be paid, and over which network
gateway_events   webhooks already processed, the idempotency key

WHY payment_intents.contract_id IS INDEXED BUT NOT UNIQUE: a brand whose first
attempt failed must be able to try again, and each try is its own row. What is
unique is the escrow, and escrows.contract_id already carries that constraint.

WHY gateway_events HAS A COMPOSITE UNIQUE: (provider, event_id) is the whole
idempotency mechanism. The webhook handler inserts BEFORE doing the work, so
two concurrent deliveries of one event race on this constraint and exactly one
wins. Without the constraint the race is silent and both deliveries settle the
same payment.

The escrows.contract_id unique constraint is what stops a double-funded
contract even if both intents somehow succeed, so nothing here duplicates it.
"""
import sqlalchemy as sa
from alembic import op

revision = "4423dba6754c"
down_revision = "e4a92c17b6d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("contract_id", sa.String(), nullable=False),
        sa.Column("business_user_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider_status", sa.String(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("escrow_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["business_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["escrow_id"], ["escrows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_intents_contract_id", "payment_intents", ["contract_id"])
    op.create_index("ix_payment_intents_business_user_id", "payment_intents", ["business_user_id"])
    # Indexed because the webhook looks a row up BY THIS COLUMN on every
    # delivery. Without it, every payment confirmation is a full table scan of
    # a table that only ever grows.
    op.create_index("ix_payment_intents_provider_ref", "payment_intents", ["provider_ref"])
    op.create_index("ix_payment_intents_status", "payment_intents", ["status"])

    op.create_table(
        "payouts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("escrow_id", sa.String(), nullable=False),
        sa.Column("recipient_user_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider_status", sa.String(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["escrow_id"], ["escrows.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payouts_escrow_id", "payouts", ["escrow_id"])
    op.create_index("ix_payouts_recipient_user_id", "payouts", ["recipient_user_id"])
    op.create_index("ix_payouts_provider_ref", "payouts", ["provider_ref"])
    # The retry sweep filters on status every run. Indexed so a growing table
    # of successfully-sent payouts does not slow down finding the few that
    # still need attention.
    op.create_index("ix_payouts_status", "payouts", ["status"])

    op.create_table(
        "payout_methods",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # One row per user: a creator is paid one way. Changing it is an
        # update, and what was actually used on a given payment is recorded on
        # the payouts row rather than by keeping old methods around.
        sa.UniqueConstraint("user_id", name="uq_payout_method_user"),
    )

    op.create_table(
        "gateway_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_gateway_event"),
    )


def downgrade() -> None:
    op.drop_table("gateway_events")
    op.drop_table("payout_methods")
    op.drop_index("ix_payouts_status", table_name="payouts")
    op.drop_index("ix_payouts_provider_ref", table_name="payouts")
    op.drop_index("ix_payouts_recipient_user_id", table_name="payouts")
    op.drop_index("ix_payouts_escrow_id", table_name="payouts")
    op.drop_table("payouts")
    op.drop_index("ix_payment_intents_status", table_name="payment_intents")
    op.drop_index("ix_payment_intents_provider_ref", table_name="payment_intents")
    op.drop_index("ix_payment_intents_business_user_id", table_name="payment_intents")
    op.drop_index("ix_payment_intents_contract_id", table_name="payment_intents")
    op.drop_table("payment_intents")
