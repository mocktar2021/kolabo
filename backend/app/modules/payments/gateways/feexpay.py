"""The FeexPay HTTP client. BJ, TG, CI, SN, and the payout leg is the point.

WHY THIS EXISTS AT ALL. Until this file there was no payout path in the
backend for any country: the only adapter was FedaPay, whose live dashboard
never grew a payouts menu after three weeks of asking, so a creator could be
hired, deliver, have the brand approve, and reach a Payout row that no gateway
could ever send. FeexPay is the provider where both legs are proven.

EVERYTHING HERE WAS MEASURED, NOT READ, except where a comment says otherwise.
FeexPay's own OpenAPI declares empty `properties` for the payout and
request-to-pay DTOs, so it is useless as a schema source; the bodies below came
from POSTing `{}` and reading the 400, which names every required field and its
constraints. See claude/kolabo-feexpay-sandbox-proven-1019.md.

THE THREE THINGS THAT MAKE THIS NOT A COPY OF fedapay.py:

1. THE PAYOUT SHAPE IS DIFFERENT PER COUNTRY, and there is no convention to
   lean on. Benin posts to one global endpoint and names the operator in a
   `network` field as `MTN` or `MOOV`. Togo posts to its own endpoint and names
   it as `MOOV TG` or `TOGOCOM TG`, uppercase, with a space. Cote d'Ivoire has
   no `network` field at all because the path carries the operator. An adapter
   that assumes one convention works in exactly one country, so the convention
   lives in _PAYOUT_ROUTES below rather than in code.

2. THERE ARE HARD AMOUNT LIMITS and this is the first thing in the codebase
   that knows about them. 10 to 1,000,000 in the currency's own units, which
   for XOF means a single payout cannot settle more than one million francs.
   That is KOL-126: the gateway's ceiling caps the largest contract Kolabo can
   settle and nothing anywhere noticed. Checked here, before the call, so the
   failure names the ceiling instead of arriving as an opaque 400.

3. `motif` IS CAPPED AT 30 CHARACTERS and the caller already exceeds it.
   payouts._send passes "Kolabo payout for contract <8 chars>", which is 35.
   Passing that through unchanged would have 400'd every payout in production,
   on every network, in every country. It is truncated here rather than fixed
   at the call site on purpose: the cap is this vendor's, the caller should not
   have to know it, and a second gateway with a different cap would otherwise
   drag the call site around behind it.

AMOUNTS ARE INTEGERS IN THE CURRENCY'S OWN UNITS, as base.py requires. XOF has
no minor unit and FeexPay also wants whole francs, so there is no conversion
anywhere in this file and no times-one-hundred waiting to be got wrong.
"""
import logging
from typing import Any

import httpx

from app.modules.payments.gateways.base import (
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_SENT,
    CollectionStart,
    CollectionState,
    GatewayError,
    PayoutState,
    PayoutTarget,
)

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox-api.feexpay.me"
LIVE_BASE_URL = "https://api-v2.feexpay.me"

# Countries where FeexPay carries ACTIVATED channels, read off the production
# dashboard for shop EGCxXP0ydLLspx0 on 23 October 2026. Activated, not merely
# listed in a selector: the two were conflated in both directions for a month
# and Senegal was wrongly excluded because of it. See
# claude/kolabo-launch-countries-1023.md.
#
# Matches the four open markets in core/country_config.py, and that is not a
# coincidence to be tidied away: the market list IS the payment list, because a
# country where money cannot move is a signup that ends at a payout form which
# cannot pay.
SUPPORTED_COUNTRIES = ("BJ", "TG", "CI", "SN")
# One currency, and it is the licence rather than a product choice. FeexPay's
# agrement is BCEAO EP.CI.006/2025, so GHS, XAF and NGN were never payable
# here whatever a dashboard country selector shows.
SUPPORTED_CURRENCIES = ("XOF",)

# Measured, by POSTing {} and reading the validation error. Both ends are
# inclusive.
MIN_AMOUNT = 10
MAX_AMOUNT = 1_000_000
# Measured the same way. Exceeding it is a 400, not a truncation on their side.
MOTIF_MAX_CHARS = 30


