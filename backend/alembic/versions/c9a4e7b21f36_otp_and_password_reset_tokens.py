"""otp challenges and password reset tokens

TWO TABLES THAT THE MODELS HAVE ALWAYS DECLARED AND NO MIGRATION HAS EVER
CREATED. app.modules.auth.models has carried OtpChallenge and
PasswordResetToken since the first commit, the baseline migration
(5f3a9c80d26f) never included either, and nothing since added them. It went
unnoticed because init_db() calls create_all on model metadata at startup and
the test suite builds its schema the same way, so every environment that has
ever run the app got the tables from SQLAlchemy rather than from alembic. A
database built by `alembic upgrade head` alone — which is what the deployment
path is meant to be — has no otp_challenges, and registration fails on the
insert at the end of it.

WHICH IS WHY THIS MIGRATION IS CONDITIONAL. The same create_all that hid the
problem guarantees two different starting points: a database that has ever
booted the app already has both tables, and one raised purely by alembic has
neither. A plain create_table crashes the first kind with DuplicateTable — and
because the container runs `alembic upgrade head && uvicorn`, a failed upgrade
takes the whole API down rather than just the migration. So each table is
created only when the inspector reports it missing.

Nothing is altered on a table that is already there. What create_all built is
the same schema this migration describes, and dropping and recreating it to
feel authoritative would discard live OTP rows to prove a point. After this
revision the tables belong to alembic either way, which is what the downgrade
assumes when it drops them unconditionally.

THE REAL FIX IS UPSTREAM and deliberately not attempted here: init_db should
stop calling create_all outside the test suite, so that alembic is the only
thing that ever builds a schema and the two can never diverge again. That
changes how every environment boots and is not a migration's decision to make.

password_reset_tokens.token is INDEXED AND NOT UNIQUE, which is a change from
what the model used to say. It now holds the same six digit code the
registration OTP uses, because a reset code arrives by SMS and gets retyped
off a lock screen; six digits over a million values means two accounts will
eventually be handed the same one, and a unique constraint would turn that
collision into a failure for whichever locked-out user asked second.
Uniqueness was never the property that mattered — a code is only ever resolved
together with the phone it was sent to.

EVERY CONSTRAINT IS NAMED, foreign keys and indexes included. SQLite cannot
alter constraints in place, so any later batch_alter_table on these tables
copies them, rebuilds them from the reflected schema and swaps them in; that
rebuild re-declares every constraint and alembic cannot reconstruct one it
cannot name ("Constraint must have a name"). c3f7a1d9e08b wrote this rule down
after CI failed on an anonymous one, and f1a7c9d2e4b8 and e2f9c4a71d38
restated it. A table created with anonymous constraints only fails later, when
somebody else is adding a column.

Revision ID: c9a4e7b21f36
Revises: e2f9c4a71d38
Create Date: 2026-08-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9a4e7b21f36'
down_revision: Union[str, None] = 'e2f9c4a71d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_OTP = 'pk_otp_challenges'
FK_OTP_USER = 'fk_otp_challenges_user_id'

PK_RESET = 'pk_password_reset_tokens'
FK_RESET_USER = 'fk_password_reset_tokens_user_id'
# Matches the name SQLAlchemy derives from PasswordResetToken.token's
# index=True, so a migrated schema and a create_all schema agree on it.
IX_RESET_TOKEN = 'ix_password_reset_tokens_token'


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    existing = set(inspector.get_table_names())

    if 'otp_challenges' not in existing:
        op.create_table(
            'otp_challenges',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('code', sa.String(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('consumed', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=PK_OTP),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=FK_OTP_USER),
        )

    if 'password_reset_tokens' not in existing:
        op.create_table(
            'password_reset_tokens',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('token', sa.String(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('consumed', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=PK_RESET),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=FK_RESET_USER),
        )

    # Re-read: the table may have just been created above, and on a create_all
    # database the index is already there under the same name.
    indexes = {
        index['name']
        for index in _inspector().get_indexes('password_reset_tokens')
    }
    if IX_RESET_TOKEN not in indexes:
        op.create_index(
            IX_RESET_TOKEN, 'password_reset_tokens', ['token'], unique=False
        )


def downgrade() -> None:
    # Unconditional on purpose. Whoever created these tables, this revision is
    # what claims them; going back past it means going back to a schema that
    # has neither.
    op.drop_index(IX_RESET_TOKEN, table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('otp_challenges')
