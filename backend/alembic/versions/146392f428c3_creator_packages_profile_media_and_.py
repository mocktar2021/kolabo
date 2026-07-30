"""creator packages, profile media and fields

Revision ID: 146392f428c3
Revises: 5f3a9c80d26f
Create Date: 2026-07-30 10:21:06.690402
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '146392f428c3'
down_revision: Union[str, None] = '5f3a9c80d26f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('media_assets',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('owner_user_id', sa.String(), nullable=False),
    sa.Column('content_type', sa.String(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_media_assets_owner_user_id'), ['owner_user_id'], unique=False)

    op.create_table('packages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('platform', sa.String(), nullable=False),
    sa.Column('deliverable_type', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price_amount', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('packages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_packages_user_id'), ['user_id'], unique=False)

    op.create_table('portfolio_items',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('media_id', sa.String(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['media_id'], ['media_assets.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('portfolio_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_items_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('headline', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('location', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('avatar_media_id', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('influencer_profiles', schema=None) as batch_op:
        batch_op.drop_column('avatar_media_id')
        batch_op.drop_column('location')
        batch_op.drop_column('headline')
        batch_op.drop_column('display_name')

    with op.batch_alter_table('portfolio_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_items_user_id'))

    op.drop_table('portfolio_items')
    with op.batch_alter_table('packages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_packages_user_id'))

    op.drop_table('packages')
    with op.batch_alter_table('media_assets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_media_assets_owner_user_id'))

    op.drop_table('media_assets')
