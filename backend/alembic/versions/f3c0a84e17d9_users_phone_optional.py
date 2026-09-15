"""users.phone becomes optional and stops being an identity

Revision ID: f3c0a84e17d9
Revises: e1b7d4c92f08
Create Date: 2026-09-15

The other half of the identity flip. e1b7d4c92f08 gave users.email a unique
index and made an address something an account could BE; this revision takes
the matching property away from the phone, because the two columns cannot both
be the identity and only one of them is still collected at signup.

WHY THE COLUMN HAS TO CHANGE AT ALL, rather than being left alone. Registration
no longer asks for a phone number: the form takes an email address, a password,
a country and a role, and nothing on that path has a number to write. users.phone
is NOT NULL today, so the very first registration after the application change
would fail at INSERT with a null in a non-null column. That is not a subtle
regression to find in production, it is every signup, immediately, and it is
the reason this revision exists.

THE UNIQUE INDEX GOES TOO, and that is a product decision rather than a
mechanical consequence. Uniqueness alone would not have broken anything, since
both Postgres and SQLite permit many nulls under a unique index, so a table
full of null phones would have been perfectly legal. It goes because once the
phone is not an identity it is a CONTACT DETAIL, and a contact detail that no
two accounts may share is a rule with no justification behind it any more. One
person running a creator account and a business account from one handset is an
ordinary thing in these markets, and a unique index would refuse the second of
them at the database with no sentence anybody could read.

WHAT IS LOST BY THAT, stated plainly. auth/account.py::update_me still refuses
a phone number another account holds, with auth_phone_taken, and after this
revision that check is the ONLY thing enforcing it: there is no longer a
constraint underneath to catch two requests racing through the gap between the
SELECT and the UPDATE. That is an acceptable trade for a field nothing
authenticates with, and it would not be if the phone were still the login key.

THE COLUMN IS NOT DROPPED. Existing accounts registered before the flip have a
number in it and it is the only way to reach some of them; a business's number
is what payments/checkout.py puts on the FedaPay customer object; and the
settings screen can still write one through PATCH /auth/me. Dropping it would
throw away real contact data to tidy up a schema.

NO INSPECTOR GUARD, for the reason e1b7d4c92f08 gives about the same table:
users has belonged to alembic since the baseline (5f3a9c80d26f), and create_all
at app startup does not alter a table it finds already present. The guards in
c9a4e7b21f36, f8a1c3d20e5b and d7b3f1a90c46 are there because the OBJECTS THOSE
REVISIONS CREATE can also be built by create_all, which runs after
`alembic upgrade head` in the container command. Nothing here creates anything.

EVERY CONSTRAINT IS NAMED AS A MODULE LEVEL CONSTANT, and on this revision that
is not a formality, it is the thing that makes it work at all. SQLite cannot
alter a column in place, so the batch_alter_table below genuinely rebuilds the
users table: it reflects the schema, creates a new table from it, copies the
rows and swaps it in. Every constraint on the table has to be reconstructible
by name for that to succeed ("Constraint must have a name"), which is the rule
c3f7a1d9e08b wrote down after CI failed on an anonymous one and a3f8b1c47d20,
e2f9c4a71d38, c9a4e7b21f36, d7b3f1a90c46 and e1b7d4c92f08 have restated since.
IX_USERS_PHONE is spelled exactly as the baseline created it and exactly as
SQLAlchemy derives it from index=True on User.phone, so a database built by
`alembic upgrade head` and one built by create_all agree about it.

THE INDEX IS DROPPED BEFORE THE COLUMN IS ALTERED, inside one batch. The other
order works on Postgres and is asking for trouble on SQLite, where the table
rebuild would carry the unique index forward onto the new table and then be
asked to drop it from a table that has just been replaced underneath it.

DOWN_REVISION IS e1b7d4c92f08, the single head, verified by reading every file
in the versions directory rather than assumed. This repo has already had one
two-head incident (see the re-parenting of b2e6d90a3f14 onto a1c5e8b30f7d): two
branches open at once both wrote themselves off the same parent, and
`upgrade head` then raises "Multiple head revisions are present" on main and on
neither branch. Worth re-checking at merge time if anything else lands first.

The downgrade reverses exactly this and nothing else: the column goes back to
NOT NULL and the unique index comes back under its original name. It will fail
on a database that has accepted registrations since the upgrade, because those
rows have no phone number and no value can be invented for them. That is the
honest behaviour for a downgrade that cannot be honestly performed, and it is
better than inventing placeholder numbers that would then collide on the unique
index it is trying to restore.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3c0a84e17d9'
down_revision: Union[str, None] = 'e1b7d4c92f08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exactly the name the baseline created (5f3a9c80d26f, via batch_op.f) and
# exactly what SQLAlchemy derives from index=True on User.phone, so the
# migrated and the create_all databases agree about what is being dropped.
IX_USERS_PHONE = 'ix_users_phone'

PHONE_COLUMN = 'phone'
USERS_TABLE = 'users'


def upgrade() -> None:
    # batch_alter_table because SQLite cannot alter a column in place. Unlike
    # e1b7d4c92f08, which only created an index and so issued plain DDL, this
    # batch really does rebuild the table on SQLite.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.drop_index(IX_USERS_PHONE)
        batch_op.alter_column(
            PHONE_COLUMN,
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.alter_column(
            PHONE_COLUMN,
            existing_type=sa.String(),
            nullable=False,
        )
        batch_op.create_index(IX_USERS_PHONE, [PHONE_COLUMN], unique=True)
