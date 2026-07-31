"""package quantity and duration

Packages gain Collabstr-style specs: a quantity (the "×10" chip) and an
optional duration (the "30 Seconds" chip). quantity gets a server_default of
'1' only to fill existing rows — every package sold so far was implicitly a
single deliverable — and then loses it, so new rows take their value from the
model; the same pattern as the languages column in d4f2b8c1e7a9. The duration
pair stays nullable: length is only part of the spec for some formats.

Revision ID: e7c3a9d15b42
Revises: d4f2b8c1e7a9
Create Date: 2026-07-31 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7c3a9d15b42'
down_revision: Union[str, None] = 'd4f2b8c1e7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('packages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('duration_value', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('duration_unit', sa.String(), nullable=True))

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('packages', schema=None) as batch_op:
        batch_op.alter_column('quantity', server_default=None)


def downgrade() -> None:
    with op.batch_alter_table('packages', schema=None) as batch_op:
        batch_op.drop_column('duration_unit')
        batch_op.drop_column('duration_value')
        batch_op.drop_column('quantity')