class _Route:
    """Where one payout network is sent, and how it names itself.

    `network` is None where the endpoint path already carries the operator,
    which is the Cote d'Ivoire and Celtiis shape. Sending a `network` field to
    those endpoints is not merely redundant, it is a field they do not declare.
    """

    __slots__ = ("path", "network", "measured")

    def __init__(self, path: str, network: str | None = None, *, measured: bool = True):
        self.path = path
        self.network = network
        self.measured = measured


# mode -> where it goes. THE MODE STRING IS THE STORED ONE: payout_methods
# validates a creator's choice against payout_modes() below and writes it to
# payout_methods.mode, so changing a key here orphans every row that holds it.
# Treat these as data, not as labels.
#
# MEASURED ROWS carry a proven round trip in sandbox, in the country named.
# INFERRED ROWS do not, and say so, because the failure mode of a wrong value
# is not a clean refusal: a payout down a network that does not exist is a
# support item days later.
_PAYOUT_ROUTES: dict[str, dict[str, _Route]] = {
    # Benin. One global endpoint, operator in a `network` field. MTN proven
    # end to end on 19 October; MOOV is the same endpoint and the same field
    # with the other declared value.
    "BJ": {
        "MTN": _Route("/api/payouts/public/transfer/global", "MTN"),
        "MOOV": _Route("/api/payouts/public/transfer/global", "MOOV"),
        # Its own endpoint, operator in the path. Declared in their spec,
        # never exercised.
        "CELTIIS_BJ": _Route("/api/payouts/public/celtiis_bj", measured=False),
    },
    # Togo. Own endpoint, and the network values are uppercase WITH A SPACE,
    # which is the detail that breaks an adapter written from the Benin shape.
    # Moov TG proven end to end on 19 October.
    "TG": {
        "MOOV TG": _Route("/api/payouts/public/togo", "MOOV TG"),
        "TOGOCOM TG": _Route("/api/payouts/public/togo", "TOGOCOM TG", measured=False),
    },
    # Cote d'Ivoire. One endpoint per operator, no `network` field anywhere.
    # MTN CI proven end to end on 19 October. orange_ci returned 503 in
    # sandbox and is live on the production dashboard, so it is routed here and
    # marked unmeasured rather than withheld.
    "CI": {
        "MTN_CI": _Route("/api/payouts/public/mtn_ci"),
        "MOOV_CI": _Route("/api/payouts/public/moov_ci", measured=False),
        "WAVE_CI": _Route("/api/payouts/public/wave_ci", measured=False),
        "ORANGE_CI": _Route("/api/payouts/public/orange_ci", measured=False),
    },
    # SENEGAL IS INFERRED IN ITS ENTIRETY. Founder's call, made knowingly on
    # 24 October: Senegal is already open in the UI and leaving it out of the
    # adapter means a Senegalese creator with no payout path at all, which is
    # the worse of the two failures.
    #
    # WHAT IS GUESSED, precisely, so that measuring it is a small diff rather
    # than a re-reading of this file. The three operators come from the
    # production dashboard, which shows Orange, Free, Wave and Card activated
    # for Senegal. The endpoint paths and the absent `network` field follow the
    # Cote d'Ivoire pattern, where one path per operator carries the operator
    # name. Nothing here has been POSTed to, so if FeexPay named these
    # differently every Senegalese payout fails at the first attempt with a
    # 404 or a validation error, is marked FAILED with the reason on the Payout
    # row, and becomes visible rather than lost. That bound is the reason this
    # is an acceptable risk and not a reckless one.
    #
    # Measuring it is one `curl` per operator with a deliberately invalid
    # reference, the technique from claude/kolabo-feexpay-production-live-1021.md
    # that proves a route exists without moving money.
    "SN": {
        "ORANGE_SN": _Route("/api/payouts/public/orange_sn", measured=False),
        "FREE_SN": _Route("/api/payouts/public/free_sn", measured=False),
        "WAVE_SN": _Route("/api/payouts/public/wave_sn", measured=False),
    },
}

