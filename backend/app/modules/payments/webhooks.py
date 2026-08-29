"""Inbound gateway webhooks. The only unauthenticated write path in the API.

Everything else behind /payments requires a bearer token belonging to a party
to the money in question. This does not, and cannot: the caller is a machine at
FedaPay that has never logged in. So the three things that make it safe are all
in this file and none of them is optional.

    1. SIGNATURE. HMAC-SHA256 over "<timestamp>.<raw body>", constant-time
       compared, five minute window. Fails -> 400, nothing read, nothing written.
    2. IDEMPOTENCY. The event id is inserted into gateway_events BEFORE the
       work, under a unique constraint. A duplicate delivery loses the insert
       and returns 200 without doing anything twice.
    3. RE-READ. The body is never believed. It names a transaction; we go and
       ask the gateway about that transaction ourselves.

WHY IT ALWAYS ANSWERS 200 ONCE THE SIGNATURE PASSES. A non-2xx tells the
gateway to redeliver, and redelivery is right for "we were down" and wrong for
everything else. An event about a transaction we do not recognise will never
become recognisable by being sent again; nor will one whose amount does not
match. Answering 500 to those turns a data problem into an infinite retry loop
that also fills the error log, hiding the real outages. So: signature failures
are 4xx and never retried, our own failures are 5xx and retried, and
"received, understood, nothing to do" is 200.

RAW BYTES, NOT A PARSED BODY. The handler takes `await request.body()` and the
signature is computed over exactly those octets. FastAPI would happily give us
a validated Pydantic model instead, and re-serialising it would change key
order and whitespace and produce a different hash. This is the most common way
webhook verification is written wrong, and it fails closed in dev (every
signature mismatches) which is why it usually gets caught — but it can just as
easily be "fixed" by disabling verification.
"""
import json
import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.payments import checkout
from app.modules.payments import gateway_models as gmodels
from app.modules.payments import payouts
from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import GatewayError

logger = logging.getLogger(__name__)

router = APIRouter()

# Events worth acting on. Anything else is recorded and acknowledged, which is
# not laziness: an unknown event type is a gateway feature we have not adopted
# yet, and the right response to one is to store it and move on, not to error.
TRANSACTION_EVENTS = (
    "transaction.approved",
    "transaction.canceled",
    "transaction.cancelled",
    "transaction.declined",
    "transaction.transferred",
    "transaction.updated",
)
PAYOUT_EVENTS = ("payout.sent", "payout.failed", "payout.updated", "payout.processing")


def _event_id(payload: dict) -> str:
    """A stable id for this delivery, whatever shape it arrived in.

    FedaPay's documented event names are solid; the envelope around them is
    less so, and the payout event names are not enumerated in their docs at
    all. So this looks in the three places an id could be and, failing all of
    them, builds one from the fields that identify the event — because an event
    with no id must still be de-duplicated, and the alternative to a derived
    key is no idempotency at all for exactly the deliveries we understand least.
    """
    for key in ("id", "event_id"):
        value = payload.get(key)
        if value:
            return str(value)
    entity = payload.get("entity") or payload.get("object") or payload.get("data") or {}
    if isinstance(entity, dict) and entity.get("id"):
        return f"{payload.get('name') or payload.get('event') or 'event'}:{entity['id']}"
    return json.dumps(payload, sort_keys=True)[:255]


def _event_name(payload: dict) -> str:
    return str(payload.get("name") or payload.get("event") or payload.get("type") or "")


def _entity(payload: dict) -> dict:
    for key in ("entity", "object", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            # Some envelopes nest one more level: {"data": {"object": {...}}}
            inner = value.get("object")
            return inner if isinstance(inner, dict) else value
    return {}


@router.post("/fedapay", status_code=status.HTTP_200_OK)
async def fedapay_webhook(request: Request, db: Session = Depends(get_db)) -> Response:
    gateway = registry.gateway_by_name("fedapay")
    if gateway is None:
        # No credentials configured, so no secret to verify against. 503 rather
        # than 200: this IS a state worth retrying, because it is us being
        # misconfigured and it will start working when somebody fixes it.
        logger.error("FedaPay webhook received but no gateway is configured")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    raw_body = await request.body()
    try:
        payload = gateway.verify_webhook(raw_body, dict(request.headers))
    except GatewayError as exc:
        # Deliberately terse to the caller. A verification failure is either a
        # forgery or a misconfiguration, and in the first case an error message
        # explaining exactly which check failed is free reconnaissance.
        logger.warning("Rejected FedaPay webhook: %s", exc)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    event_id = _event_id(payload)
    event_name = _event_name(payload)

    record = gmodels.GatewayEvent(
        provider="fedapay",
        event_id=event_id,
        event_type=event_name,
        payload=raw_body.decode("utf-8", errors="replace")[:100_000],
    )
    db.add(record)
    try:
        # Committed BEFORE the work. Two concurrent deliveries of one event
        # both reach this line; the unique constraint on (provider, event_id)
        # lets exactly one through, and the other finds out it lost before it
        # has funded anything.
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("Duplicate FedaPay webhook %s ignored", event_id)
        return Response(status_code=status.HTTP_200_OK)

    try:
        _handle(db, event_name, _entity(payload))
    except GatewayError:
        # We could not reach the gateway to re-read. This one IS worth a
        # retry — the event is real and we simply could not check it — so the
        # de-dup row is removed first, or the redelivery would be swallowed as
        # a duplicate and the payment would never settle.
        db.delete(record)
        db.commit()
        logger.exception("Could not verify FedaPay event %s upstream", event_id)
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception:
        # Our bug, on an event we have already recorded. 500 so it is retried
        # and so it is loud, but the record stays: a redelivery that hits the
        # same bug should not also duplicate the event row.
        logger.exception("Failed handling FedaPay event %s", event_id)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    record.processed_at = gmodels.utcnow()
    db.commit()
    return Response(status_code=status.HTTP_200_OK)


def _handle(db: Session, event_name: str, entity: dict) -> None:
    reference = entity.get("id")
    if reference is None:
        return
    reference = str(reference)

    if event_name in TRANSACTION_EVENTS or event_name.startswith("transaction."):
        intent = (
            db.query(gmodels.PaymentIntent)
            .filter(
                gmodels.PaymentIntent.provider == "fedapay",
                gmodels.PaymentIntent.provider_ref == reference,
            )
            .first()
        )
        if intent is None:
            # A transaction we did not start, or one whose intent row is gone.
            # Logged and acknowledged: retrying will not make it ours.
            logger.info("FedaPay transaction %s has no matching intent", reference)
            return
        checkout.settle_intent(db, intent)
        return

    if event_name in PAYOUT_EVENTS or event_name.startswith("payout."):
        payout = (
            db.query(gmodels.Payout)
            .filter(
                gmodels.Payout.provider == "fedapay",
                gmodels.Payout.provider_ref == reference,
            )
            .first()
        )
        if payout is None:
            logger.info("FedaPay payout %s has no matching row", reference)
            return
        gateway = registry.gateway_by_name("fedapay")
        state = gateway.read_payout(reference)
        payout.provider_status = state.raw_status
        mapped = payouts._PAYOUT_STATUS.get(state.status, gmodels.PAYOUT_PENDING)
        payouts._mark(
            payout, mapped, provider="fedapay", reason=state.failure_reason, fee=state.fee
        )
        if mapped == gmodels.PAYOUT_SENT:
            payouts._notify_paid(db, payout)
        db.commit()
        return

    logger.info("Ignoring FedaPay event %s", event_name)
