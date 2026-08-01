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


def upgrade() -> None:
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
    op.create_index(IX_RESET_TOKEN, 'password_reset_tokens', ['token'], unique=False)


def downgrade() -> None:
    op.drop_index(IX_RESET_TOKEN, table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('otp_challenges')
