"""drop every stored identity document

Revision ID: b1d7e3a05c92
Revises: a7f1c6e3d940
Create Date: 2026-10-05

THE FIRST DESTRUCTIVE MIGRATION IN THIS REPOSITORY. Every other one adds,
reshapes or backfills; this one removes rows and nothing recreates them. Read
the whole docstring before running it anywhere whose contents matter.

WHY. On 3 October 2026 the founder decided that Kolabo collects no personal
identity document. The change beside this one narrows
profiles.service.DOC_TYPES to business_registration, which closes the door.
This empties the room. Doing only the first would leave us holding other
people's identity papers under a policy that says we hold none, which is worse
than never having taken them.

WHAT IT TOUCHES. Rows in verification_documents whose doc_type is exactly
'identity'. Nothing else. business_registration rows are the live half of this
feature: they are counted, not read, and not deleted.

'identity' IS WRITTEN OUT RATHER THAN IMPORTED, for the reason 9c41d7b2ae05
gives for duplicating the country list: a migration records the world as it was
the day the data moved and has to keep working after the application constant
changes. Importing DOC_TYPES would make this file mean "delete whatever we no
longer accept", which is a different instruction and a far more dangerous one.

IT CANNOT BE UNDONE. The rows hold Fernet ciphertext and nothing else in the
system keeps a copy, so downgrade() restores nothing and says so rather than
pretending. Take a dump first if you are running this against anything you
would miss.

WHAT WAS THERE WHEN THIS WAS WRITTEN. No real users, and no production database
at all: the production box was bought on 3 October and is still empty. On the
development box this is expected to remove a handful of test rows or none. The
count is printed rather than assumed, so whoever runs it ends up with a number.

WHAT THIS DOES NOT REACH, stated so nobody assumes otherwise. Notifications
already sent about an identity document keep their text, and that text
interpolates the raw doc_type, so a creator's notification history can still
read "your identity document was approved". Whether those should be rewritten
is an open question on KOL-122 and is deliberately not answered here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1d7e3a05c92'
down_revision: Union[str, None] = 'a7f1c6e3d940'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Both written out on purpose. See the docstring.
TABLE = 'verification_documents'
IDENTITY = 'identity'


def upgrade() -> None:
    bind = op.get_bind()
    found = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE doc_type = :doc_type"),
        {"doc_type": IDENTITY},
    ).scalar()
    # Printed rather than logged: this runs from `alembic upgrade head` in the
    # backend container's start command, where stdout is the deploy log and is
    # the only place anybody will look for it.
    print(f"b1d7e3a05c92: deleting {found} identity document row(s) from {TABLE}")
    bind.execute(
        sa.text(f"DELETE FROM {TABLE} WHERE doc_type = :doc_type"),
        {"doc_type": IDENTITY},
    )


def downgrade() -> None:
    # Nothing to restore, and that is the honest implementation rather than a
    # missing one. The deleted rows held encrypted bytes with no copy anywhere,
    # so a downgrade that recreated empty rows would be a lie and one that
    # raised would block test_migrations.py from reversing the schema.
    pass
