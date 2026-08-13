"""What a payment gateway has to be able to do, and what it hands back.

THE INTERFACE IS FOUR VERBS, and the split between them is the asynchrony that
provider.py's two-verb Protocol could not express:

    start_collection   ask the payer for money. Returns somewhere to send them.
    read_collection    ask the gateway what actually happened. THE ONLY TRUTH.
    send_payout        push money to a wallet.
    read_payout        ask the gateway whether it landed.

read_collection is separate from start_collection because a webhook is a
notification, not a fact. Anyone on the internet can POST to a webhook URL; a
signature makes that harder but the signed thing is still the sender's own
account of events. So every path in this codebase that believes a payment
happened believes it because read_collection said so, over an authenticated
outbound connection we opened, to a host we chose. The webhook's entire job is
to tell us when to ask.

AMOUNTS ARE INTEGERS IN THE CURRENCY'S OWN UNITS, matching the rest of the
codebase and, as it happens, matching FedaPay: XOF has no minor unit, so 2000
is two thousand francs and there is no times-one-hundred anywhere. A gateway
whose API wants centimes converts inside its own module and never leaks that
outward.
"""
from dataclasses import dataclass, field
from typing import Protocol

# Collection statuses, normalised. Every gateway maps its own vocabulary onto
# these four, so escrow logic never learns a vendor's spelling of "declined".
#
# PENDING is the honest answer for "asked, not answered yet" and is the state
# a fresh intent is in for as long as the payer is looking at their phone.
PENDING = "pending"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELED = "canceled"

TERMINAL_COLLECTION_STATUSES = (SUCCEEDED, FAILED, CANCELED)

# Payout statuses. A DIFFERENT set from collections, deliberately, because a
# payout has a step collections do not: SENT means the gateway says the money
# left, which is not the same as the wallet having received it, and merging the
# two vocabularies would hide that.
PAYOUT_PENDING = "pending"
PAYOUT_SENT = "sent"
PAYOUT_FAILED = "failed"

TERMINAL_PAYOUT_STATUSES = (PAYOUT_SENT, PAYOUT_FAILED)


class GatewayError(RuntimeError):
    """The gateway could not be reached, or answered something unusable.

    Deliberately NOT an AppError. An AppError is a rule the user broke and it
    carries a sentence we want them to read; this is our side failing, and the
    caller decides whether that is a 502 to a brand mid-checkout or a line in
    a retry log for a payout sweep. The two want different handling and a
    shared base class would flatten them.

    `retryable` is the distinction that matters to a sweep: a timeout is worth
    trying again, a 400 saying the phone number is malformed never will be.
    """

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


@dataclass(frozen=True)
class CollectionStart:
    """Where to send the payer, and what to call this attempt afterwards.

    `reference` is the gateway's id for the transaction and is what
    read_collection is later called with. `checkout_url` is single-use and
    short-lived at every gateway I know of (FedaPay: 24 hours), which is why
    nothing stores it as though it were a permanent property of an order — it
    belongs to one attempt.
    """

    reference: str
    checkout_url: str
    expires_in_seconds: int | None = None


@dataclass(frozen=True)
class CollectionState:
    """What the gateway says about one collection, right now.

    `amount` and `currency` are on here and are not decoration. They are how
    the caller checks that the money that arrived is the money that was asked
    for — a webhook that says "approved" for a transaction whose amount is a
    tenth of the contract is the single cheapest fraud against a marketplace,
    and the only defence is comparing the two numbers on the way in.
    """

    reference: str
    status: str
    amount: int
    currency: str
    raw_status: str = ""
    failure_reason: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PayoutState:
    reference: str
    status: str
    amount: int
    currency: str
    raw_status: str = ""
    failure_reason: str | None = None


@dataclass(frozen=True)
class PayoutTarget:
    """Who is being paid, in the shape a mobile money network needs.

    `mode` is the network — the gateway's own string for MTN Benin, Moov Togo
    and so on. It is REQUIRED and is not guessed from the phone number: number
    ranges are reassigned between operators, portability moves a subscriber
    across networks without changing their digits, and a payout sent down the
    wrong network does not bounce, it fails days later with money in limbo. So
    the creator tells us, once, and we store it. See payments/payout_methods.py.
    """

    phone: str
    country: str
    mode: str
    first_name: str = "Kolabo"
    last_name: str = "Creator"
    email: str | None = None


class PaymentGateway(Protocol):
    """The four verbs. A gateway is anything that can answer all of them."""

    name: str

    def supports(self, country: str, currency: str) -> bool:
        ...

    def start_collection(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        callback_url: str,
        payer_phone: str,
        payer_country: str,
        payer_first_name: str,
        payer_last_name: str,
        payer_email: str | None = None,
        merchant_reference: str | None = None,
        metadata: dict | None = None,
    ) -> CollectionStart:
        ...

    def read_collection(self, reference: str) -> CollectionState:
        ...

    def send_payout(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        target: PayoutTarget,
        merchant_reference: str | None = None,
    ) -> PayoutState:
        ...

    def read_payout(self, reference: str) -> PayoutState:
        ...

    def verify_webhook(self, raw_body: bytes, headers: dict) -> dict:
        """Authenticate an inbound webhook and return its decoded payload.

        Raises GatewayError when the request is not provably from the gateway.
        Takes RAW BYTES, never a parsed body: the signature covers the exact
        octets that were sent, and re-serialising a dict changes key order and
        whitespace and produces a different string to hash. This is the single
        most common way webhook verification is written wrong.
        """
        ...
