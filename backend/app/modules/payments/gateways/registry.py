"""Which gateway answers for which country, and the refusal when none does.

THE REFUSAL IS THE POINT OF THIS MODULE. FedaPay covers Benin, Togo and Cote
d'Ivoire. country_config.py has seven countries open for registration, and the
five-country pilot list includes Ghana (GHS) and Cameroon (XAF), neither of
which FedaPay serves in any currency. That gap is real and it is not going to
be closed by a code change on our side.

So the choice was: quietly fall back to the mock in the uncovered countries, or
say so. This says so. A Ghanaian brand that clicks Fund gets a sentence telling
them payments are not live in Ghana yet — which is disappointing and true —
rather than a receipt for money nobody collected and a creator waiting on a
payout that will never arrive. Registration stays open in those countries
because a profile is still worth building; only the money path refuses.

Adding a second gateway (Paystack or Flutterwave for GHS, a CEMAC provider for
XAF) is a class implementing gateways.base.PaymentGateway and one line in
_build_registry. No escrow logic changes, because none of it names a vendor.
"""
import logging

from fastapi import status

from app.core.config import settings
from app.core.errors import AppError
from app.modules.payments.gateways import fedapay
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.fedapay import FedaPayGateway

logger = logging.getLogger(__name__)

# Set by _build_registry at import, and reassignable — the test suite drops a
# fake gateway in here the same way payments tests already reassign
# service.payment_provider. One seam, one habit.
_registry: dict[str, PaymentGateway] = {}


def _build_registry() -> dict[str, PaymentGateway]:
    """Wire up whatever this deployment has credentials for.

    An unconfigured gateway is ABSENT, not present-and-broken. That is the same
    rule the YouTube and Anthropic integrations follow in this codebase: a
    feature with no key reports itself unavailable rather than half working. It
    also means a developer running the stack with no FedaPay account gets the
    honest "payments are not configured" refusal instead of a stack trace from
    an HTTP call to an endpoint with an empty bearer token.
    """
    registry: dict[str, PaymentGateway] = {}
    if settings.fedapay_secret_key:
        gateway = FedaPayGateway(
            secret_key=settings.fedapay_secret_key,
            webhook_secret=settings.fedapay_webhook_secret,
            sandbox=settings.fedapay_sandbox,
        )
        for country in fedapay.SUPPORTED_COUNTRIES:
            registry[country] = gateway
    else:
        logger.info("FEDAPAY_SECRET_KEY is unset; live payments are disabled")
    return registry


def registry() -> dict[str, PaymentGateway]:
    global _registry
    if not _registry:
        _registry = _build_registry()
    return _registry


def reset_registry() -> None:
    """Forget the built registry so the next call rebuilds it from settings."""
    global _registry
    _registry = {}


def set_gateway(country: str, gateway: PaymentGateway) -> None:
    """Install a gateway for one country. The test seam, and nothing else."""
    registry()[country] = gateway


def gateway_for(country: str | None, currency: str) -> PaymentGateway:
    """The gateway that can move `currency` in `country`, or a refusal.

    Both arguments are checked, not just the country, because they can
    disagree: a contract priced in GHS with a Beninese buyer is a data bug we
    would rather catch here — where the message can name the currency — than
    discover as a FedaPay 400 halfway through a checkout.
    """
    if not country:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payments_country_unknown",
            detail=(
                "We could not tell which country this payment belongs to. "
                "Please complete your profile country and try again."
            ),
        )
    gateway = registry().get(country)
    if gateway is None:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payments_country_unsupported",
            detail=(
                f"Online payments are not available in {country} yet. "
                "We are working on it and will let you know as soon as it opens."
            ),
        )
    if not gateway.supports(country, currency):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="payments_currency_unsupported",
            detail=(
                f"We cannot process {currency} payments in {country} yet. "
                "Please contact support if you think this is a mistake."
            ),
        )
    return gateway


def gateway_by_name(name: str) -> PaymentGateway | None:
    """Find a configured gateway by its own name.

    The webhook path needs this: a webhook arrives addressed to a provider, not
    to a country, and it must be verified by the same gateway object that holds
    that provider's secret.
    """
    for gateway in registry().values():
        if gateway.name == name:
            return gateway
    return None
