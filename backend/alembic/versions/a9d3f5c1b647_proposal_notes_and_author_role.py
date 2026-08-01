"""proposal notes and author role

A proposal version gains the reason for its numbers (note) and the side that
wrote it (author_role). Both belong on the version rather than in a table of
their own: a note argues for one specific set of terms and stops being true the
moment they change, and author_role is what turns a chain of five rows into a
conversation instead of one creator apparently changing their mind five times.

author_role gets a server_default of 'influencer' only to fill existing rows —
every proposal written before the business could reply came from a creator —
and then loses it, so new rows take their value from the model. Same pattern as
quantity in e7c3a9d15b42.

No new constraint is introduced here; both columns are plain. The batch rebuild
still copies proposals and re-declares what it already carries, so the rule the
referral foreign key taught in a102d590 stands for this table too: any
constraint added to it later must be NAMED, because alembic cannot reconstruct
one it cannot name.

Revision ID: a9d3f5c1b647
Revises: c3f7a1d9e08b
Create Date: 2026-08-01 01:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9d3f5c1b647'
down_revision: Union[str, None] = 'c3f7a1d9e08b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app.modules.campaigns.models.AUTHOR_INFLUENCER. Duplicated on
# purpose: a migration records the value as it was the day the data moved, and
# must keep working after the application constant changes.
AUTHOR_INFLUENCER = 'influencer'


def upgrade() -> None:
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column('author_role', sa.String(), nullable=False, server_default=AUTHOR_INFLUENCER)
        )

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.alter_column(
            'author_role',
            existing_type=sa.String(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_column('author_role')
        batch_op.drop_column('note')
