"""referral credits

A ledger of platform credit earned from referrals: one row per recipient per
award, denominated in that recipient's own market currency. The "referee" row
for a user doubles as the record that their first order completed and was
rewarded, which is what stops a second order paying out again — see
app.modules.auth.referrals for the product decisions behind all of it.

Every constraint is NAMED, foreign keys included. SQLite cannot alter
constraints in place, so any later batch_alter_table on this table copies it,
rebuilds it from the reflected schema and swaps it in; that rebuild re-declares
every constraint, and alembic cannot reconstruct one it cannot name
("Constraint must have a name"). The previous migration learned this the hard
way on users, and a table created with anonymous constraints only fails later,
when someone else is trying to add a column.

source_user_id is nullable on purpose: an earned credit outlives the other half
of the pair deleting their account.

Revision ID: c3f7a1d9e08b
Revises: b8d4f6a2c9e1
Create Date: 2026-07-31 15:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f7a1d9e08b'
down_revision: Union[str, None] = 'b8d4f6a2c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_REFERRAL_CREDITS = 'pk_referral_credits'
FK_USER = 'fk_referral_credits_user_id'
FK_SOURCE_USER = 'fk_referral_credits_source_user_id'
IX_USER = 'ix_referral_credits_user_id'


def upgrade() -> None:
    op.create_table(
        'referral_credits',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('source_user_id', sa.String(), nullable=True),
        sa.Column('contract_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_REFERRAL_CREDITS),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=FK_USER),
        sa.ForeignKeyConstraint(['source_user_id'], ['users.id'], name=FK_SOURCE_USER),
    )
    op.create_index(IX_USER, 'referral_credits', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(IX_USER, table_name='referral_credits')
    op.drop_table('referral_credits')
