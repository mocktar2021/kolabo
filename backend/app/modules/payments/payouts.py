"""Getting money out of the platform and into a creator's wallet.

THIS MODULE IS WHY THE GATEWAY DECISION WENT THE WAY IT DID. A marketplace has
to be able to pay a third party from code. KKiaPay cannot: its only payout
endpoint schedules settlement of your own merchant balance into your own
registered account, which is a treasury feature, not a disbursement API.
FedaPay can: POST /v1/payouts names a recipient and a network, and
PUT /v1/payouts/start sends it. Everything below is built on that pair.

THE RULE THIS MODULE EXISTS TO ENFORCE: releasing an escrow and paying a
creator are two different events and they are allowed to have different
outcomes. Before this, they were one line —

    payout_ref = payment_provider.payout(...)   # then mark the escrow RELEASED

— which is correct against a mock that cannot fail and wrong against a network
that can. If a real payout raised, the release would 500 after the platform had
already decided the creator was owed; if it were swallowed, the escrow would
read RELEASED with nobody paid.

So the escrow records the DECISION and never takes it back, and a Payout row
records what happened to the MONEY. A payout that fails is retried; one that
keeps failing stops and becomes a support queue item, with the creator still
visibly owed. That is the honest state, and it is recoverable. "Released, but
actually nobody was paid, and nothing knows" is neither.

The same argument the _award_referral_credits docstring already makes about
post-payment work: a step after the decision must never turn a successful
decision into a failed request.
"""
import logging

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.notifications.service import notify
from app.modules.payments import gateway_models as gmodels
from app.modules.payments import models
from app.modules.payments.gateways import base as gwbase
from app.modules.payments.gateways import fedapay as fedapay_module
from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import GatewayError, PayoutTarget

logger = logging.getLogger(__name__)

_PAYOUT_STATUS = {
    gwbase.PAYOUT_PENDING: gmodels.PAYOUT_PENDING,
    gwbase.PAYOUT_SENT: gmodels.PAYOUT_SENT,
    gwbase.PAYOUT_FAILED: gmodels.PAYOUT_FAILED,
}


# --------------------------------------------------------------- payout method


def valid_modes(country: str) -> tuple[str, ...]:
    return fedapay_module.PAYOUT_MODES.get(country, ())


def set_payout_method(
    db: Session, user_id: str, *, country: str, mode: str, phone: str, account_name: str | None
) -> dict:
    """Record where this person wants to be paid. Validated here, not at payout time.

    The mode is checked against the gateway's own closed set NOW, while the
    creator is looking at a form and can fix it, rather than in three weeks
    when a release fails against a network string nobody accepts. A rule
    enforced at the last possible moment is a rule that fails in front of the
    wrong person.
    """
    allowed = valid_modes(country)
    if not allowed:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payout_country_unsupported",
            detail=(
                f"We cannot pay out to {country} yet. "
                "We will let you know as soon as your country opens."
            ),
        )
    if mode not in allowed:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payout_mode_unsupported",
            detail=f"Choose one of: {', '.join(allowed)}.",
        )
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 8:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payout_phone_invalid",
            detail="That does not look like a mobile money number.",
        )

    method = (
        db.query(gmodels.PayoutMethod).filter(gmodels.PayoutMethod.user_id == user_id).first()
    )
    if method is None:
        method = gmodels.PayoutMethod(user_id=user_id)
        db.add(method)
    method.country = country
    method.mode = mode
    method.phone = phone
    method.account_name = account_name
    method.updated_at = gmodels.utcnow()
    db.commit()
    db.refresh(method)
    return _method_out(method)


def get_payout_method(db: Session, user_id: str) -> dict | None:
    method = db.query(gmodels.PayoutMethod).filter(gmodels.PayoutMethod.user_id == user_id).first()
    return _method_out(method) if method else None


def _method_out(method: gmodels.PayoutMethod) -> dict:
    return {
        "country": method.country,
        "mode": method.mode,
        # Masked. The full number goes to the gateway and nowhere near a
        # response body: it is the one field on this row that is worth
        # stealing, and a creator confirming "yes, that's my number" only needs
        # the last four digits to do it.
        "phone_masked": f"*** {method.phone[-4:]}" if len(method.phone) >= 4 else "***",
        "account_name": method.account_name,
    }


