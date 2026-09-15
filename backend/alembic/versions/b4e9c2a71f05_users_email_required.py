"""users.email becomes NOT NULL

Revision ID: b4e9c2a71f05
Revises: f3c0a84e17d9
Create Date: 2026-09-15

The last of the three revisions that moved the login identity from the phone
number to the email address, and the one e1b7d4c92f08 promised. That revision
gave users.email a unique index and deliberately left the column nullable,
because at the time almost every backend test file built a User with a phone
and no address at all; it recorded that NOT NULL was "left to a later cleanup
revision, once the fixtures carry an email". The fixtures carry one now, so
this is that revision.

WHAT THE CONSTRAINT ADDS, GIVEN THE UNIQUE INDEX IS ALREADY THERE. Uniqueness
says no two accounts may be the same mailbox. It says nothing about an account
having a mailbox at all, because Postgres and SQLite both allow any number of
rows to sit under a unique index with a null in the indexed column. So until
now the schema permitted an account that cannot be logged in to, cannot be
sent a verification code and cannot reset its password, and the only thing
between the product and such a row was a check in the service layer. The
service layer is the right place to REPORT a missing address to the person who
failed to supply one. It is not a place that can promise the address is there,
because two requests racing through the gap between a SELECT and an INSERT
both pass it. The column can promise it, and from here it does.

WHAT HAPPENS TO A ROW THAT ALREADY HOLDS A NULL EMAIL: THIS MIGRATION REFUSES
TO RUN. It counts them first, and if the count is not zero it raises before it
alters anything, naming how many rows are involved. Nothing is written, the
revision does not stamp, and the database is left exactly as it was found.

  That is deliberate, and it is the whole reason the count exists. The obvious
  alternative is to fabricate an address for each orphan row, something shaped
  like user-<id>@invalid, and it is wrong twice over. It would be a lie in a
  column the product uses to REACH a person: a password reset sent there goes
  nowhere, and the account is locked out with nothing to show that anything
  was ever wrong. It would also be unique, so the constraint would report
  success over precisely the rows it was added to find. A migration that
  cannot honestly do its job should stop and say so, which is the position
  f3c0a84e17d9 already took about its own downgrade.

  WHAT AN OPERATOR DOES ABOUT SUCH A ROW IS A DECISION, NOT A COMMAND, which
  is why this file does not make it. Every one of them is an account created
  before registration began asking for an address. Either somebody knows the
  address and writes it in, or the account is genuinely unreachable and its
  fate belongs to whoever owns the data rather than to a migration. The
  development database this lands against is being rebuilt from empty, where
  the count is zero and the check costs one query.

TWO PLACES IN THE APPLICATION STILL READ THIS COLUMN DEFENSIVELY, and after
this revision both are belt and braces rather than live cases:
notifications/service.py::notify sends no email when the address is falsy, and
payments/service.py falls back to the phone and then to an empty string when
naming the payer to the mock provider. Neither is wrong and neither is touched
here. What changes is that the state they guard against can no longer be
reached through the database.

NO INSPECTOR GUARD, for the reason e1b7d4c92f08 and f3c0a84e17d9 both give
about this same table: users has belonged to alembic since the baseline
(5f3a9c80d26f), and create_all at app startup does not alter a table it finds
already present. The guards in c9a4e7b21f36, f8a1c3d20e5b and d7b3f1a90c46 are
there because the OBJECTS THOSE REVISIONS CREATE can also be built by
create_all, which runs after `alembic upgrade head` in the container command,
so a deployment that has already booted once presents them before the
migration reaches them. Nothing here creates anything.

THE TABLE AND COLUMN ARE NAMED AS MODULE LEVEL CONSTANTS, and the reason is
the same one e1b7d4c92f08 and f3c0a84e17d9 set out at length: SQLite cannot
alter a column in place, so the batch_alter_table below genuinely rebuilds the
users table, reflecting the schema, creating a new table from it, copying the
rows and swapping it in. That rebuild re-declares every constraint on the
table and alembic cannot reconstruct one it cannot name ("Constraint must have
a name"), the rule c3f7a1d9e08b wrote down after CI failed on an anonymous one
and a3f8b1c47d20, e2f9c4a71d38, c9a4e7b21f36, d7b3f1a90c46, e1b7d4c92f08 and
f3c0a84e17d9 have restated since. ix_users_email and ix_users_referral_code
are carried through that rebuild under the names the baseline gave them. This
revision names no index of its own, because it drops and creates none: an
unused constant for an index nothing here touches would be one more name to
keep in step with a column it does not describe.

DOWN_REVISION IS f3c0a84e17d9, the single head, verified by reading every file
in the versions directory rather than assumed. This repo has already had one
two-head incident (see the re-parenting of b2e6d90a3f14 onto a1c5e8b30f7d):
two branches open at once both wrote themselves off the same parent, and
`upgrade head` then raises "Multiple head revisions are present" on main and
on neither branch. Worth re-checking at merge time if anything else lands
first.

The downgrade reverses exactly this and nothing else: the column goes back to
nullable. Unlike f3c0a84e17d9's, it always succeeds, because widening a column
can never conflict with data already sitting in it. The unique index is left
alone in both directions; it predates this revision and outlives it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4e9c2a71f05'
down_revision: Union[str, None] = 'f3c0a84e17d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USERS_TABLE = 'users'
EMAIL_COLUMN = 'email'

# What the refusal says. Its own constant because it is read by whoever is
# running the deployment, at the moment it stops, and it has to carry the
# whole decision on its own: a sentence that long inside a raise is a sentence
# nobody keeps up to date.
NULL_EMAIL_REFUSAL = (
    "Cannot make {table}.{column} NOT NULL: {count} row(s) still have no "
    "address. This revision will not invent one, because a fabricated address "
    "is a mailbox nobody reads and would hide the very accounts it was added "
    "to find. Decide what each row should be, either writing in the address if "
    "it is known or removing the account if it is not, then run the upgrade "
    "again. Nothing has been changed."
)


def _null_email_count(bind) -> int:
    return bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {USERS_TABLE} WHERE {EMAIL_COLUMN} IS NULL")
    ).scalar()


def upgrade() -> None:
    # Counted and refused BEFORE the batch opens, so a database that still has
    # addressless accounts is left untouched rather than half rebuilt.
    orphans = _null_email_count(op.get_bind())
    if orphans:
        raise RuntimeError(
            NULL_EMAIL_REFUSAL.format(
                table=USERS_TABLE, column=EMAIL_COLUMN, count=orphans
            )
        )

    # batch_alter_table because SQLite cannot alter a column in place. As in
    # f3c0a84e17d9, and unlike e1b7d4c92f08 which only issued a CREATE INDEX,
    # this batch really does rebuild the table.
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.alter_column(
            EMAIL_COLUMN,
            existing_type=sa.String(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table(USERS_TABLE, schema=None) as batch_op:
        batch_op.alter_column(
            EMAIL_COLUMN,
            existing_type=sa.String(),
            nullable=True,
        )
