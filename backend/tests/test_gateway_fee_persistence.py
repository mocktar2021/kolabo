"""A fee, once recorded, survives a later read that does not mention one.

WHAT WAS WRONG. `checkout.settle_intent` assigned `intent.gateway_fee =
state.fee` unconditionally. `payouts._mark`, written in the same PR, guards the
identical assignment with `if fee is not None` and says why; the collection leg
did not.

WHY THAT IS NOT A THEORETICAL RACE. A pending intent is settled MORE THAN ONCE
by design — checkout.py's own docstring says the webhook and the return page
both call `settle_intent` and calls that race "not a problem" — and `get_intent`
settles on every poll while the payer is still deciding. Each of those is a
fresh `read_collection`. A read that does not mention a fee is the gateway
staying silent, not the gateway retracting a fee. Assigning unconditionally let
the quietest read in that sequence delete a cost already recorded, and since
the last read before the intent turns terminal is the one that sticks, the
deletion was permanent.

AND IT FAILED IN THE DIRECTION THAT FLATTERS US. A null `gateway_fee` reads as
"the gateway did not report a fee", so an erased row is indistinguishable from
an honest unknown, and `commission_amount - payment_intent.gateway_fee -
payout.gateway_fee` understates what the collection cost. That is the exact
error the column exists to prevent.

WHY THIS FILE EXISTS RATHER THAN MORE CASES IN test_fedapay_checkout.py. Every
fee test there settles an intent exactly once, which is why none of them could
see this. The property under test here is specifically what a SECOND settlement
does, so it wants its own file and its own smallest possible fixture.

Driven against `settle_intent` directly, following test_otp_attempts.py: what
changed is the arithmetic of a repeated read, and going through HTTP would drag
in registration, contracts and country config without testing one more thing
about it.

Only the PENDING and FAILED paths are exercised. A SUCCEEDED settlement calls
`hold_funds` and needs a real contract, escrow and two users, none of which is
involved in whether an assignment is guarded.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.modules.payments import checkout
from app.modules.payments import gateway_models as gmodels
from app.modules.payments.gateways import base as gwbase
from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import CollectionState

AMOUNT = 50000
CURRENCY = "XOF"


class FakeGateway:
    """A gateway whose answer can be changed between reads.

    That is the whole point of it: the defect only appears when one read
    reports a fee and a later read does not, which no fixture that answers the
    same thing twice can produce.
    """

    name = "fake"

    def __init__(self):
        self.status = gwbase.PENDING
        self.fee = None
        self.reads = 0

    def read_collection(self, reference):
        self.reads += 1
        return CollectionState(
            reference=reference,
            status=self.status,
            amount=AMOUNT,
            currency=CURRENCY,
            raw_status=self.status,
            fee=self.fee,
        )


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models

    import_all_models()
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def gateway(monkeypatch):
    """Patched onto the registry module, which is how checkout.py reaches it.

    `checkout` does `from ...gateways import registry` and then calls
    `registry.gateway_by_name(...)` at settle time, so replacing the attribute
    on the module object is enough and no import inside checkout needs touching.
    """
    fake = FakeGateway()
    monkeypatch.setattr(registry, "gateway_by_name", lambda name: fake)
    return fake


def _intent(db):
    """A pending intent with a provider reference, and nothing else.

    The contract and user ids are strings that match no row. SQLite does not
    enforce foreign keys unless asked to, and settle_intent never dereferences
    either one on the paths under test — it reads `provider`, `provider_ref`,
    `amount`, `currency` and `status`. Seeding a real contract and two users
    would add fifty lines that no assertion here depends on.
    """
    intent = gmodels.PaymentIntent(
        contract_id="contract-not-a-real-row",
        business_user_id="user-not-a-real-row",
        amount=AMOUNT,
        currency=CURRENCY,
        country="BJ",
        provider="fake",
        provider_ref="txn-1",
        status=gmodels.INTENT_PENDING,
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent


def test_a_reported_fee_is_recorded(db, gateway):
    """The behaviour #154 added, unchanged by the guard."""
    intent = _intent(db)
    gateway.fee = 600

    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert intent.gateway_fee == 600


def test_a_later_silent_read_does_not_erase_a_recorded_fee(db, gateway):
    """THE REGRESSION. Against the unguarded code this is red on the last line.

    Two settlements of one pending intent, which is the ordinary case and not a
    contrived one: the first is the webhook or the return page, the second is
    the client polling while the payer decides. The gateway reports a fee, then
    goes quiet.

    Silence is not a retraction. A gateway that says nothing about a fee has not
    told us the movement became free, and the column must not say it did.
    """
    intent = _intent(db)
    gateway.fee = 600
    checkout.settle_intent(db, intent)
    assert intent.gateway_fee == 600

    gateway.fee = None
    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert gateway.reads == 2, "the intent must still be pending, or this proves nothing"
    assert intent.gateway_fee == 600


def test_a_corrected_fee_still_replaces_an_earlier_one(db, gateway):
    """The guard is on the gateway's SILENCE, not on the column being empty.

    Written against the plausible wrong fix — `if intent.gateway_fee is None` —
    which would also make the test above pass while quietly making the first
    number ever seen permanent. A gateway that revises a fee upward between a
    provisional read and a settled one must be believed.
    """
    intent = _intent(db)
    gateway.fee = 600
    checkout.settle_intent(db, intent)

    gateway.fee = 750
    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert intent.gateway_fee == 750


def test_an_intent_the_gateway_never_charged_for_stays_null(db, gateway):
    """Null is the honest answer, and zero would not be.

    Defaulting an unreported fee to 0 would claim the collection was free,
    which is a claim we cannot support and one that only ever errs in our
    favour.
    """
    intent = _intent(db)

    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert intent.gateway_fee is None


def test_a_fee_is_recorded_on_a_collection_that_failed(db, gateway):
    """A failed collection can still have cost us something.

    The assignment sits before the status branch precisely so it lands on every
    terminal path; the guard must not have moved it back onto the happy one.
    """
    intent = _intent(db)
    gateway.status = gwbase.FAILED
    gateway.fee = 300

    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert intent.status == gmodels.INTENT_FAILED
    assert intent.gateway_fee == 300


def test_a_terminal_intent_is_not_re_read_at_all(db, gateway):
    """The early return, which is what bounds the whole problem.

    Once an intent is terminal `settle_intent` returns before touching the
    gateway, so a recorded fee cannot be disturbed afterwards. Asserted rather
    than assumed, because if this early return ever went away the guard above
    would become the only thing standing between a settled row and a later
    quiet read.
    """
    intent = _intent(db)
    gateway.status = gwbase.FAILED
    gateway.fee = 300
    checkout.settle_intent(db, intent)
    assert gateway.reads == 1

    gateway.fee = None
    checkout.settle_intent(db, intent)

    db.refresh(intent)
    assert gateway.reads == 1
    assert intent.gateway_fee == 300
