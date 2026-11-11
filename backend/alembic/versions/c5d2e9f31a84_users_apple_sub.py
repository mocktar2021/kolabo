"""users.apple_sub: the Apple account an account is linked to

Revision ID: c5d2e9f31a84
Revises: a2f7b1c45d90
Create Date: 2026-11-11

The same shape as a7f1c6e3d940, one nullable column and one unique index, and
almost everything that file argues applies here unchanged: the index is what
stops two Kolabo accounts claiming one identity, nullable is honest because
almost no row has one, there is no backfill because a `sub` cannot be derived
from anything we hold, and the index name is the one SQLAlchemy derives from
unique=True, index=True so a database built by `alembic upgrade head` and one
built by create_all agree about it.

WHAT IS DIFFERENT IS HOW MUCH THIS COLUMN CARRIES. google_sub is bookkeeping:
the Google sign in path finds the account by the confirmed address in the
token and writes the subject afterwards so a settings screen can draw a
connected row. Apple does not put an address in the token after the first
authorisation, and the address it does put there may be a per app relay, so
THIS column is the only way to find the account on every sign in after the
first. A row that loses it is a person who can no longer sign in with Apple,
not a settings screen that looks wrong.

WHICH IS ALSO WHY THE SECOND PROVIDER DID NOT EARN THE identities TABLE that
a7f1c6e3d940 said it might. That file's own test was rows this product cannot
have: many providers per user, or many links per provider. Apple adds neither.
It is still at most one link per provider per account, so a table would buy a
join on the sign in path and a second home for one fact, in exchange for
nothing. Two nullable columns is where two providers honestly lands.

DOWN_REVISION IS a2f7b1c45d90, the single head, verified by reading every file
in the versions directory rather than assumed. a7f1c6e3d940 records why that
matters on this repo: two branches open at once both wrote themselves off the
same parent once before, and `upgrade head` then raises "Multiple head
revisions are present" on main and on neither branch. Worth re-checking at
merge time if anything else lands first.

The downgrade drops exactly what the upgrade added, in the reverse order, and
always succeeds. What it costs is every Apple link, and the next sign in from
one of those devices arrives with a subject nothing recognises and an address
Apple has stopped sending, which on this provider means a new account rather
than a re-link. That is the real cost of this downgrade and it is worth saying
out loud, because the equivalent sentence in a7f1c6e3d940 is "losing this
column loses the link and nothing else" and that is not true here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d2e9f31a84'
down_revision: Union[str, None] = 'a2f7b1c45d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USERS_TABLE = 'users'
APPLE_SUB_COLUMN = 'apple_sub'

# Matches the name SQLAlchemy derives from User.apple_sub's unique=True,
# index=True, exactly as IX_USERS_GOOGLE_SUB does next door.
IX_USERS_APPLE_SUB = 'ix_users_apple_sub'


def upgrade() -> None:
    # batch_alter_table for the reason a7f1c6e3d940 gives: SQLite cannot alter
    # a table in place, neither of these two operations forces a rebuild
    # today, and the batch is still the right shape for the day one that does
    # is added beside them.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(APPLE_SUB_COLUMN, sa.String(), nullable=True))
        batch_op.create_index(IX_USERS_APPLE_SUB, [APPLE_SUB_COLUMN], unique=True)


def downgrade() -> None:
    # The index before the column, inside one batch. Same ordering and same
    # reason as a7f1c6e3d940 and f3c0a84e17d9.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.drop_index(IX_USERS_APPLE_SUB)
        batch_op.drop_column(APPLE_SUB_COLUMN)
