"""profile faq answers

Adds a JSON faq column to influencer_profiles holding the creator's answers to
the two standard profile questions, keyed by stable question id ("audience",
"brands"). The question wording is fixed product copy that lives in frontend
i18n so it renders in the viewer's language; only the answers are data, and two
fixed questions with free-text answers do not justify a table of their own.

Revision ID: b7e1f0a4c2d8
Revises: 9c41d7b2ae05
Create Date: 2026-07-31 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e1f0a4c2d8'
down_revision: Union[str, None] = '9c41d7b2ae05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('faq', sa.JSON(), nullable=False, server_default='{}'))

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.alter_column('faq', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.drop_column('faq')
