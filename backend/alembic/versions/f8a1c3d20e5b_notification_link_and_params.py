"""notification link and params

Adds two nullable columns to notifications: link (deep-link target, built at
emit time where the recipient's side is known) and params (the localised-body
source: an i18n key plus interpolation values). Both nullable, so there is no
server_default and no backfill — an old row simply has no deep link and renders
its stored English message, which is exactly the pre-migration behaviour.

GUARDED like c9a4e7b21f36 (the OTP migration), and for the same reason: the
notifications table is not owned by any migration. It exists only because
init_db() runs create_all, which happens at APP startup — AFTER `alembic
upgrade head` in the container command (`alembic upgrade head && uvicorn`). So
on a pure-migration database the table does not exist yet at this point, and a
bare add_column would crash the upgrade and take the API down with it. When the
table is absent we skip: create_all will build it from the model with these
columns already on it. When it is present (every environment that has ever
booted the app) we add whichever columns are missing, so a re-run is a no-op.

Revision ID: f8a1c3d20e5b
Revises: b5d2e9f31a04
Create Date: 2026-08-03

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8a1c3d20e5b'
down_revision = 'b5d2e9f31a04'
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if 'notifications' not in inspector.get_table_names():
        # create_all will build the table from the model, these columns on it.
        return
    columns = {c['name'] for c in inspector.get_columns('notifications')}
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        if 'link' not in columns:
            batch_op.add_column(sa.Column('link', sa.String(), nullable=True))
        if 'params' not in columns:
            batch_op.add_column(sa.Column('params', sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = _inspector()
    if 'notifications' not in inspector.get_table_names():
        return
    columns = {c['name'] for c in inspector.get_columns('notifications')}
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        if 'params' in columns:
            batch_op.drop_column('params')
        if 'link' in columns:
            batch_op.drop_column('link')
