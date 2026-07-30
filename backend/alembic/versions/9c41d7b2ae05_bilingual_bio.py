"""bilingual bio and generation counter

Adds bio_fr and bio_en alongside the existing bio, and backfills each row into
the column matching the language of the creator's country. The old bio column
is deliberately left in place: the backfill is a heuristic (a Beninese creator
could still have written in English) and dropping the source in the same
migration would make that unrecoverable. It is removed in a later migration
once the split has been checked against real data.

Revision ID: 9c41d7b2ae05
Revises: 7f742eefddc6
Create Date: 2026-07-30 19:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c41d7b2ae05'
down_revision: Union[str, None] = '7f742eefddc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app.core.country_config. Duplicated on purpose: a migration must keep
# working even after the application constant changes, so it records the
# mapping as it was the day the data moved.
ENGLISH_COUNTRIES = ("GH", "NG")


def upgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bio_fr', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('bio_en', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('bio_generations', sa.Integer(), nullable=False, server_default='0'))

    codes = ", ".join(f"'{c}'" for c in ENGLISH_COUNTRIES)
    # Anglophone countries into bio_en, everyone else into bio_fr.
    op.execute(f"""
        UPDATE influencer_profiles SET bio_en = bio
        WHERE bio IS NOT NULL AND user_id IN (
            SELECT id FROM users WHERE country_code IN ({codes})
        )
    """)
    op.execute(f"""
        UPDATE influencer_profiles SET bio_fr = bio
        WHERE bio IS NOT NULL AND user_id NOT IN (
            SELECT id FROM users WHERE country_code IN ({codes})
        )
    """)

    # The default existed only to fill existing rows; new rows get their value
    # from the model.
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.alter_column('bio_generations', server_default=None)


def downgrade() -> None:
    # bio was never cleared, so nothing needs restoring into it.
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.drop_column('bio_generations')
        batch_op.drop_column('bio_en')
        batch_op.drop_column('bio_fr')
