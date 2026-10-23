"""party details on profiles, party snapshot and body hash on contracts

Six nullable columns across three tables, no backfill. This is what lets a
generated contract say WHO signed it.

WHY. A contract generated today names its parties like this, in the stored
body:

    Business party (user id): 0f3c8a1e-...
    Influencer party (user id): 9b21d7f4-...

That is the whole of it, and the data to write anything better has never been
collected. A business profile holds one free text company_name, overwritten
whole on every save. A creator profile holds a nullable display_name that
enrichment sometimes writes from whatever a social platform's API returned, so
it may be a handle rather than a name. No legal form, no registration number,
no tax identifier, no address and no representative, on either side. The
signature columns therefore validate against nothing: there is no legal name in
this database to compare a signature to. The spec for this change is
claude/kolabo-contract-parties-spec.md, sections 3 and 9.

THIS IS NOT IDENTITY VERIFICATION AND MUST NEVER BE PRESENTED AS ANY. Decided
3 October 2026: Kolabo collects no personal identity document, and b1d7e3a05c92
directly below this revision is what emptied the store of the ones it held. A
party block is self declared contract content, exactly as it would be on paper.
The platform records what each party states about itself and checks none of it,
so nothing here earns a badge and no column is named as though it had been
checked.

WHY JSON RATHER THAN SCALAR COLUMNS, which is what the rest of this schema
would lead you to expect. The convention in this repo is scalar columns copied
inline with no foreign key back to the source, used at four hops from Package
through Campaign to Contract to PaymentIntent, and it is the right convention
wherever something joins or aggregates on the value. Nothing joins on a party
block. It is read whole, for one contract at a time, by a renderer and by a
human; it is never filtered, grouped or summed, which is also why no index is
created for it below. It has a VARIABLE SHAPE as well: a registered company
states a legal form, a registration number and a representative, a sole trader
states none of the three. The scalar version of this is eleven mostly null
columns plus a discriminator saying which of them mean anything.
campaigns.deliverables is the documented exception for exactly this reason
("nothing joins on them: they are read whole, for one campaign at a time") and
this is the second one.

TWO HOMES, AND THEY ARE NOT A DUPLICATE OF ONE ANOTHER.

business_profiles.party_details and influencer_profiles.party_details hold a
user's CURRENT details. They are a convenience default so nobody retypes an
address for every contract, and they stay editable at any time.

contracts.business_party and contracts.influencer_party hold the SNAPSHOT taken
at generation, and are never rewritten afterwards: not on profile edit, not on
signature, not on cancellation. Editing a profile changes what the NEXT
contract says and nothing at all about one that already exists. That is the
rule this schema already applies to money. PaymentIntent copies amounts off the
contract rather than reading them through a join at settlement because "a join
would silently settle the new number against the old payment", and a join here
would restate a contract signed in October in terms of a company that
reincorporated in March.

body_sha256 AND legal_version ARE THE SIGNATURE RECORD. Columns rather than a
table, because there is exactly one of each per contract and both are written
once, at generation. body_sha256 is what lets anyone later prove the text has
not changed since it was signed. legal_version records which published Terms
were in force, because nothing in this backend stores a terms acceptance
anywhere and the legal pages' effective date is the only version marker that
exists. Both are filled by the generation path; this migration only makes room
for them.

THE IP AND USER AGENT COLUMNS FROM THE SPEC ARE DELIBERATELY ABSENT. Section 6
proposes four of them and recommends capturing them. An IP address is personal
data in most regimes including Benin's, and adding it would re-expand a data
footprint the founder narrowed on 3 October, so it is her call together with
counsel rather than something a migration decides quietly. Section 11 question
2 tracks it. If the answer is yes, that is another additive revision and
nothing here has to move.

NULLABLE EVERYWHERE, NO BACKFILL, AND NONE IS OWED. contracts has never been
altered since 5f3a9c80d26f_initial_schema.py, so this is its first migration.
Existing contract rows have nothing to backfill FROM beyond the two uuids
already written into their body, and inventing a party block for a document
somebody has signed is the one thing a migration must not do. There are no real
users yet and the production box carries no rows, so in practice this fills
nothing anywhere.

NO CONSTRAINT IS INTRODUCED. sa.JSON() and sa.String() emit none, so nothing
anonymous is created on any of the three tables. The rule c3f7a1d9e08b wrote
down, and f1a7c9d2e4b8, e2f9c4a71d38 and c9a4e7b21f36 restated, holds for these
tables too: ANY CONSTRAINT ADDED TO THEM LATER MUST BE NAMED, because the batch
rebuild re-declares the whole table and alembic cannot reconstruct a constraint
it cannot name.

The shape of a block is documented at the two model modules and asserted by
profiles/schemas.py, which is where a shape belongs. A CHECK constraint over
JSON would be unenforceable on SQLite and unreadable on both backends.

No conditional guard is needed here, for the reason b5d2e9f31a04 gives: these
are columns on tables alembic has owned since the baseline, and add_column on
an existing table is not a state create_all can leave behind for a database
that has run every migration.

Revision ID: c8e2a5f71b30
Revises: b1d7e3a05c92
Create Date: 2026-10-22 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8e2a5f71b30'
down_revision: Union[str, None] = 'b1d7e3a05c92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The profile defaults. One column each, and the SAME column name on both
    # sides on purpose: a creator block and a business block have identical
    # shape, so one renderer, one schema and one reader serve both, and the
    # gate at generation reads the same attribute whichever side it is asking
    # about.
    with op.batch_alter_table('business_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('party_details', sa.JSON(), nullable=True))

    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('party_details', sa.JSON(), nullable=True))

    # The snapshot, and the signature record beside it. Four columns in one
    # batch: they arrive together because they are all written in the same
    # instant by the same code path, and a database that has one and not the
    # others describes a contract that cannot exist.
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('business_party', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('influencer_party', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('body_sha256', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('legal_version', sa.String(), nullable=True))


def downgrade() -> None:
    # Reverse order of upgrade, and a real reversal rather than a pass: these
    # columns hold a copy of data that still exists on the profiles, so
    # dropping them loses the snapshot's independence from a later profile
    # edit but destroys no fact that is recorded nowhere else. Contrast
    # b1d7e3a05c92, which genuinely cannot be undone and says so.
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_column('legal_version')
        batch_op.drop_column('body_sha256')
        batch_op.drop_column('influencer_party')
        batch_op.drop_column('business_party')

    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.drop_column('party_details')

    with op.batch_alter_table('business_profiles', schema=None) as batch_op:
        batch_op.drop_column('party_details')