# ------------------------------------------------------------------ disbursing


def disburse(
    db: Session,
    escrow: models.Escrow,
    *,
    amount: int,
    recipient_user_id: str,
    kind: str,
    legacy_provider=None,
) -> str | None:
    """Pay `amount` to `recipient_user_id`. NEVER RAISES on a gateway failure.

    Returns a reference for escrow.provider_payout_ref, or None when the money
    could not be sent yet — and None is a normal answer, not an error. The
    caller has already decided the money is owed; this reports whether it has
    moved, and a Payout row is written either way so a sweep can finish the job.

    `legacy_provider` is the mock seam payments.service still holds. When no
    real gateway is configured for the recipient's country — which is every
    test, and every local dev stack — the old synchronous path runs unchanged
    and returns its "payout_<hex>" string. That is what keeps the existing
    suite green while the real path exists alongside it.
    """
    payout = gmodels.Payout(
        escrow_id=escrow.id,
        recipient_user_id=recipient_user_id,
        kind=kind,
        amount=amount,
        currency=escrow.currency,
        provider="pending",
        status=gmodels.PAYOUT_PENDING,
    )
    db.add(payout)
    db.flush()

    method = (
        db.query(gmodels.PayoutMethod)
        .filter(gmodels.PayoutMethod.user_id == recipient_user_id)
        .first()
    )
    country = method.country if method else _user_country(db, recipient_user_id)
    gateway = registry.registry().get(country or "")

    if gateway is None:
        # No live gateway here. Fall back to the legacy provider so the mock
        # path, the tests and any uncovered country behave exactly as before.
        if legacy_provider is not None:
            user = db.query(User).filter(User.id == recipient_user_id).first()
            ref = legacy_provider.payout(user.phone if user else "", amount, escrow.currency)
            _mark(payout, gmodels.PAYOUT_SENT, provider="mock", ref=ref)
            return ref
        _mark(payout, gmodels.PAYOUT_NO_METHOD, provider="none", reason="no_gateway_for_country")
        return None

    payout.provider = gateway.name
    if method is None:
        # Owed, but we do not know where to send it. NOT a failure and NOT
        # retryable — no amount of retrying invents a wallet. The creator is
        # asked for one, and the sweep picks this row up the moment they answer.
        _mark(payout, gmodels.PAYOUT_NO_METHOD, provider=gateway.name, reason="no_payout_method")
        notify(
            db,
            recipient_user_id,
            "payment",
            "Add your mobile money details so we can send your payment.",
            link="/settings/payouts",
            params={"key": "payout_method_missing"},
        )
        return None

    return _send(db, payout, gateway, method, escrow)


def _send(db: Session, payout: gmodels.Payout, gateway, method, escrow) -> str | None:
    user = db.query(User).filter(User.id == payout.recipient_user_id).first()
    target = PayoutTarget(
        phone=method.phone,
        country=method.country,
        mode=method.mode,
        first_name=(method.account_name or "Kolabo").split(" ")[0][:40],
        last_name=(method.account_name or "Creator").split(" ")[-1][:40],
        email=user.email if user else None,
    )
    payout.attempts += 1
    payout.last_attempt_at = gmodels.utcnow()
    try:
        state = gateway.send_payout(
            amount=payout.amount,
            currency=payout.currency,
            description=f"Kolabo payout for contract {escrow.contract_id[:8]}",
            target=target,
            merchant_reference=payout.id,
        )
    except GatewayError as exc:
        # Swallowed on purpose, and this is the load-bearing line of the module.
        # The caller is mid-release: the escrow decision is made, the referral
        # hook is about to run, and the transaction is about to commit. Letting
        # this propagate would roll all of that back over a network blip and
        # leave a creator who delivered with an escrow still HELD.
        logger.exception("Payout %s failed at the gateway", payout.id)
        _mark(
            payout,
            gmodels.PAYOUT_FAILED,
            provider=gateway.name,
            reason=str(exc)[:400],
        )
        return None

    payout.provider_ref = state.reference
    payout.provider_status = state.raw_status
    mapped = _PAYOUT_STATUS.get(state.status, gmodels.PAYOUT_PENDING)
    _mark(payout, mapped, provider=gateway.name, reason=state.failure_reason)
    return state.reference


