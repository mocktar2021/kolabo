"""creator referral codes

Users gain a shareable referral_code (unique, minted lazily the first time the
owner asks for it) and referred_by_user_id, a self-referencing FK recording who
brought them in. MVP scope: codes and attribution only — reward mechanics are
a later business decision, so nothing here touches money. batch_alter_table
throughout because SQLite cannot add a FK column in place; the batch recreate
carries the inline ForeignKey with it.

Revision ID: b8d4f6a2c9e1
Revises: e7c3a9d15b42
Create Date: 2026-07-31 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d4f6a2c9e1'
down_revision: Union[str, None] = 'e7c3a9d15b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('referral_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('referred_by_user_id', sa.String(), sa.ForeignKey('users.id'), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_referral_code'), ['referral_code'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_referral_code'))
        batch_op.drop_column('referred_by_user_id')
        batch_op.drop_column('referral_code')
