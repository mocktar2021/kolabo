"""creator identity: birth date, gender, languages

Adds the fields behind the 18+ gate and the identity section of the profile.
birth_date and gender are never exposed publicly; languages is public. The age
gate itself lives in the service and runs on every write, so the column
carries no CHECK constraint: "18 as of today" is application logic, not
schema.

Revision ID: d4f2b8c1e7a9
Revises: b7e1f0a4c2d8
Create Date: 2026-07-31 04:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f2b8c1e7a9'
down_revision: Union[str, None] = 'b7e1f0a4c2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('birth_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('gender', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('languages', sa.JSON(), nullable=False, server_default='[]'))

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.alter_column('languages', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.drop_column('languages')
        batch_op.drop_column('gender')
        batch_op.drop_column('birth_date')