def _mark(
    payout: gmodels.Payout,
    status_value: str,
    *,
    provider: str,
    ref: str | None = None,
    reason: str | None = None,
) -> None:
    payout.status = status_value
    payout.provider = provider
    if ref:
        payout.provider_ref = ref
    if reason:
        payout.failure_reason = reason[:400]
    if status_value == gmodels.PAYOUT_SENT:
        payout.sent_at = gmodels.utcnow()
    payout.updated_at = gmodels.utcnow()


def _user_country(db: Session, user_id: str) -> str | None:
    user = db.query(User).filter(User.id == user_id).first()
    return user.country_code if user else None


# ----------------------------------------------------------------- the sweep


def run_pending_payouts(db: Session, limit: int = 100) -> dict:
    """Finish the payouts that did not finish themselves.

    Three jobs in one pass, because they are the three ways a payout can be
    unfinished:

      * PENDING with a reference  -> ask the gateway whether it landed. RE-READ,
        never re-send: a timeout means we do not know whether the money went,
        and "try again" against that uncertainty is how somebody gets paid
        twice.
      * FAILED under the attempt cap -> send it again. This is the network blip
        case and it is the one that resolves on its own.
      * AWAITING_METHOD with a method now on file -> the creator answered.

    Above the attempt cap a payout is left FAILED and reported. It stops costing
    us a call per sweep and starts costing somebody five minutes of attention,
    which is the correct trade once a thing has failed five times in a row.
    """
    sent = 0
    retried = 0
    stuck = 0

    pending = (
        db.query(gmodels.Payout)
        .filter(
            gmodels.Payout.status == gmodels.PAYOUT_PENDING,
            gmodels.Payout.provider_ref.isnot(None),
        )
        .limit(limit)
        .all()
    )
    for payout in pending:
        gateway = registry.gateway_by_name(payout.provider)
        if gateway is None:
            continue
        try:
            state = gateway.read_payout(payout.provider_ref)
        except GatewayError:
            logger.warning("Could not read payout %s", payout.id)
            continue
        payout.provider_status = state.raw_status
        mapped = _PAYOUT_STATUS.get(state.status, gmodels.PAYOUT_PENDING)
        _mark(payout, mapped, provider=payout.provider, reason=state.failure_reason)
        if mapped == gmodels.PAYOUT_SENT:
            sent += 1
            _notify_paid(db, payout)

    retryable = (
        db.query(gmodels.Payout)
        .filter(
            gmodels.Payout.status.in_((gmodels.PAYOUT_FAILED, gmodels.PAYOUT_NO_METHOD)),
            gmodels.Payout.attempts < settings.payout_max_attempts,
        )
        .limit(limit)
        .all()
    )
    for payout in retryable:
        method = (
            db.query(gmodels.PayoutMethod)
            .filter(gmodels.PayoutMethod.user_id == payout.recipient_user_id)
            .first()
        )
        if method is None:
            continue
        gateway = registry.registry().get(method.country)
        if gateway is None:
            continue
        escrow = db.query(models.Escrow).filter(models.Escrow.id == payout.escrow_id).first()
        if escrow is None:
            continue
        if _send(db, payout, gateway, method, escrow):
            retried += 1

    stuck = (
        db.query(gmodels.Payout)
        .filter(
            gmodels.Payout.status == gmodels.PAYOUT_FAILED,
            gmodels.Payout.attempts >= settings.payout_max_attempts,
        )
        .count()
    )

    db.commit()
    return {"settled": sent, "retried": retried, "needs_attention": stuck}


def _notify_paid(db: Session, payout: gmodels.Payout) -> None:
    if payout.kind != gmodels.PAYOUT_KIND_RELEASE:
        return
    notify(
        db,
        payout.recipient_user_id,
        "payment",
        "Your payment has been sent to your mobile money wallet.",
        link="/earnings",
        params={"key": "payout_sent"},
    )
