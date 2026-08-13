"""Checkout, payout-method and payout-operations endpoints.

MOUNTED UNDER THE SAME /payments PREFIX AS router.py, as a second router rather
than 90 more lines inside the first. payments/router.py is already the longest
router in the codebase and every endpoint on it is about escrow, disputes or
statements — the platform's own view of money. These are about the machinery
that talks to a gateway, they came in together, and they will change together
when a second gateway lands. Splitting them keeps each file about one thing;
FastAPI does not care that two routers share a prefix.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.payments import checkout, gateway_schemas, payouts
from app.modules.payments.gateways import registry

router = APIRouter()


@router.get("/config", response_model=gateway_schemas.PaymentConfigOut)
def payment_config():
    """What the clients need to know before showing a Fund button.

    Unauthenticated on purpose: it carries the PUBLISHABLE key and a list of
    country codes, which is the same information any visitor gets by opening
    the checkout page. Keeping it here rather than baking it into the web and
    mobile builds means rotating a key or opening a country is a backend deploy
    and not two app-store releases.

    `enabled` false is the honest answer for a deployment with no gateway
    configured, and the clients render the mock/dev path from it instead of
    guessing.
    """
    live = registry.registry()
    return {
        "enabled": bool(live),
        "public_key": settings.fedapay_public_key,
        "sandbox": settings.fedapay_sandbox,
        "countries": sorted(live.keys()),
        # Only where there is no gateway AND this is not production. See
        # gateway_schemas.PaymentConfigOut for why the environment check is the
        # load-bearing half of that condition.
        "mock_payments": (not live) and settings.env != "production",
    }


@router.post(
    "/checkout/start",
    response_model=gateway_schemas.PaymentIntentOut,
    status_code=status.HTTP_201_CREATED,
)
def start_checkout(
    payload: gateway_schemas.CheckoutStartIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Begin funding a signed contract. Returns a checkout url to open.

    Replaces POST /payments/escrow/fund wherever a real gateway is configured.
    The escrow does NOT exist yet when this returns — it is created when the
    payment is confirmed, either by the webhook or by the client polling
    GET /payments/checkout/{id}. A 201 here means "we asked", not "they paid".
    """
    return checkout.start_checkout(
        db,
        business_user_id,
        payload.contract_id,
        payer_first_name=payload.payer_first_name,
        payer_last_name=payload.payer_last_name,
        return_url=payload.return_url,
    )


@router.get("/checkout/{intent_id}", response_model=gateway_schemas.PaymentIntentOut)
def read_checkout(
    intent_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Where this payment stands. SETTLES ON READ.

    The client polls this from the return page. It is not merely a status
    lookup: a still-pending intent is re-read from the gateway here, and if the
    money arrived the escrow is created in this request. In practice this is
    the fastest path to a funded contract, and the webhook is the safety net
    for the payer who pays and then closes the tab.
    """
    return checkout.get_intent(db, user_id, intent_id)


@router.get("/payout-method", response_model=gateway_schemas.PayoutMethodOut | None)
def read_payout_method(
    db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    """Where the caller gets paid. Null when they have not told us yet."""
    return payouts.get_payout_method(db, user_id)


@router.put("/payout-method", response_model=gateway_schemas.PayoutMethodOut)
def write_payout_method(
    payload: gateway_schemas.PayoutMethodIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Set or change the wallet a creator is paid into.

    The network (`mode`) is validated against the gateway's closed set here, at
    the form, rather than discovered at payout time — see payouts.set_payout_method
    for why the network is asked for instead of inferred from the number.
    """
    return payouts.set_payout_method(
        db,
        user_id,
        country=payload.country,
        mode=payload.mode,
        phone=payload.phone,
        account_name=payload.account_name,
    )


@router.get("/payout-modes/{country}", response_model=list[str])
def payout_modes(country: str):
    """The networks we can pay out to in a country. Drives the form's dropdown."""
    return list(payouts.valid_modes(country.upper()))


@router.post("/payouts/run")
def run_payouts(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Finish the payouts that did not finish themselves.

    Admin-triggered and on demand, like /payments/escrow/auto-release and
    /payments/disputes/escalate. That makes four jobs with no scheduler behind
    them; this is the one that gets money to creators whose payout hit a
    network failure, so it is the one that most wants a real cron in front of it
    before the pilot. See docs/PAYMENTS_FEDAPAY.md.
    """
    return payouts.run_pending_payouts(db)
