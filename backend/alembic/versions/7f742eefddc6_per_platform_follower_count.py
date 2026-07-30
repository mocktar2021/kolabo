"""per platform follower count

Revision ID: 7f742eefddc6
Revises: 146392f428c3
Create Date: 2026-07-30 14:32:59.640854
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f742eefddc6'
down_revision: Union[str, None] = '146392f428c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('follower_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.drop_column('follower_count')
