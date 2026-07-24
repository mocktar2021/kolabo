"""initial schema

Revision ID: 5f3a9c80d26f
Revises:
Create Date: 2026-07-24 09:01:00.499854
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f3a9c80d26f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admin_action_logs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('admin_id', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('target_type', sa.String(), nullable=False),
    sa.Column('target_id', sa.String(), nullable=False),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('country_configs',
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('phone_prefix', sa.String(), nullable=False),
    sa.Column('phone_example', sa.String(), nullable=True),
    sa.Column('mobile_money_provider', sa.String(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('country_code', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_phone'), ['phone'], unique=True)

    op.create_table('business_profiles',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('company_name', sa.String(), nullable=False),
    sa.Column('industry', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('campaigns',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('business_user_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('budget_amount', sa.Integer(), nullable=True),
    sa.Column('budget_currency', sa.String(), nullable=True),
    sa.Column('deliverables', sa.JSON(), nullable=False),
    sa.Column('deadline', sa.Date(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['business_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaigns_business_user_id'), ['business_user_id'], unique=False)

    op.create_table('favorites',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('business_user_id', sa.String(), nullable=False),
    sa.Column('influencer_user_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['business_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['influencer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_user_id', 'influencer_user_id', name='uq_favorite')
    )
    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_favorites_business_user_id'), ['business_user_id'], unique=False)

    op.create_table('influencer_profiles',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('categories', sa.JSON(), nullable=False),
    sa.Column('rate_card', sa.JSON(), nullable=False),
    sa.Column('follower_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('notification_preferences',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('muted_types', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('notifications',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)

    op.create_table('reports',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('reporter_user_id', sa.String(), nullable=False),
    sa.Column('target_type', sa.String(), nullable=False),
    sa.Column('target_id', sa.String(), nullable=False),
    sa.Column('reason_code', sa.String(), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('reviewer_id', sa.String(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['reporter_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('social_accounts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('platform', sa.String(), nullable=False),
    sa.Column('handle', sa.String(), nullable=False),
    sa.Column('method', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('proof_url', sa.String(), nullable=True),
    sa.Column('reviewer_id', sa.String(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('verification_documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('doc_type', sa.String(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('ciphertext', sa.LargeBinary(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('rejection_reason', sa.String(), nullable=True),
    sa.Column('reviewer_id', sa.String(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_invitations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('influencer_user_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['influencer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaign_invitations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaign_invitations_campaign_id'), ['campaign_id'], unique=False)

    op.create_table('messages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('sender_user_id', sa.String(), nullable=False),
    sa.Column('recipient_user_id', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messages_campaign_id'), ['campaign_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_messages_created_at'), ['created_at'], unique=False)

    op.create_table('proposals',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('influencer_user_id', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('rate_amount', sa.Integer(), nullable=False),
    sa.Column('rate_currency', sa.String(), nullable=False),
    sa.Column('timeline_days', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['influencer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_proposals_campaign_id'), ['campaign_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_proposals_influencer_user_id'), ['influencer_user_id'], unique=False)

    op.create_table('contracts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('proposal_id', sa.String(), nullable=False),
    sa.Column('business_user_id', sa.String(), nullable=False),
    sa.Column('influencer_user_id', sa.String(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('rate_amount', sa.Integer(), nullable=False),
    sa.Column('rate_currency', sa.String(), nullable=False),
    sa.Column('timeline_days', sa.Integer(), nullable=False),
    sa.Column('deliverables', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('business_signature', sa.String(), nullable=True),
    sa.Column('business_signed_at', sa.DateTime(), nullable=True),
    sa.Column('influencer_signature', sa.String(), nullable=True),
    sa.Column('influencer_signed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['business_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['influencer_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proposal_id')
    )
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contracts_campaign_id'), ['campaign_id'], unique=False)

    op.create_table('contract_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('contract_id', sa.String(), nullable=False),
    sa.Column('actor_user_id', sa.String(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('contract_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contract_events_contract_id'), ['contract_id'], unique=False)

    op.create_table('escrows',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('contract_id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('business_user_id', sa.String(), nullable=False),
    sa.Column('influencer_user_id', sa.String(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('commission_amount', sa.Integer(), nullable=True),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('provider_fund_ref', sa.String(), nullable=False),
    sa.Column('provider_payout_ref', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('held_at', sa.DateTime(), nullable=False),
    sa.Column('due_release_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['business_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
    sa.ForeignKeyConstraint(['influencer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('contract_id')
    )
    op.create_table('escrow_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('escrow_id', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['escrow_id'], ['escrows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('escrow_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_escrow_events_escrow_id'), ['escrow_id'], unique=False)

    op.create_table('reviews',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('escrow_id', sa.String(), nullable=False),
    sa.Column('campaign_id', sa.String(), nullable=False),
    sa.Column('reviewer_user_id', sa.String(), nullable=False),
    sa.Column('reviewee_user_id', sa.String(), nullable=False),
    sa.Column('stars', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('revealed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['escrow_id'], ['escrows.id'], ),
    sa.ForeignKeyConstraint(['reviewee_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('escrow_id', 'reviewer_user_id', name='uq_review_per_reviewer')
    )
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reviews_escrow_id'), ['escrow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reviews_reviewee_user_id'), ['reviewee_user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('reviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reviews_reviewee_user_id'))
        batch_op.drop_index(batch_op.f('ix_reviews_escrow_id'))

    op.drop_table('reviews')
    with op.batch_alter_table('escrow_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_escrow_events_escrow_id'))

    op.drop_table('escrow_events')
    op.drop_table('escrows')
    with op.batch_alter_table('contract_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contract_events_contract_id'))

    op.drop_table('contract_events')
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contracts_campaign_id'))

    op.drop_table('contracts')
    with op.batch_alter_table('proposals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_proposals_influencer_user_id'))
        batch_op.drop_index(batch_op.f('ix_proposals_campaign_id'))

    op.drop_table('proposals')
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_messages_created_at'))
        batch_op.drop_index(batch_op.f('ix_messages_campaign_id'))

    op.drop_table('messages')
    with op.batch_alter_table('campaign_invitations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_invitations_campaign_id'))

    op.drop_table('campaign_invitations')
    op.drop_table('verification_documents')
    op.drop_table('social_accounts')
    op.drop_table('reports')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))

    op.drop_table('notifications')
    op.drop_table('notification_preferences')
    op.drop_table('influencer_profiles')
    with op.batch_alter_table('favorites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_favorites_business_user_id'))

    op.drop_table('favorites')
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaigns_business_user_id'))

    op.drop_table('campaigns')
    op.drop_table('business_profiles')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_phone'))

    op.drop_table('users')
    op.drop_table('country_configs')
    op.drop_table('admin_action_logs')
