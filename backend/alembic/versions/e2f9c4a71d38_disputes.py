"""disputes, their thread and their evidence

Three tables. `disputes` is one disagreement over one escrow — escrow_id is
UNIQUE, so "one dispute per escrow" is a database fact rather than a race the
service hopes to win. `dispute_messages` is the thread the two parties settle
it in during the response window. `dispute_attachments` is the evidence, and
it points at media_assets rather than carrying bytes: the image upload,
the owner column and the serving route already exist, and a second image store
would be a second thing to move to object storage later for the same JPEGs.

EVERY CONSTRAINT IS NAMED, foreign keys included. SQLite cannot alter
constraints in place, so any later batch_alter_table on these tables copies
them, rebuilds them from the reflected schema and swaps them in; that rebuild
re-declares every constraint and alembic cannot reconstruct one it cannot name
("Constraint must have a name"). c3f7a1d9e08b wrote this rule down after CI
failed on an anonymous one, and f1a7c9d2e4b8 restated it. A table created with
anonymous constraints only fails later, when someone else is adding a column.

dispute_attachments.message_id is nullable on purpose: NULL means the image
came with the opening statement, a value means it came with a later message.
One table for both, because an admin reading the case wants the evidence in
arrival order and not split across two queries.

Revision ID: e2f9c4a71d38
Revises: a4c8e2f60b19
Create Date: 2026-08-04 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f9c4a71d38'
down_revision: Union[str, None] = 'a4c8e2f60b19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_DISPUTES = 'pk_disputes'
UQ_DISPUTES_ESCROW = 'uq_disputes_escrow_id'
FK_DISPUTES_ESCROW = 'fk_disputes_escrow_id'
FK_DISPUTES_OPENED_BY = 'fk_disputes_opened_by_user_id'

PK_MESSAGES = 'pk_dispute_messages'
FK_MESSAGES_DISPUTE = 'fk_dispute_messages_dispute_id'
FK_MESSAGES_AUTHOR = 'fk_dispute_messages_author_user_id'
IX_MESSAGES_DISPUTE = 'ix_dispute_messages_dispute_id'

PK_ATTACHMENTS = 'pk_dispute_attachments'
FK_ATTACHMENTS_DISPUTE = 'fk_dispute_attachments_dispute_id'
FK_ATTACHMENTS_MESSAGE = 'fk_dispute_attachments_message_id'
FK_ATTACHMENTS_MEDIA = 'fk_dispute_attachments_media_id'
IX_ATTACHMENTS_DISPUTE = 'ix_dispute_attachments_dispute_id'


def upgrade() -> None:
    op.create_table(
        'disputes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('escrow_id', sa.String(), nullable=False),
        sa.Column('opened_by_user_id', sa.String(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('respond_by', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('released_amount', sa.Integer(), nullable=True),
        sa.Column('refunded_amount', sa.Integer(), nullable=True),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_DISPUTES),
        sa.UniqueConstraint('escrow_id', name=UQ_DISPUTES_ESCROW),
        sa.ForeignKeyConstraint(['escrow_id'], ['escrows.id'], name=FK_DISPUTES_ESCROW),
        sa.ForeignKeyConstraint(['opened_by_user_id'], ['users.id'], name=FK_DISPUTES_OPENED_BY),
    )

    op.create_table(
        'dispute_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('dispute_id', sa.String(), nullable=False),
        sa.Column('author_user_id', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_MESSAGES),
        sa.ForeignKeyConstraint(['dispute_id'], ['disputes.id'], name=FK_MESSAGES_DISPUTE),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], name=FK_MESSAGES_AUTHOR),
    )
    op.create_index(IX_MESSAGES_DISPUTE, 'dispute_messages', ['dispute_id'], unique=False)

    # After dispute_messages: message_id points at it.
    op.create_table(
        'dispute_attachments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('dispute_id', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('media_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_ATTACHMENTS),
        sa.ForeignKeyConstraint(['dispute_id'], ['disputes.id'], name=FK_ATTACHMENTS_DISPUTE),
        sa.ForeignKeyConstraint(['message_id'], ['dispute_messages.id'], name=FK_ATTACHMENTS_MESSAGE),
        sa.ForeignKeyConstraint(['media_id'], ['media_assets.id'], name=FK_ATTACHMENTS_MEDIA),
    )
    op.create_index(IX_ATTACHMENTS_DISPUTE, 'dispute_attachments', ['dispute_id'], unique=False)


def downgrade() -> None:
    op.drop_index(IX_ATTACHMENTS_DISPUTE, table_name='dispute_attachments')
    op.drop_table('dispute_attachments')
    op.drop_index(IX_MESSAGES_DISPUTE, table_name='dispute_messages')
    op.drop_table('dispute_messages')
    op.drop_table('disputes')
