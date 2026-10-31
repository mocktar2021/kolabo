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

ONE COUNTRY CAN NOW HAVE TWO GATEWAYS, ONE PER LEG, and that is the change
this module grew for FeexPay. It used to hold a single map: the gateway for
Benin took both the brand's money in and the creator's money out. That held
while one provider did both, and it stopped holding the moment the two legs
had different best answers.

They do. FedaPay's hosted page is the proven way to take a card, and it has
no payout menu at all, which is the reason FeexPay was integrated. FeexPay's
mobile money collection is what the launch markets actually pay with. Forcing
one choice per country means the better collection leg cannot be taken
without also taking a payout leg, and vice versa, and a swap of either drags
the other along behind it.

So: two maps, keyed the same way, selected by `leg`. A country absent from
one and present in the other is an ordinary state and not a misconfiguration.
"""
import logging

from fastapi import status

from app.core.config import settings
from app.core.errors import AppError
from app.modules.payments.gateways import fedapay, feexpay
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.fedapay import FedaPayGateway
from app.modules.payments.gateways.feexpay import FeexPayGateway

logger = logging.getLogger(__name__)

# The two things a gateway can be asked to do, and the key into the maps
# below. Strings rather than an enum to match how `country` and `currency`
# already travel through this module.
COLLECTIONS = "collections"
PAYOUTS = "payouts"
LEGS = (COLLECTIONS, PAYOUTS)

# Set by _build_registry at import, and reassignable — the test suite drops a
# fake gateway in here the same way payments tests already reassign
# service.payment_provider. One seam, one habit.
_registry: dict[str, dict[str, PaymentGateway]] = {}


def _build_registry() -> dict[str, dict[str, PaymentGateway]]:
    """Wire up whatever this deployment has credentials for, per leg.

    An unconfigured gateway is ABSENT, not present-and-broken. That is the same
    rule the YouTube and Anthropic integrations follow in this codebase: a
    feature with no key reports itself unavailable rather than half working. It
    also means a developer running the stack with no FedaPay account gets the
    honest "payments are not configured" refusal instead of a stack trace from
    an HTTP call to an endpoint with an empty bearer token.

    FEDAPAY FILLS BOTH LEGS AND FEEXPAY OVERRIDES ONE, which is the ordering
    that makes this change inert by default. A box with only FedaPay keys is
    routed exactly as it was before this module learned about legs.

    FEEXPAY TAKES COLLECTIONS ONLY, AND ONLY WHEN ASKED. Both halves matter.
    Only when asked, because having a key is not the same as deciding a
    provider should take live money, and settings.feexpay_collections is
    false unless somebody set it. Collections only, because switching the
    payout leg would strand every creator who has already saved a payout
    method: payout_methods.mode holds FedaPay's vocabulary and FeexPay
    accepts a different one. See config.feexpay_collections for the whole
    argument; there is no payout switch here on purpose.
    """
    registry: dict[str, dict[str, PaymentGateway]] = {leg: {} for leg in LEGS}
    if settings.fedapay_secret_key:
        gateway = FedaPayGateway(
            secret_key=settings.fedapay_secret_key,
            webhook_secret=settings.fedapay_webhook_secret,
            sandbox=settings.fedapay_sandbox,
        )
        for country in fedapay.SUPPORTED_COUNTRIES:
            for leg in LEGS:
                registry[leg][country] = gateway
    else:
        logger.info("FEDAPAY_SECRET_KEY is unset; live payments are disabled")

    wanted = [leg for leg, on in (
        (COLLECTIONS, settings.feexpay_collections),
        (PAYOUTS, settings.feexpay_payouts),
    ) if on]
    if wanted:
        if settings.feexpay_api_key and settings.feexpay_shop_id:
            # ONE OBJECT FOR BOTH LEGS when both are switched on, not two.
            # They share a key, a shop and a base url, and two instances
            # would be two HTTP clients and two chances for a future
            # per-instance cache to disagree with itself about the same
            # provider.
            gateway = FeexPayGateway(
                api_key=settings.feexpay_api_key,
                shop_id=settings.feexpay_shop_id,
                webhook_secret=settings.feexpay_webhook_secret,
                sandbox=settings.feexpay_sandbox,
            )
            for leg in wanted:
                for country in feexpay.SUPPORTED_COUNTRIES:
                    registry[leg][country] = gateway
            logger.info(
                "FeexPay is taking %s in %s",
                " and ".join(wanted),
                ", ".join(feexpay.SUPPORTED_COUNTRIES),
            )
        else:
            # LOUD, because this is somebody intending to switch providers and
            # silently not doing it. The quiet version leaves a box routing to
            # FedaPay while its operator believes otherwise, and the way that
            # surfaces is a brand seeing a card page where a mobile money
            # prompt was expected, or a creator never being paid.
            logger.error(
                "FEEXPAY_COLLECTIONS or FEEXPAY_PAYOUTS is on but FEEXPAY_API_KEY or "
                "FEEXPAY_SHOP_ID is unset, so %s are still routed to the previous gateway",
                " and ".join(wanted),
            )
    return registry


def registry(leg: str = COLLECTIONS) -> dict[str, PaymentGateway]:
    """The country map for one leg.

    DEFAULTS TO COLLECTIONS because that is what every caller meant when
    there was only one map, with the single exception of payouts.py, which
    now asks for its own by name. A caller that forgets gets the behaviour it
    had before this split rather than a mixture.
    """
    global _registry
    if not _registry:
        _registry = _build_registry()
    return _registry.get(leg, {})


def reset_registry() -> None:
    """Forget the built registry so the next call rebuilds it from settings."""
    global _registry
    _registry = {}


def set_gateway(country: str, gateway: PaymentGateway, leg: str | None = None) -> None:
    """Install a gateway for one country. The test seam, and nothing else.

    BOTH LEGS BY DEFAULT, which is what keeps every test written before this
    split correct rather than subtly wrong. Those tests install one fake and
    then exercise funding, payouts and the webhook through it; filling only
    the collections map would leave their payouts falling through to the
    legacy provider and the failure would read as a bug in payouts.

    Pass `leg` to install into one map, which is how a test says the two
    halves of a country are served by different providers.
    """
    if leg is None:
        for each in LEGS:
            registry(each)[country] = gateway
        return
    registry(leg)[country] = gateway


def gateway_for(
    country: str | None, currency: str, leg: str = COLLECTIONS
) -> PaymentGateway:
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
    live = registry(leg)
    if not live:
        # NOTHING IS CONFIGURED AT ALL, which is a different failure from "your
        # country is not covered" and has to say so. It used to fall through to
        # the country refusal below, so a deployment that had simply forgotten
        # FEDAPAY_SECRET_KEY told a Beninese brand that payments were not
        # available in Benin — sending whoever debugged it looking at the
        # country routing instead of at an unset environment variable. 503
        # rather than 400: nobody did anything wrong, the server is not
        # finished being set up.
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            code="payments_gateway_not_configured",
            detail=(
                "Online payments are not switched on for this deployment yet. "
                "If you are running it, set FEDAPAY_SECRET_KEY."
            ),
        )
    gateway = live.get(country)
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

    SEARCHES BOTH LEGS, because a provider that takes only payouts still sends
    callbacks about them. Looking in the collections map alone would answer
    None for a payout webhook and the delivery would be acknowledged and
    dropped, which is the quietest way to lose a settlement notice.
    """
    seen: set[int] = set()
    for leg in LEGS:
        for gateway in registry(leg).values():
            if id(gateway) in seen:
                continue
            seen.add(id(gateway))
            if gateway.name == name:
                return gateway
    return None
