"""users.google_sub: the Google account an account is linked to

Revision ID: a7f1c6e3d940
Revises: b4e9c2a71f05
Create Date: 2026-09-16

One nullable column and one unique index, and between them they are the whole
of "this account is linked to Google".

UNTIL NOW THE LINK WAS VERIFIED AND THEN THROWN AWAY. auth/google.py checked a
Google ID token, read the `sub` claim out of it, carried it on a frozen
GoogleIdentity and handed it to a service that stored nothing. So the settings
screen could not draw a connected row, there was nothing for a later revoke to
clear, and the platform had no way to notice that two Kolabo accounts were one
person's single Google account. The claim was already trustworthy; it simply
had nowhere to live.

WHAT THE UNIQUE INDEX BUYS is the one property the service layer cannot supply
on its own: that no two accounts claim the same Google identity. A service that
SELECTs by subject and then UPDATEs has a window between the two, and two sign
ins racing through that window both pass the check and both write. Only the
database can refuse the second one. The index is the read path as well, because
the sign in path looks a row up by this value to answer exactly that question.

A COLUMN AND NOT A TABLE, and a reviewer should weigh this rather than assume
it. There is one provider and at most one value per account, so a
google_identities table would be a join on the sign in path and a second home
for one fact. The tables that DO exist next door earn their shape from rows
this does not have: social_accounts is one row per platform per creator, and
social_tokens is separate from it because it holds ciphertext that must not be
selected on the public profile path (see d7b3f1a90c46). Nothing here is a
secret and nothing here is repeated. The day a second sign in provider arrives
is the day a table earns itself, and moving one nullable column into one is a
smaller migration than this one.

THE COLUMN IS NULLABLE BECAUSE ALMOST NO ACCOUNT HAS ONE, which is the same
reasoning e1b7d4c92f08 set out for users.email at the time: Postgres and SQLite
both permit any number of rows under a unique index with a null in the indexed
column, so the constraint that matters is real either way. Two accounts still
cannot share a Google identity, and a row carrying none is simply not in the
running for one.

NO BACKFILL, AND NOTHING COULD HAVE BEEN BACKFILLED. Every existing row stays
null, which reads as "not linked", and that is the truth rather than a
convenient default: no subject was ever recorded, and a `sub` cannot be derived
from an address by us or by anybody else, because only a token Google signed
carries one. Fabricating a value would be a lie in a column whose entire job is
to be compared for equality, and it would be unique, so the constraint would
report success over precisely the rows it was added to police. An account that
really is linked starts saying so the next time its owner signs in with Google:
the service adopts the subject whenever the column is null.

THE INDEX NAME IS NOT ARBITRARY. ix_users_google_sub is exactly what SQLAlchemy
derives from unique=True, index=True on User.google_sub, so a database built by
`alembic upgrade head` and one built by create_all at app startup agree about
it, rather than differing by a name nobody would notice until a later revision
tried to drop one of them. ix_users_email, ix_users_phone and
ix_users_referral_code were named the same way and for the same reason.

IT IS A NAMED MODULE CONSTANT because SQLite cannot alter constraints in place.
A later batch_alter_table on users copies the table, rebuilds it from the
reflected schema and swaps it in; that rebuild re-declares every constraint,
and alembic cannot reconstruct one it cannot name ("Constraint must have a
name"). c3f7a1d9e08b wrote that rule down after CI failed on an anonymous one,
and a3f8b1c47d20, e2f9c4a71d38, c9a4e7b21f36, d7b3f1a90c46, e1b7d4c92f08,
f3c0a84e17d9 and b4e9c2a71f05 have restated it since. b8d4f6a2c9e1 is the
precedent on this table specifically, and its named foreign key is one of the
constraints the downgrade below depends on being reconstructible.

NO INSPECTOR GUARD, for the reason e1b7d4c92f08, f3c0a84e17d9 and b4e9c2a71f05
all give about this same table: users has belonged to alembic since the
baseline (5f3a9c80d26f), and create_all at app startup does not add a column or
an index to a table it finds already present. The guards in c9a4e7b21f36,
f8a1c3d20e5b, d7b3f1a90c46, a1c5e8b30f7d and c4a1e8d73b25 are there because the
OBJECTS THOSE REVISIONS CREATE can also be built by create_all, which runs
AFTER `alembic upgrade head` in the container command, so a deployment that has
already booted once presents them before the migration arrives.

DOWN_REVISION IS b4e9c2a71f05, the single head, verified by reading every file
in the versions directory rather than assumed. This repo has already had one
two-head incident (see the re-parenting of b2e6d90a3f14 onto a1c5e8b30f7d): two
branches open at once both wrote themselves off the same parent, and
`upgrade head` then raises "Multiple head revisions are present" on main and on
neither branch. Worth re-checking at merge time if anything else lands first.

The downgrade drops exactly what the upgrade added, in the reverse order, and
always succeeds: losing this column loses the link and nothing else, since no
credential, no history and no money reference it. What it cannot do is put the
links back afterwards, for the same reason the upgrade cannot backfill them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7f1c6e3d940'
down_revision: Union[str, None] = 'b4e9c2a71f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USERS_TABLE = 'users'
GOOGLE_SUB_COLUMN = 'google_sub'

# Matches the name SQLAlchemy derives from User.google_sub's unique=True,
# index=True, so this is one UNIQUE index rather than an index plus a
# separate constraint.
IX_USERS_GOOGLE_SUB = 'ix_users_google_sub'


def upgrade() -> None:
    # batch_alter_table because SQLite cannot alter a table in place. Neither
    # an add_column nor a create_index requires a rebuild, so alembic issues
    # plain ALTER TABLE ADD COLUMN and CREATE UNIQUE INDEX here rather than
    # copying the table; e1b7d4c92f08 makes the same observation about its own
    # create_index. The batch is still the right shape, because the day an
    # operation that DOES force a rebuild is added beside these two, nothing
    # about the file has to change.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(GOOGLE_SUB_COLUMN, sa.String(), nullable=True))
        batch_op.create_index(IX_USERS_GOOGLE_SUB, [GOOGLE_SUB_COLUMN], unique=True)


def downgrade() -> None:
    # THE INDEX GOES BEFORE THE COLUMN, inside one batch, for the reason
    # f3c0a84e17d9 gives for the same ordering: dropping a column really does
    # rebuild the table on SQLite, and the other order would carry the unique
    # index forward onto the new table and then be asked to drop it from a
    # table that has just been replaced underneath it.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.drop_index(IX_USERS_GOOGLE_SUB)
        batch_op.drop_column(GOOGLE_SUB_COLUMN)
