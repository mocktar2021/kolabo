"""open briefs and targeting

Five columns on campaigns for the open board.

campaigns.is_open marks a brief that any creator may find and apply to,
rather than one that only reaches the people the buyer invited. It gets a
server_default of 'false' only to fill existing rows — every campaign written
before this column was addressed to invited creators — and then loses it, so
new rows take their value from the model. Same pattern as is_direct in
f1a7c9d2e4b8 and author_role in a9d3f5c1b647.

THE BACKFILL VALUE IS THE INTERESTING PART. False, not true, and not a guess
from the campaign's age or status. A brief that was published last month was
published under the old rule, where the only people who could see it were the
ones the brand picked; turning those into open briefs would start delivering
applications from strangers to buyers who never asked for any, against briefs
they believed were private. Opening a brief is a decision, and a migration is
not the place decisions get made on a buyer's behalf.

target_categories and target_countries are JSON lists defaulting to the empty
list, which is the honest starting value: an existing brief targeted nobody in
particular because it had no way to. They are NOT NULL like deliverables, so
the server_default fills the existing rows and is then dropped for the same
reason is_open's is. target_min_followers and target_max_followers stay
nullable with no default, because NULL is meaningful there and 0 is not — a
brief with no opinion about audience size must not read as one demanding at
least zero followers.

No constraint is introduced. sa.Boolean() emits no CHECK under SQLAlchemy 2.x
(create_constraint defaults to False) and sa.JSON() emits none either, so
nothing anonymous is created here — which matters, because the batch rebuild
re-declares the whole campaigns table and alembic cannot reconstruct a
constraint it cannot name ("Constraint must have a name"). The rule
c3f7a1d9e08b wrote down and f1a7c9d2e4b8, e2f9c4a71d38 and c9a4e7b21f36
restated stands: ANY CONSTRAINT ADDED TO campaigns LATER MUST BE NAMED.

No conditional guard is needed here, unlike c9a4e7b21f36. That revision was
conditional because create_all may already have built its TABLES; these are
columns on a table alembic has owned since the baseline, and add_column on an
existing table is not a state create_all can leave behind for a database that
has run every migration.

Revision ID: b5d2e9f31a04
Revises: c9a4e7b21f36
Create Date: 2026-08-08 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5d2e9f31a04'
down_revision: Union[str, None] = 'c9a4e7b21f36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The literal an empty JSON list is spelled as a server default. Written once
# so the two columns cannot drift into two different empty values.
EMPTY_JSON_LIST = sa.text("'[]'")


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_open', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                'target_categories', sa.JSON(), nullable=False,
                server_default=EMPTY_JSON_LIST,
            )
        )
        batch_op.add_column(
            sa.Column(
                'target_countries', sa.JSON(), nullable=False,
                server_default=EMPTY_JSON_LIST,
            )
        )
        batch_op.add_column(sa.Column('target_min_followers', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('target_max_followers', sa.Integer(), nullable=True))

    # The defaults existed only to fill existing rows; new rows get their
    # values from the model.
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.alter_column(
            'is_open',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'target_categories',
            existing_type=sa.JSON(),
            existing_nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'target_countries',
            existing_type=sa.JSON(),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('target_max_followers')
        batch_op.drop_column('target_min_followers')
        batch_op.drop_column('target_countries')
        batch_op.drop_column('target_categories')
        batch_op.drop_column('is_open')
