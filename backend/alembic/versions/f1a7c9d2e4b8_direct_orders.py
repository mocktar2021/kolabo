"""direct orders

Two columns for the direct-order flow.

campaigns.is_direct marks a campaign that is really one brand buying one
creator's package. It gets a server_default of 'false' only to fill existing
rows — every campaign written before this column was a brief — and then loses
it, so new rows take their value from the model. Same pattern as author_role
in a9d3f5c1b647 and quantity in e7c3a9d15b42.

proposals.expires_at is the 48 hour clock a direct order runs on. It stays
nullable with no default, because NULL is the meaningful value for everything
else: a brief's proposals do not expire, and backfilling a deadline onto them
would silently kill open negotiations the first time the sweep runs.

Neither column introduces a constraint. sa.Boolean() emits no CHECK under
SQLAlchemy 2.x (create_constraint defaults to False), so nothing anonymous is
created here — which matters, because the batch rebuild re-declares the whole
table and alembic cannot reconstruct a constraint it cannot name. Any
constraint added to campaigns or proposals later must be NAMED.

Revision ID: f1a7c9d2e4b8
Revises: a9d3f5c1b647
Create Date: 2026-08-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a7c9d2e4b8'
down_revision: Union[str, None] = 'a9d3f5c1b647'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_direct', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.alter_column(
            'is_direct',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )

    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_column('expires_at')

    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('is_direct')
