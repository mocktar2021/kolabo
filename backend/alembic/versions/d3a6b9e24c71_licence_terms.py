"""content licence terms on campaigns, proposals and contracts

Three nullable JSON columns, no backfill. This is what lets the parties answer
Article 10 of the approved collaboration model before a contract is written.

WHY. Article 10 of claude/kolabo-contrat-collaboration-modele-fr.md makes the
Parties retain one of three options for how the Entreprise may use the Travaux,
and leaves "Option retenue : [ 1 / 2 / 3 ]" to be filled in per contract:

    Option 1  Diffusion par le Createur seul. No redistribution right.
    Option 2  Licence de rediffusion, for a stated duration, on stated
              territories, on stated media, paid advertising included.
    Option 3  Cession des droits patrimoniaux, for a stated duration and
              territories, with a separate consideration possibly agreed.

Nothing in this database could fill that in. There is no column anywhere
recording which option was agreed, and none for the duration, territories,
media or consideration the second and third options depend on, so every
generated contract carried an unanswered choice at the heart of it. The
founder decided that the BRAND states the option before the contract exists,
that all three stay on offer, and that Kolabo captures it. These columns hold
what it states.

TWO CAPTURE HOMES AND ONE SNAPSHOT, which is the split c8e2a5f71b30 directly
below this revision already made for party details.

campaigns.licence_terms is the brief's. A brand writing a brief states its
licence there, beside the budget and the deliverables, because that is part of
what a creator prices against: option 2 is worth a different number from
option 1, and a creator who cannot see which one is on offer is pricing blind.

proposals.licence_terms is the direct order's. On an order the brand's offer IS
the proposal row (author_role business, written by
campaigns.service._place_order), so its stated terms belong on that row, and a
later version in the same chain carries the block forward exactly as it already
carries expires_at. A creator never writes it on either path.

contracts.licence_terms is the copy taken at generation and never rewritten:
not on a later edit of the brief, not at signature, not at cancellation. A
brand that changes its mind changes what the NEXT contract says and nothing at
all about one that already exists. That is the rule this schema already applies
to money, for the reason PaymentIntent's docstring gives: a join would settle
the new number against the old payment, and with licence terms a join would
restate what a signed document permits.

WHY JSON RATHER THAN SCALAR COLUMNS. The same two reasons c8e2a5f71b30 gives,
and the same exception campaigns.deliverables established. NOTHING JOINS ON A
LICENCE BLOCK: it is read whole, for one campaign or one contract at a time, by
a renderer and by a human, and it is never filtered, grouped or summed, which
is also why no index is created below. And it has a VARIABLE SHAPE by option:
option 1 states nothing beyond the choice, option 2 states three further
fields, option 3 states two plus one optional. The scalar version of that is
five mostly null columns and a discriminator saying which of them mean
anything.

NULLABLE EVERYWHERE, NO BACKFILL, AND NONE IS POSSIBLE. A licence is something
the parties state. A migration that wrote a default option into existing rows
would be a migration deciding how a brand may use a creator's work, which is
the one thing it must not do, and the conservative-looking choice is not
neutral either: option 1 recorded against a brief whose brand meant to
redistribute is a statement nobody made. So null means "nobody has stated a
licence here", and contracts/service.py refuses to generate from it with
contract_licence_terms_missing rather than guessing. There are no real users
yet and the production box carries no rows, so in practice this fills nothing.

NO CONSTRAINT IS INTRODUCED. sa.JSON() emits none, so nothing anonymous is
created on any of the three tables. The rule c3f7a1d9e08b wrote down, and
f1a7c9d2e4b8, e2f9c4a71d38 and c8e2a5f71b30 restated, holds for these tables
too: ANY CONSTRAINT ADDED TO THEM LATER MUST BE NAMED, because the batch
rebuild re-declares the whole table and alembic cannot reconstruct a constraint
it cannot name.

The shape of a block is enforced in app/modules/campaigns/licence.py and
documented at the three model columns, which is where a shape belongs. A CHECK
constraint over JSON would be unenforceable on SQLite and unreadable on both
backends.

No conditional guard is needed here, for the reason b5d2e9f31a04 gives: these
are columns on tables alembic has owned since the baseline, and add_column on
an existing table is not a state create_all can leave behind for a database
that has run every migration.

Revision ID: d3a6b9e24c71
Revises: c8e2a5f71b30
Create Date: 2026-10-23 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3a6b9e24c71'
down_revision: Union[str, None] = 'c8e2a5f71b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The brief's licence, which a creator reads before pricing.
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('licence_terms', sa.JSON(), nullable=True))

    # The direct order's, which is the brand's own offer row. Same column name
    # as on campaigns on purpose: one block, one shape, one reader, whichever
    # record a particular deal stated it on.
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('licence_terms', sa.JSON(), nullable=True))

    # The snapshot, beside the two party blocks c8e2a5f71b30 added.
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('licence_terms', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Reverse order of upgrade, and a real reversal rather than a pass. The
    # contract's copy is the one thing here that is recorded nowhere else: the
    # brief or the order it was taken from stays editable, so dropping the
    # snapshot loses its independence from a later edit. That is the same
    # trade-off c8e2a5f71b30 makes about party details and states out loud,
    # and it is a different thing from b1d7e3a05c92, which genuinely cannot be
    # undone and says so.
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_column('licence_terms')

    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_column('licence_terms')

    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('licence_terms')
