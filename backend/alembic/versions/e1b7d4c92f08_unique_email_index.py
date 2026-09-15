"""unique index on users.email

Revision ID: e1b7d4c92f08
Revises: d7b3f1a90c46
Create Date: 2026-09-15

One index, and it is the point at which an email address stops being a note
attached to an account and starts being an identity.

users.email HAS EXISTED SINCE THE BASELINE (5f3a9c80d26f) AND NOTHING HAS EVER
WRITTEN TO IT. It was declared nullable, with no index and no unique
constraint, and no code path anywhere in the application ever set a value. That
is what makes this migration cheap: a UNIQUE index over a column holding
nothing but nulls cannot collide with data that is already there, and there is
no backfill to get wrong.

WHAT THE CONSTRAINT BUYS is the one property the API layer cannot provide on
its own: that no two accounts share an address. A service that SELECTs by email
and then INSERTs has a window between the two, and two registrations racing
through that window both pass the check and both write. Only the database can
refuse the second one. The index is the read path as well, because every login
and every "is this address already taken" answer starts from a lookup by email,
and a sequential scan of a growing users table is not an answer anyone should
be made to wait for.

THE COLUMN STAYS NULLABLE, DELIBERATELY, AND A REVIEWER SHOULD NOT "FIX" IT BY
ADDING NOT NULL HERE. 49 of the 60 backend test files construct User(phone=...)
with no email at all, so a NOT NULL email would fail at flush in 49 files at
once, and every one of those failures would be in a fixture rather than in
anything this change is about. Postgres permits multiple nulls under a unique
index, so the constraint that actually matters is real either way: two accounts
still cannot share an address, and a row carrying no address is simply not in
the running for one. PRESENCE IS ENFORCED IN THE API LAYER, where the request
that supplies the address lives and where a missing one can be reported to the
person who failed to supply it. Making the column NOT NULL is left to a later
cleanup revision, once the fixtures carry an email.

THE INDEX NAME IS NOT ARBITRARY. ix_users_email is exactly what SQLAlchemy
derives from unique=True, index=True on User.email, so a database built by
`alembic upgrade head` and one built by create_all at app startup agree on it,
rather than differing by a name nobody would notice until a later revision
tried to drop one of them. ix_users_phone and ix_users_referral_code were named
the same way and for the same reason.

IT IS A NAMED MODULE CONSTANT because SQLite cannot alter constraints in place.
A later batch_alter_table on users copies the table, rebuilds it from the
reflected schema and swaps it in; that rebuild re-declares every constraint,
and alembic cannot reconstruct one it cannot name ("Constraint must have a
name"). c3f7a1d9e08b wrote that rule down after CI failed on an anonymous one,
and a3f8b1c47d20, e2f9c4a71d38, c9a4e7b21f36 and d7b3f1a90c46 restated it.
b8d4f6a2c9e1 is the precedent on this table specifically.

NO INSPECTOR GUARD, unlike c9a4e7b21f36, f8a1c3d20e5b and d7b3f1a90c46. Those
revisions had to look before touching anything, because the OBJECTS THEY CREATE
can also be built by create_all at app startup, which runs AFTER
`alembic upgrade head` in the container command, so a deployment that has
already booted once presents them before the migration reaches them. users is
not in that position: it has belonged to alembic since the baseline, and
create_all does not add an index to a table it finds already present. This is
the same reasoning b5d2e9f31a04 set out for the columns it added to campaigns.

DOWN_REVISION IS d7b3f1a90c46, the single head, verified by reading every file
in the versions directory rather than assumed. This repo has already had one
two-head incident (see the re-parenting of b2e6d90a3f14 onto a1c5e8b30f7d):
two branches open at once both wrote themselves off the same parent, and
`upgrade head` then raises "Multiple head revisions are present" on main and on
neither branch. Worth re-checking at merge time if anything else lands first.

The downgrade drops exactly what the upgrade added: the index, and nothing
else. The column predates this revision and outlives it.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e1b7d4c92f08'
down_revision: Union[str, None] = 'd7b3f1a90c46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches the name SQLAlchemy derives from User.email's unique=True,
# index=True — one UNIQUE index, not an index plus a separate constraint.
IX_USERS_EMAIL = 'ix_users_email'


def upgrade() -> None:
    # batch_alter_table because SQLite cannot alter a table in place. With
    # nothing in the batch but a create_index, alembic issues a plain
    # CREATE UNIQUE INDEX and does not rebuild the table.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(IX_USERS_EMAIL, ['email'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(IX_USERS_EMAIL)
