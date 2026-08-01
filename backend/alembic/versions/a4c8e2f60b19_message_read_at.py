"""message read_at

One column: messages.read_at, null until the recipient opens the thread.

Messaging had no read state at all, and a thread that opens with a contract
needs one — an inbox with no unread count is an inbox nobody checks. A
timestamp rather than the boolean notifications carry (is_read), because these
messages hang off a contract and are the evidence trail a dispute reads: "when
did you see this" is a question a boolean cannot answer.

Nullable with no default and no backfill. Every message written before this
column existed has an unknown read state, and stamping them all read (or all
unread) would invent history on rows a dispute might later be argued from.
NULL is honest and reads as "we do not know".

No constraint is introduced. The batch rebuild re-declares the whole messages
table and alembic cannot reconstruct a constraint it cannot name, so the rule
f1a7c9d2e4b8 wrote down holds here too: any constraint added to this table
later must be NAMED.

Revision ID: a4c8e2f60b19
Revises: d2b6f4e91c07
Create Date: 2026-08-03 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4c8e2f60b19'
down_revision: Union[str, None] = 'd2b6f4e91c07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('read_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('read_at')
