"""campaign description

One column: campaigns.description, the brief in prose beside the title.

It arrives with the edit endpoints because it is half of what stays editable
after a campaign is published — title and description are description, not
terms, so rewriting them does not change what a creator bid FOR. Without a
description column that rule had nowhere to land.

Nullable with no default, and no backfill. A campaign written before this
column had a title and a deliverables list and nothing else to say; inventing
prose for it would be putting words in a brand's mouth. NULL is the true
value and reads as "nobody wrote one".

No constraint is introduced. The batch rebuild re-declares the whole campaigns
table, and alembic cannot reconstruct a constraint it cannot name, so the rule
f1a7c9d2e4b8 left behind stands: any constraint added to this table later must
be NAMED.

Revision ID: d2b6f4e91c07
Revises: f1a7c9d2e4b8
Create Date: 2026-08-03 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2b6f4e91c07'
down_revision: Union[str, None] = 'f1a7c9d2e4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('description')
