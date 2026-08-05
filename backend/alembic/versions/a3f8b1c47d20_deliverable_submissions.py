"""deliverable submissions and their attachments

Two tables. `deliverable_submissions` is one hand-in of completed work against
one funded contract — an immutable attempt, so "request changes" closes a row
and the creator's next hand-in is a new one. `deliverable_attachments` is the
proof, and it points at media_assets rather than carrying bytes, for the reason
dispute_attachments does: the upload, the owner column and the serving route
already exist, and a second image store would be a second thing to move to
object storage later for the same JPEGs.

NO INSPECTOR GUARD HERE, unlike f8a1c3d20e5b. That one had to check before it
touched `notifications`, because that table is owned by no migration — it comes
into existence only through create_all at APP startup, which runs AFTER
`alembic upgrade head` in the container command, so on a migration-only
database it did not exist yet at that point. These two tables are introduced
BY this migration, so the ordering runs the other way: create_table lands
first, and the create_all at startup then finds them present and does nothing.

CONTRACT_ID IS INDEXED, NOT UNIQUE, and that is the whole shape of the feature.
Unique would mean one submission ever per contract, which is exactly the thing
this design is not: work gets sent back, redone and resubmitted, and the
history of that is what an admin reads if it later becomes a dispute. The rule
is one OPEN submission at a time, which is a question about status and not
something a column can ask, so deliverables.service enforces it against the
open set. The index stays, because every read of this table starts from a
contract. e2f9c4a71d38 made the same call for disputes and explains what
getting it wrong cost.

EVERY CONSTRAINT IS NAMED, foreign keys and indexes included. SQLite cannot
alter constraints in place, so a later batch_alter_table on these tables
rebuilds them from the reflected schema, and alembic cannot reconstruct a
constraint it cannot name. c3f7a1d9e08b wrote that rule down after CI failed on
an anonymous one; e2f9c4a71d38 and f1a7c9d2e4b8 restated it. The index names
match what SQLAlchemy derives from index=True, so a migrated schema and a
create_all schema agree.

Revision ID: a3f8b1c47d20
Revises: f8a1c3d20e5b
Create Date: 2026-08-05 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f8b1c47d20'
down_revision: Union[str, None] = 'f8a1c3d20e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_SUBMISSIONS = 'pk_deliverable_submissions'
FK_SUBMISSIONS_CONTRACT = 'fk_deliverable_submissions_contract_id'
FK_SUBMISSIONS_SUBMITTED_BY = 'fk_deliverable_submissions_submitted_by_user_id'
FK_SUBMISSIONS_REVIEWED_BY = 'fk_deliverable_submissions_reviewed_by_user_id'
# Matches the name SQLAlchemy derives from DeliverableSubmission.contract_id's
# index=True.
IX_SUBMISSIONS_CONTRACT = 'ix_deliverable_submissions_contract_id'

PK_ATTACHMENTS = 'pk_deliverable_attachments'
FK_ATTACHMENTS_SUBMISSION = 'fk_deliverable_attachments_submission_id'
FK_ATTACHMENTS_MEDIA = 'fk_deliverable_attachments_media_id'
IX_ATTACHMENTS_SUBMISSION = 'ix_deliverable_attachments_submission_id'


def upgrade() -> None:
    op.create_table(
        'deliverable_submissions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('contract_id', sa.String(), nullable=False),
        sa.Column('submitted_by_user_id', sa.String(), nullable=False),
        # Nullable, because a submission may be files only. The service
        # refuses one that has neither a link nor an attachment.
        sa.Column('link_url', sa.String(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.String(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_SUBMISSIONS),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], name=FK_SUBMISSIONS_CONTRACT),
        sa.ForeignKeyConstraint(
            ['submitted_by_user_id'], ['users.id'], name=FK_SUBMISSIONS_SUBMITTED_BY
        ),
        sa.ForeignKeyConstraint(
            ['reviewed_by_user_id'], ['users.id'], name=FK_SUBMISSIONS_REVIEWED_BY
        ),
    )
    op.create_index(
        IX_SUBMISSIONS_CONTRACT, 'deliverable_submissions', ['contract_id'], unique=False
    )

    # After deliverable_submissions: submission_id points at it.
    op.create_table(
        'deliverable_attachments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('submission_id', sa.String(), nullable=False),
        sa.Column('media_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=PK_ATTACHMENTS),
        sa.ForeignKeyConstraint(
            ['submission_id'], ['deliverable_submissions.id'], name=FK_ATTACHMENTS_SUBMISSION
        ),
        sa.ForeignKeyConstraint(['media_id'], ['media_assets.id'], name=FK_ATTACHMENTS_MEDIA),
    )
    op.create_index(
        IX_ATTACHMENTS_SUBMISSION, 'deliverable_attachments', ['submission_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(IX_ATTACHMENTS_SUBMISSION, table_name='deliverable_attachments')
    op.drop_table('deliverable_attachments')
    op.drop_index(IX_SUBMISSIONS_CONTRACT, table_name='deliverable_submissions')
    op.drop_table('deliverable_submissions')
