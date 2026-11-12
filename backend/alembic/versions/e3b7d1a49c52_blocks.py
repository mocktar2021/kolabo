"""blocks: one person's decision to stop dealing with another

Revision ID: e3b7d1a49c52
Revises: c5d2e9f31a84
Create Date: 2026-11-12

A NEW TABLE RATHER THAN A COLUMN, because the fact is about a PAIR and not
about either person. Anything hung off users would have to be a list, and a
list in a column is a thing you cannot index, cannot constrain and cannot ask
"is B in A's" without reading every row.

THE TABLE NAME IS A STRING LITERAL AND MUST STAY ONE.
tests/test_schema_owned_by_migrations.py reads this directory as TEXT, not as
code, and matches create_table calls with a regex that cannot resolve a
constant. Writing `op.create_table(BLOCKS_TABLE, ...)` made `blocks`
invisible to it, and the suite then reported that a model table had no
migration behind it, which is the exact alarm that file exists to raise and
was in this case false. The index names below stay constants because nothing
parses those.

THE UNIQUE CONSTRAINT IS THE WHOLE POINT OF THE SHAPE. Without it, pressing
block twice writes two rows, unblocking deletes one, and the person is still
blocked with no way to see why. uq_block_pair makes the second press a
conflict the endpoint can swallow and answer idempotently, which is what a
button somebody taps twice on a slow connection needs.

BOTH COLUMNS ARE INDEXED, SEPARATELY, and not only as the leading column of
the pair. Every read in blocks.py asks `blocker = me OR blocked = me`, so an
index on the pair alone would serve half of that condition and scan for the
other half. The names are the ones SQLAlchemy derives from index=True on each
column, so a database built by `alembic upgrade head` and one built by
create_all agree about them.

NO FOREIGN KEY CASCADE, deliberately. Account deletion in auth/service.py
already removes a user's rows explicitly, table by table, and a cascade here
would be a second mechanism doing the same job in a different place. BLOCKS
ARE NOT YET IN THAT LIST, and they must be before anything can create one: a
user with a block row and no cleanup is a user whose deletion fails on a
foreign key. That line lands with the endpoints, in the change that first
makes a row possible.

DOWN_REVISION IS c5d2e9f31a84, the single head, verified by reading the
versions directory rather than assumed. Worth re-checking at merge time if
anything else lands first; this repo has had two branches write themselves
off the same parent before, and `upgrade head` then fails on main and on
neither branch.

The downgrade drops the table. What it costs is every block anybody made,
which is to say it silently reconnects people who chose not to be connected.
That is a worse outcome than most downgrades on this repo and it is worth
saying out loud rather than discovering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3b7d1a49c52'
down_revision: Union[str, None] = 'c5d2e9f31a84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UQ_BLOCK_PAIR = 'uq_block_pair'
IX_BLOCKS_BLOCKER = 'ix_blocks_blocker_user_id'
IX_BLOCKS_BLOCKED = 'ix_blocks_blocked_user_id'


def upgrade() -> None:
    op.create_table(
        'blocks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('blocker_user_id', sa.String(), nullable=False),
        sa.Column('blocked_user_id', sa.String(), nullable=False),
        sa.Column('reason_code', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['blocker_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['blocked_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_user_id', 'blocked_user_id', name=UQ_BLOCK_PAIR),
    )
    op.create_index(IX_BLOCKS_BLOCKER, 'blocks', ['blocker_user_id'], unique=False)
    op.create_index(IX_BLOCKS_BLOCKED, 'blocks', ['blocked_user_id'], unique=False)


def downgrade() -> None:
    # Indexes before the table, so the drop does not depend on the database
    # cleaning up after itself. Same ordering as every other downgrade here.
    op.drop_index(IX_BLOCKS_BLOCKED, table_name='blocks')
    op.drop_index(IX_BLOCKS_BLOCKER, table_name='blocks')
    op.drop_table('blocks')
