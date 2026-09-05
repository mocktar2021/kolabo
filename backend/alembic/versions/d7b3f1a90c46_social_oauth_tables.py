"""social oauth states and tokens

Revision ID: d7b3f1a90c46
Revises: c4a1e8d73b25
Create Date: 2026-09-04

Two tables behind the OAuth subsystem, and neither of them touches an existing
one.

oauth_states holds ONE AUTHORIZATION IN FLIGHT: the CSRF state, the PKCE
verifier, and the user id the callback will attach the resulting account to.
That user id is the point of the table — the callback is a browser redirect
from a social platform and carries no bearer token, so the row is the only
thing that says whose profile is being written. Hence a UNIQUE index on
`state`: "resolves to exactly one creator" is a property of the schema here,
not of whichever query happens to be written above it.

social_tokens holds the credentials for one connected account, encrypted with
the same Fernet key as verification_documents.ciphertext. IT IS A SEPARATE
TABLE RATHER THAN COLUMNS ON social_accounts on purpose: social_accounts is
read on every public profile view, by anybody, with no token in the request,
and token ciphertext must not be selected on that path. Unique on
social_account_id — re-authorising replaces the credentials rather than growing
a pile of live secrets.

THE INSPECTOR GUARD, following c9a4e7b21f36 and a1c5e8b30f7d. Both tables are
also created by create_all at app startup, which runs AFTER `alembic upgrade
head` in the container command, so a deployment that has already booted once
presents them before this migration reaches them. An unguarded create_table
raises DuplicateTable there, and because the command is
`alembic upgrade head && uvicorn` a failed upgrade takes the whole API down
rather than just the migration. Note that CI cannot catch this class of bug:
test_migrations builds a fresh database, where the guard is never exercised.

Nothing is altered on a table that is already present. What create_all built is
the schema this migration describes — the index names below are exactly the
ones SQLAlchemy derives from index=True on the models — so there is nothing to
reconcile, and dropping and recreating a table to feel authoritative would
discard live rows to prove a point.

EVERY CONSTRAINT IS NAMED, foreign keys and indexes included. SQLite cannot
alter constraints in place, so a later batch_alter_table on these tables
rebuilds them from the reflected schema, and alembic cannot reconstruct a
constraint it cannot name. c3f7a1d9e08b wrote that rule down after CI failed on
an anonymous one; a3f8b1c47d20, e2f9c4a71d38 and c9a4e7b21f36 restated it.

DOWN_REVISION IS c4a1e8d73b25, the single head after #161, verified by reading
the versions directory rather than assumed. This repo has already had one
two-head incident (see the re-parenting of b2e6d90a3f14 onto a1c5e8b30f7d): two
branches open at once both wrote themselves off 4423dba6754c, and `upgrade
head` then raises "Multiple head revisions are present" on main, not on either
branch. Worth re-checking at merge time if anything else lands first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7b3f1a90c46'
down_revision: Union[str, None] = 'c4a1e8d73b25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_STATES = 'pk_oauth_states'
FK_STATES_USER = 'fk_oauth_states_user_id'
# Matches the name SQLAlchemy derives from OAuthState.state's
# unique=True, index=True — one UNIQUE index, not an index plus a constraint.
IX_STATES_STATE = 'ix_oauth_states_state'

PK_TOKENS = 'pk_social_tokens'
FK_TOKENS_ACCOUNT = 'fk_social_tokens_social_account_id'
IX_TOKENS_ACCOUNT = 'ix_social_tokens_social_account_id'


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    existing = set(_inspector().get_table_names())

    if 'oauth_states' not in existing:
        op.create_table(
            'oauth_states',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('state', sa.String(), nullable=False),
            sa.Column('code_verifier', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('platform', sa.String(), nullable=False),
            # Nullable: an API client that just wants the result does not need
            # anywhere to be sent afterwards.
            sa.Column('redirect_to', sa.String(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('consumed', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=PK_STATES),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=FK_STATES_USER),
        )

    if 'social_tokens' not in existing:
        op.create_table(
            'social_tokens',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('social_account_id', sa.String(), nullable=False),
            # LargeBinary, like verification_documents.ciphertext: Fernet
            # returns bytes and storing them as text would mean an encoding
            # round trip on a value that must come back byte-identical.
            sa.Column('access_token_ciphertext', sa.LargeBinary(), nullable=False),
            # Nullable: not every provider issues a refresh token, and one
            # that does not has not failed at anything.
            sa.Column('refresh_token_ciphertext', sa.LargeBinary(), nullable=True),
            sa.Column('access_expires_at', sa.DateTime(), nullable=False),
            sa.Column('refresh_expires_at', sa.DateTime(), nullable=True),
            sa.Column('scope', sa.String(), nullable=True),
            sa.Column('provider_user_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=PK_TOKENS),
            sa.ForeignKeyConstraint(
                ['social_account_id'], ['social_accounts.id'], name=FK_TOKENS_ACCOUNT
            ),
        )

    # Re-read the inspector: a table may have just been created above, and on a
    # create_all database the indexes are already there under these same names.
    # Both are UNIQUE, and on oauth_states.state that uniqueness is a security
    # property rather than a tidiness one.
    inspector = _inspector()
    states_indexes = {index['name'] for index in inspector.get_indexes('oauth_states')}
    if IX_STATES_STATE not in states_indexes:
        op.create_index(IX_STATES_STATE, 'oauth_states', ['state'], unique=True)

    tokens_indexes = {index['name'] for index in inspector.get_indexes('social_tokens')}
    if IX_TOKENS_ACCOUNT not in tokens_indexes:
        op.create_index(
            IX_TOKENS_ACCOUNT, 'social_tokens', ['social_account_id'], unique=True
        )


def downgrade() -> None:
    # Guarded, so a downgrade on a database where the upgrade skipped a table
    # is a no-op rather than a crash. Dropped in the reverse of the order they
    # were created, and only what this revision put there.
    existing = set(_inspector().get_table_names())

    if 'social_tokens' in existing:
        op.drop_index(IX_TOKENS_ACCOUNT, table_name='social_tokens')
        op.drop_table('social_tokens')

    if 'oauth_states' in existing:
        op.drop_index(IX_STATES_STATE, table_name='oauth_states')
        op.drop_table('oauth_states')
