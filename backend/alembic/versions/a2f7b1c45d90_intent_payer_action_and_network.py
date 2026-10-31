"""payment_intents: what the payer has to do next, and on which network

Two nullable string columns, no backfill, no constraint. This is what lets a
collection exist that has nothing for the payer to open.

WHY. Kolabo's funding flow was built on one assumption: starting a collection
returns a URL, and the brand's browser goes there. Checkout.tsx redirects,
CollectionStart required a checkout_url, and checkout.py's duplicate-funding
guard literally queried `checkout_url IS NOT NULL`.

That assumption does not survive contact with the market this product
launches in. FeexPay's only hosted checkout page takes CARDS: it was opened
and read on 27 October and carries no mobile money option at all. Mobile
money is how brands in Benin, Togo, Cote d'Ivoire and Senegal pay, and its
endpoint pushes a prompt to a handset and returns no URL of any kind. So a
funding attempt now has two possible next steps and the schema has to be able
to say which one happened.

payer_action is that answer: `redirect` or `device_prompt`. It is recorded
rather than derived because deriving it means reading the nullness of
checkout_url, and the first caller to get that inference backwards either
sends a brand to a blank page or polls a transaction that is waiting for a
browser nobody is going to open.

payer_network is which operator the prompt was addressed to. Stored for two
reasons that are both about later rather than now: reconciling a movement
against a provider statement needs to know which operator it went through,
and a brand retrying a failed payment should not be asked the same question
twice. It holds the gateway's own string, uppercase with spaces, which is NOT
the underscored vocabulary payout_methods.mode holds for the same provider.

NULLABLE, WITH NO SERVER DEFAULT AND NO BACKFILL, and that is the release rule
rather than laziness. Every intent written before this revision is a redirect,
and a `UPDATE payment_intents SET payer_action = 'redirect'` would be true
today and would also make this migration non-additive: the previous image,
redeployed as a rollback, writes rows with a null in a column a NOT NULL
constraint forbids. claude/kolabo-release-strategy-1023.md states the rule
that every migration is additive and nullable in the release that ships the
code reading it, precisely so that rolling back a tag means something. The
null is read as `redirect` at the edge, in checkout._intent_out, which is one
line in one place and costs nothing.

NO INDEX ON EITHER. Nothing filters, groups or joins on them. payer_action is
read one row at a time by the screen rendering a funding attempt, and
payer_network is read one row at a time by whoever is reconciling it. An
index on a two-valued column over a table this size would be read overhead
with no reader.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2f7b1c45d90'
down_revision: Union[str, None] = 'd3a6b9e24c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('payment_intents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payer_action', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('payer_network', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('payment_intents', schema=None) as batch_op:
        batch_op.drop_column('payer_network')
        batch_op.drop_column('payer_action')