PAYOUT_STATUS_PATH = "/api/payouts/status/public/{reference}"

# FeexPay's vocabulary -> ours. UPPERCASE because theirs is: statuses came back
# as SUCCESSFUL and PENDING, not the lowercase FedaPay uses, and the lookup
# below upper-cases before reading this so a change of case on their side is
# not an outage.
#
# ANYTHING UNRECOGNISED IS PENDING, AND LOGGED. The same rule fedapay.py
# follows and for the same reason: an unknown word must never be read as
# success, and reading it as failure would mark a creator unpaid on a string we
# simply have not seen before. The failure vocabulary in particular is
# UNMEASURED, because no payout has ever been made to fail on purpose. FAILED
# and FAILURE are both mapped on the chance that either is the word.
_PAYOUT_STATUS = {
    "SUCCESSFUL": PAYOUT_SENT,
    "SUCCESS": PAYOUT_SENT,
    "PENDING": PAYOUT_PENDING,
    "PROCESSING": PAYOUT_PENDING,
    "FAILED": PAYOUT_FAILED,
    "FAILURE": PAYOUT_FAILED,
    "CANCELED": PAYOUT_FAILED,
    "CANCELLED": PAYOUT_FAILED,
}


def _fee(body: dict) -> int | None:
    """What FeexPay charged us, or None when it did not say.

    NONE IS NOT ZERO, which base.py spells out and this function exists to
    respect. The fee has never been measured on this provider: the balance
    before and after a payout was not read in the sandbox session, so the
    margin model still rests on the published 1.7% in and 1% out for Benin and
    the markedly worse 3% in and 2.4% out for Togo. Reading a missing fee as
    free would understate our own cost silently, and further with every row.

    So this reads the keys a fee could plausibly arrive under and returns None
    otherwise. It does not compute, estimate or default.
    """
    for key in ("fee", "fees", "frais", "commission"):
        raw = body.get(key)
        if raw is None:
            continue
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            logger.warning("FeexPay reported a %s of %r, which is not a number", key, raw)
            return None
    return None


