"""creator referral codes

Users gain a shareable referral_code (unique, minted lazily the first time the
owner asks for it) and referred_by_user_id, a self-referencing FK recording who
brought them in. MVP scope: codes and attribution only — reward mechanics are
a later business decision, so nothing here touches money.

batch_alter_table throughout because SQLite cannot add a FK column in place: it
copies the table, rebuilds it with the new schema and swaps it in. That rebuild
re-declares every constraint, so the foreign key has to be NAMED — an inline
sa.ForeignKey() is anonymous and alembic cannot reconstruct what it cannot name
("Constraint must have a name"). Hence the column is added plain and the
constraint created explicitly below.

Revision ID: b8d4f6a2c9e1
Revises: e7c3a9d15b42
Create Date: 2026-07-31 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d4f6a2c9e1'
down_revision: Union[str, None] = 'e7c3a9d15b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_REFERRED_BY = 'fk_users_referred_by_user_id'


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('referral_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('referred_by_user_id', sa.String(), nullable=True))
        batch_op.create_foreign_key(FK_REFERRED_BY, 'users', ['referred_by_user_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_users_referral_code'), ['referral_code'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_referral_code'))
        batch_op.drop_constraint(FK_REFERRED_BY, type_='foreignkey')
        batch_op.drop_column('referred_by_user_id')
        batch_op.drop_column('referral_code')