class FeexPayGateway:
    """A thin, synchronous FeexPay client.

    Synchronous for the same reason FedaPayGateway is: everything that calls it
    is sync SQLAlchemy inside sync FastAPI handlers, and an async client would
    buy an event loop per request and nothing else.
    """

    name = "feexpay"

    def __init__(
        self,
        api_key: str,
        shop_id: str,
        *,
        webhook_secret: str = "",
        sandbox: bool = True,
        timeout: float = 20.0,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        # REQUIRED ON EVERY CALL, collection and payout alike. An absent shop
        # is a 400 on every request rather than a degraded mode, so it is a
        # constructor argument and not an option.
        self.shop_id = shop_id
        self.webhook_secret = webhook_secret
        self.sandbox = sandbox
        self.base_url = (base_url or (SANDBOX_BASE_URL if sandbox else LIVE_BASE_URL)).rstrip("/")
        self.timeout = timeout
        # The test seam, same habit as fedapay.py: the suite hands in an
        # httpx.Client on a MockTransport so every path here runs against
        # recorded FeexPay payloads with no network and no keys.
        self._client = client

    # ------------------------------------------------------------------ http

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            if self._client is not None:
                response = self._client.request(
                    method, url, json=payload, headers=headers, timeout=self.timeout
                )
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(method, url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            # RETRYABLE, AND ON A PAYOUT THAT MEANS RE-READ, NOT RE-SEND. A
            # timeout leaves us not knowing whether the money left, and
            # FeexPay offers no idempotency key, so a blind retry is how a
            # creator gets paid twice. payouts.py persists the reference before
            # it believes anything, and the sweep re-reads.
            raise GatewayError(f"FeexPay timed out on {method} {path}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise GatewayError(f"Could not reach FeexPay: {exc}", retryable=True) from exc

        if response.status_code == 401:
            # Called out separately from the other 4xx because of what it
            # usually means here, which is not a wrong key. The payout API is
            # gated on an IP allowlist scoped PER BOUTIQUE, so a correct key
            # from an unregistered address fails exactly like a bad one. A
            # payout that starts failing after a server move is this, every
            # time, and the message should say so before somebody rotates a
            # working key over it.
            raise GatewayError(
                "FeexPay refused the credentials. Check the API key, and check that this "
                "server's egress IP is on the boutique's IP list: the allowlist is scoped "
                "per boutique, so a new shop needs its own row.",
                retryable=False,
                status=401,
            )
        if response.status_code >= 500:
            raise GatewayError(
                f"FeexPay returned {response.status_code} on {method} {path}",
                retryable=True,
                status=response.status_code,
            )
        if response.status_code >= 400:
            # Our request being wrong. Retrying produces the same answer
            # forever, so it is not retryable, and the body is carried into the
            # message because FeexPay's validation errors name the offending
            # field and losing that turns a two minute fix into an afternoon.
            raise GatewayError(
                f"FeexPay rejected {method} {path}: {response.status_code} {response.text[:400]}",
                retryable=False,
                status=response.status_code,
            )
        if not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise GatewayError("FeexPay returned a body that is not JSON", retryable=True) from exc
        if not isinstance(body, dict):
            raise GatewayError(f"FeexPay returned a {type(body).__name__}, not an object")
        return body

    # ------------------------------------------------------------ capability

    def supports(self, country: str, currency: str) -> bool:
        return country in SUPPORTED_COUNTRIES and currency in SUPPORTED_CURRENCIES

    def payout_modes(self, country: str) -> tuple[str, ...]:
        """The closed set a creator's choice is validated against.

        Validated when they SAVE it, not when we try to pay them, which is the
        whole reason this is a method on the gateway rather than a list in the
        UI. See payments/payouts.set_payout_method.
        """
        return tuple(_PAYOUT_ROUTES.get(country, {}))

    # ---------------------------------------------------------------- payout

    def _check_amount(self, amount: int) -> None:
        if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
            # KOL-126 made visible. Not retryable: the number will not shrink
            # on a second attempt, and the sweep should stop rather than bill
            # us for five identical refusals.
            raise GatewayError(
                f"FeexPay accepts {MIN_AMOUNT} to {MAX_AMOUNT} per movement and this is "
                f"{amount}. A contract above the ceiling has to be settled in parts, which "
                "nothing in the product does yet.",
                retryable=False,
            )

    def send_payout(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        target: PayoutTarget,
        merchant_reference: str | None = None,
    ) -> PayoutState:
        self._check_amount(amount)
        if currency not in SUPPORTED_CURRENCIES:
            raise GatewayError(
                f"FeexPay cannot pay out {currency}; its licence covers {SUPPORTED_CURRENCIES[0]}",
                retryable=False,
            )
        routes = _PAYOUT_ROUTES.get(target.country)
        if not routes:
            raise GatewayError(
                f"FeexPay has no payout route for {target.country}", retryable=False
            )
        route = routes.get(target.mode)
        if route is None:
            raise GatewayError(
                f"{target.mode!r} is not a FeexPay payout network in {target.country}. "
                f"Known: {', '.join(sorted(routes))}",
                retryable=False,
            )
        if not route.measured:
            # Not a refusal. A line in the log that is worth having the first
            # time one of these is used in anger, because an inferred route is
            # the likeliest explanation for a payout that failed on its first
            # attempt with a 404.
            logger.warning(
                "FeexPay payout on an UNMEASURED route: %s %s. If this fails, the endpoint "
                "or network value may simply be wrong rather than the payout being refused.",
                target.country,
                target.mode,
            )

        body: dict[str, Any] = {
            "shop": self.shop_id,
            "amount": amount,
            "phoneNumber": target.phone,
            # TRUNCATED, NOT VALIDATED. See the module docstring: the caller
            # already passes 35 characters and this cap is FeexPay's, not the
            # product's, so refusing here would mean every payout fails over a
            # vendor detail the call site has no business knowing.
            "motif": description[:MOTIF_MAX_CHARS],
        }
        if route.network is not None:
            body["network"] = route.network
        if merchant_reference:
            # OURS, OPAQUE TO THEM, AND THE WHOLE OF RECONCILIATION. It came
            # back null in the sandbox read, so nothing may depend on reading
            # it off a status response, but it means every movement at FeexPay
            # carries Kolabo's own Payout id. Without it, matching their
            # statement to our rows is amounts and timestamps, which stops
            # being possible the first time two creators are paid the same
            # figure in the same minute.
            body["callback_info"] = merchant_reference

        created = self._request("POST", route.path, body)
        reference = _reference_of(created)
        if not reference:
            # The money may well have moved. Loud, and deliberately not
            # swallowed: a sent payout whose reference we never captured is the
            # one state no sweep can clean up, because there is nothing to
            # re-read.
            raise GatewayError(
                f"FeexPay accepted a payout on {route.path} and returned no reference. "
                f"Body keys: {sorted(created)}"
            )
        return _payout_state(created, reference, fallback_amount=amount, fallback_currency=currency)

    def read_payout(self, reference: str) -> PayoutState:
        body = self._request("GET", PAYOUT_STATUS_PATH.format(reference=reference))
        return _payout_state(body, reference)

    # ------------------------------------------------------------ collection

    def start_collection(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        callback_url: str,
        payer_country: str,
        payer_first_name: str,
        payer_last_name: str,
        payer_phone: str | None = None,
        payer_email: str | None = None,
        merchant_reference: str | None = None,
        metadata: dict | None = None,
    ) -> CollectionStart:
        """NOT WIRED YET, AND THE REASON IS A SHAPE MISMATCH, NOT AN OVERSIGHT.

        CollectionStart requires a `checkout_url`, because the whole funding
        flow is a redirect: Checkout.tsx sends the brand's browser out of the
        app to the provider's hosted page, and checkout.py's duplicate-funding
        guard literally queries `checkout_url IS NOT NULL`.

        The only FeexPay collection endpoint proven in sandbox is
        POST /api/transactions/public/requesttopay/{network}, which is not that
        shape at all. It needs the payer's phone number AND their operator in
        the path, pushes a prompt to that handset, and returns no URL. This
        interface does not even carry a network to put in the path.

        Closing that gap is either a hosted checkout endpoint nobody has looked
        for yet, which keeps this a one-file adapter, or a network picker and a
        polling screen in Kolabo's own UI on web and mobile, which is not.
        Until that is settled, refusing here is the honest answer: the registry
        does not route collections to this gateway, and nothing calls this.

        It raises rather than returning something empty because a
        CollectionStart with a blank checkout_url would be stored, reused by
        the guard above, and sent to a brand as a link to nowhere.
        """
        raise GatewayError(
            "FeexPay collections are not wired up. Its proven endpoint pushes a prompt to a "
            "handset and returns no checkout URL, which the funding flow requires. Fund "
            "through the configured collection gateway instead.",
            retryable=False,
        )

    def read_collection(self, reference: str) -> CollectionState:
        """Also not wired, and for the same reason as start_collection above.

        The endpoint is known, GET /api/transactions/public/single/status/
        {reference}, and two of its behaviours are already measured and worth
        writing down before anybody implements this:

        A collection MAY BE TERMINAL ON CREATION. Cote d'Ivoire returned
        SUCCESSFUL synchronously from the POST; Togo returned PENDING and
        settled on a later read. Both are normal, so code that always polls
        wastes a call and code that never polls loses Togo.

        `responsecode` IS A MIRROR OF `status`, NOT AN INDEPENDENT SIGNAL. It
        reads -1 while pending and SUCCESSFUL when terminal. A non-zero code
        that does not mean failure is exactly the field that gets misread.
        Branch on `status` only.
        """
        raise GatewayError(
            "FeexPay collections are not wired up; nothing should be reading one.",
            retryable=False,
        )

    # --------------------------------------------------------------- webhook

    def verify_webhook(self, raw_body: bytes, headers: dict) -> dict:
        """REFUSES, because the scheme has never been observed.

        FeexPay's callback was never configured during the sandbox work, so the
        payload shape and whatever signs it are both unknown. There are two
        ways to write this function without that knowledge and one of them is
        dangerous:

        GUESS AN HMAC SCHEME. If the guess is wrong in the strict direction
        every real webhook is rejected, which looks like an outage. If it is
        wrong in the permissive direction, anyone who can POST to the URL can
        tell Kolabo that an escrow was funded. The second failure is silent and
        it is the one that costs money.

        REFUSE UNTIL MEASURED, which is this. It costs almost nothing, and that
        is a property of the architecture rather than luck: a webhook in this
        codebase is only ever permission to ask. Every conclusion that money
        moved comes from read_payout or read_collection over a connection we
        opened, to a host we chose, with our own bearer token. So with no
        webhook the sweeps container reaches the same answer on its next pass,
        a few minutes later instead of a few seconds.

        Measuring it is small: point the callback at a capture URL, run one
        payout, and read the headers and body that arrive.
        """
        raise GatewayError(
            "FeexPay webhook verification is not implemented: the signature scheme has not "
            "been observed, and guessing one would either reject every real callback or "
            "accept forged ones. Payout and collection state is re-read from the API "
            "instead, which is where this codebase takes its answers from anyway.",
            retryable=False,
        )


# --------------------------------------------------------------------- parsing


def _reference_of(body: dict) -> str:
    """FeexPay's id for a movement, under whichever key it used this time.

    THERE IS NO SINGLE FORMAT AND NO SINGLE KEY. Three reference formats were
    observed in one sandbox session: a UUID, twenty uppercase hex characters,
    and a twelve character mixed-case token. So this returns an opaque string
    and the column behind it is Text, never a UUID type. Anything that parses
    one of these is wrong.
    """
    for key in ("reference", "transaction_id", "transactionId", "id", "ref"):
        value = body.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _payout_state(
    body: dict,
    reference: str,
    *,
    fallback_amount: int | None = None,
    fallback_currency: str | None = None,
) -> PayoutState:
    """One payout, as FeexPay describes it.

    PARSED SEPARATELY FROM A COLLECTION, deliberately. The two status payloads
    are different shapes: a collection response carries `operator_id` and
    `comment` and a payout response does not. One model over both would have to
    make every field optional, which is how a missing field becomes a None that
    nothing notices.

    The fallbacks exist for the create response, which may describe the payout
    only partially. Falling back to what we ASKED for is right there and wrong
    on a status read, which is why they default to None: a status read that
    reports no amount should surface a zero somebody investigates rather than
    quietly echo the figure we hoped for.
    """
    raw_status = str(body.get("status", "") or "")
    status = _PAYOUT_STATUS.get(raw_status.upper())
    if status is None:
        logger.warning(
            "Unknown FeexPay payout status %r on %s; treating as pending", raw_status, reference
        )
        status = PAYOUT_PENDING

    amount_raw = body.get("amount")
    if amount_raw is None:
        amount = fallback_amount if fallback_amount is not None else 0
    else:
        try:
            amount = int(float(amount_raw))
        except (TypeError, ValueError):
            logger.warning("FeexPay reported an amount of %r on %s", amount_raw, reference)
            amount = fallback_amount if fallback_amount is not None else 0

    currency = str(body.get("currency") or fallback_currency or SUPPORTED_CURRENCIES[0]).upper()

    return PayoutState(
        reference=_reference_of(body) or reference,
        status=status,
        amount=amount,
        currency=currency,
        raw_status=raw_status,
        # `message` and `motif` are the two fields a reason has been seen in.
        # Never `responsecode`, which mirrors the status and would read as a
        # failure reason on a perfectly successful payout.
        failure_reason=(
            (body.get("message") or body.get("motif")) if status == PAYOUT_FAILED else None
        ),
        fee=_fee(body),
    )
