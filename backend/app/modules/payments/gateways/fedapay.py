"""The FedaPay gateway. Benin, Togo, Cote d'Ivoire.

WHY FEDAPAY AND NOT KKIAPAY, in one sentence, because the reason is structural
and somebody will ask again in six months: KKiaPay has no API that sends money
to a third party's wallet — its `/merchant/payouts/schedule` endpoint schedules
settlement of your own balance into your own registered account — and a
marketplace that cannot pay its creators from code is not a marketplace. See
docs/PAYMENTS_FEDAPAY.md for the full comparison and the numbers.

COLLECTION IS A HOSTED REDIRECT, in three calls:

    POST /v1/transactions            create it, get an id
    POST /v1/transactions/{id}/token get a single-use 24h checkout url
    GET  /v1/transactions/{id}       later, ask what actually happened

THE TWO POST RESPONSES ARE NOT THE SAME SHAPE, which is worth stating up front
because assuming they were is what broke the first real sandbox checkout. The
transaction is wrapped in a resource envelope ({"v1/transaction": {...}}); the
token is FLAT ({"token": ..., "url": ...}). _unwrap handles the first,
_checkout_url the second, and neither is a general-purpose reader.

PAYOUT IS TWO STEPS ON PURPOSE:

    POST /v1/payouts                 create it. NOTHING IS SENT YET.
    PUT  /v1/payouts/start           now send it.

That gap is a feature and this module keeps it visible rather than hiding both
behind one call. A created-but-unstarted payout is a durable, inspectable
record of an intention to pay, which is exactly what a release needs when the
network is down: the row exists, the money has not moved, and starting it later
is idempotent in a way that "retry the whole operation" is not.

AMOUNTS. FedaPay takes whole units and XOF has no minor unit, so the integers
in this codebase go over the wire unchanged. There is deliberately no scaling
factor anywhere in this file; adding one for a future minor-unit currency is a
change to make with a test, not a helper to leave lying around.
"""
import logging
from typing import Any

import httpx

from app.modules.payments.gateways import signature
from app.modules.payments.gateways.base import (
    CANCELED,
    FAILED,
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_SENT,
    PENDING,
    SUCCEEDED,
    CollectionStart,
    CollectionState,
    GatewayError,
    PayoutState,
    PayoutTarget,
)

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox-api.fedapay.com/v1"
LIVE_BASE_URL = "https://api.fedapay.com/v1"

# Countries this gateway can both COLLECT and PAY OUT in. Both directions
# matter and the list is the intersection, not the union: a country where we
# can take a brand's money but cannot pay the creator is worse than one we do
# not serve at all, because the money arrives and then strands.
#
# Senegal is deliberately absent even though FedaPay lists Senegalese methods.
# Its published matrix has collection on free_sn only and payout on wave_sn and
# orange_sn — the two halves do not meet, so a Senegalese collaboration cannot
# complete. It goes back in when FedaPay confirms a network that does both.
SUPPORTED_COUNTRIES = ("BJ", "TG", "CI")
SUPPORTED_CURRENCIES = ("XOF",)

# Network strings FedaPay accepts as a payout `mode`, per country. This is the
# closed set payout_methods.py validates a creator's choice against, so a bad
# value is refused when they save it rather than discovered when we try to pay
# them.
PAYOUT_MODES: dict[str, tuple[str, ...]] = {
    "BJ": ("mtn_open", "moov", "sbin"),
    "TG": ("moov_tg", "togocel"),
    "CI": ("mtn_ci", "moov_ci", "wave_ci", "orange_ci"),
}

# FedaPay's vocabulary -> ours. Anything not in here is treated as PENDING and
# logged, which is the only safe default: an unrecognised status must never be
# read as success, and treating it as failure would resolve an escrow on a
# word we simply have not seen before.
_COLLECTION_STATUS = {
    "pending": PENDING,
    "approved": SUCCEEDED,
    # `transferred` means the funds reached our merchant balance. It is a later
    # stage of the same success, not a different outcome.
    "transferred": SUCCEEDED,
    "declined": FAILED,
    "canceled": CANCELED,
    "cancelled": CANCELED,
    # A refund is money going back. Whatever it says about the past, an intent
    # in this state must not fund an escrow.
    "refunded": FAILED,
}

_PAYOUT_STATUS = {
    "pending": PAYOUT_PENDING,
    "started": PAYOUT_PENDING,
    "processing": PAYOUT_PENDING,
    "scheduled": PAYOUT_PENDING,
    "sent": PAYOUT_SENT,
    "failed": PAYOUT_FAILED,
    "canceled": PAYOUT_FAILED,
    "cancelled": PAYOUT_FAILED,
}


def _unwrap(payload: Any, *keys: str) -> dict:
    """Get the resource out of whatever envelope it arrived in.

    FedaPay returns resources keyed by name — {"v1/transaction": {...}} — but
    the envelope is not documented as a stable contract and the SDKs differ on
    whether they see it. So: look for the keys we expect, and fall back to the
    body itself if it already looks like the resource. Defensive rather than
    clever, because the alternative is a KeyError in the middle of a payment.

    FOR RESOURCES ONLY — transactions and payouts. The token endpoint is not
    one and must not be read with this; see _checkout_url for what went wrong
    when it was.
    """
    if not isinstance(payload, dict):
        raise GatewayError(f"Unexpected response body: {type(payload).__name__}")
    for key in keys:
        inner = payload.get(key)
        if isinstance(inner, dict):
            return inner
    if "id" in payload or "status" in payload:
        return payload
    raise GatewayError(f"Could not find a resource in the response (keys: {list(payload)[:8]})")


def _checkout_url(payload: Any) -> str | None:
    """The hosted checkout url out of a token response, or None.

    DELIBERATELY NOT _unwrap, and the distinction cost a full sandbox session
    to find. The token endpoint does not answer with the resource envelope the
    rest of the API uses. It answers FLAT:

        {"token": "...", "url": "https://process.fedapay.com/..."}

    Handed that, _unwrap looks for a dict under "v1/token" (absent), then under
    "token" — which IS present but is a STRING, so it is skipped — then finds
    neither "id" nor "status" to fall back on, and raises:

        Could not find a resource in the response (keys: ['token', 'url'])

    Which is exactly what every checkout against the real sandbox did, after
    the transaction had already been created at FedaPay. The unit test did not
    catch it because its mock returned the wrapped shape: the fixture encoded a
    GUESS about FedaPay rather than an observation of it, and the guess was
    wrong. That is the general lesson and it is why the test now asserts both
    shapes explicitly.

    Reads the flat shape first, because that is what FedaPay actually sends,
    and still accepts a wrapped one — the envelope is not a documented contract
    either way, and their own SDKs differ on whether they see it. Returns None
    rather than raising so the caller can give the failure a sentence about
    checkout urls instead of one about resources.
    """
    if not isinstance(payload, dict):
        return None
    url = payload.get("url")
    if isinstance(url, str) and url:
        return url
    for key in ("v1/token", "token"):
        inner = payload.get(key)
        if isinstance(inner, dict):
            nested = inner.get("url")
            if isinstance(nested, str) and nested:
                return nested
    return None


class FedaPayGateway:
    """A thin, synchronous FedaPay client.

    Synchronous because everything that calls it is: the escrow service is
    sync SQLAlchemy inside sync FastAPI handlers, and threading an async client
    through that would mean an event loop per request for no gain. httpx's sync
    client gives us timeouts and connection reuse, which is what we actually
    need from it.
    """

    name = "fedapay"

    def __init__(
        self,
        secret_key: str,
        *,
        webhook_secret: str = "",
        sandbox: bool = True,
        timeout: float = 20.0,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.sandbox = sandbox
        self.base_url = (base_url or (SANDBOX_BASE_URL if sandbox else LIVE_BASE_URL)).rstrip("/")
        self.timeout = timeout
        # An injectable client is the test seam. The suite hands in an
        # httpx.Client wired to a MockTransport, so every path in this file is
        # exercised against recorded FedaPay payloads with no network at all.
        self._client = client

    # ------------------------------------------------------------------ http

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-FedaPay-Lib": "kolabo-backend",
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
            # Retryable, and the distinction earns its keep here: a timeout on
            # a payout means we do not know whether it was sent, so the sweep
            # must re-READ it rather than re-SEND it. See payouts.py.
            raise GatewayError(f"FedaPay timed out on {method} {path}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise GatewayError(f"Could not reach FedaPay: {exc}", retryable=True) from exc

        if response.status_code >= 500:
            raise GatewayError(
                f"FedaPay returned {response.status_code} on {method} {path}",
                retryable=True,
                status=response.status_code,
            )
        if response.status_code >= 400:
            # 4xx is our request being wrong. Retrying it will produce the same
            # answer forever, so it is marked not-retryable and the body is
            # carried into the message — FedaPay's validation errors name the
            # field, and losing that turns a two-minute fix into an afternoon.
            raise GatewayError(
                f"FedaPay rejected {method} {path}: {response.status_code} {response.text[:400]}",
                retryable=False,
                status=response.status_code,
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise GatewayError("FedaPay returned a body that is not JSON", retryable=True) from exc

    # ------------------------------------------------------------ capability

    def supports(self, country: str, currency: str) -> bool:
        return country in SUPPORTED_COUNTRIES and currency in SUPPORTED_CURRENCIES

    def payout_modes(self, country: str) -> tuple[str, ...]:
        return PAYOUT_MODES.get(country, ())

    # ------------------------------------------------------------ collection

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
        body: dict[str, Any] = {
            "description": description,
            "amount": amount,
            # A NESTED OBJECT, not a bare string. FedaPay wants {"iso": "XOF"}
            # and answers a plain "XOF" with a validation error that does not
            # say so.
            "currency": {"iso": currency},
            "callback_url": callback_url,
            "customer": {
                "firstname": payer_first_name,
                "lastname": payer_last_name,
                "phone_number": {"number": payer_phone, "country": payer_country.lower()},
            },
        }
        if payer_email:
            body["customer"]["email"] = payer_email
        if merchant_reference:
            # Our own id, echoed back on every read and every webhook. This is
            # what makes reconciliation possible without trusting anything the
            # webhook says: given a merchant_reference we can find our row, and
            # given our row we can find theirs.
            body["merchant_reference"] = merchant_reference
        if metadata:
            body["custom_metadata"] = metadata

        created = _unwrap(self._request("POST", "/transactions", body), "v1/transaction", "transaction")
        transaction_id = created.get("id")
        if transaction_id is None:
            raise GatewayError("FedaPay created a transaction with no id")

        # NOT _unwrap — the token body is flat, not an enveloped resource. See
        # _checkout_url, which exists because reading it with _unwrap failed
        # every checkout against the real sandbox while the unit test passed.
        checkout_url = _checkout_url(
            self._request("POST", f"/transactions/{transaction_id}/token", {})
        )
        if not checkout_url:
            # The transaction EXISTS at this point, which is why the caller
            # commits the intent row before calling us: an orphan transaction
            # at FedaPay with no local record is the one state nobody can
            # reconcile.
            raise GatewayError(
                f"FedaPay returned no checkout url for transaction {transaction_id}"
            )

        return CollectionStart(
            reference=str(transaction_id),
            checkout_url=checkout_url,
            # Documented as 24 hours and single use. Carried out so the caller
            # can show an honest expiry rather than inventing one.
            expires_in_seconds=24 * 3600,
        )

    def read_collection(self, reference: str) -> CollectionState:
        body = _unwrap(
            self._request("GET", f"/transactions/{reference}"), "v1/transaction", "transaction"
        )
        raw_status = str(body.get("status", "")).lower()
        status = _COLLECTION_STATUS.get(raw_status)
        if status is None:
            logger.warning(
                "Unknown FedaPay transaction status %r on %s; treating as pending",
                raw_status,
                reference,
            )
            status = PENDING
        return CollectionState(
            reference=str(body.get("id", reference)),
            status=status,
            amount=int(body.get("amount") or 0),
            currency=_currency_iso(body),
            raw_status=raw_status,
            failure_reason=body.get("last_error_code") or body.get("mode"),
            metadata=body.get("custom_metadata") or {},
            fee=_fee_amount(body),
        )

    # ---------------------------------------------------------------- payout

    def send_payout(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        target: PayoutTarget,
        merchant_reference: str | None = None,
    ) -> PayoutState:
        body: dict[str, Any] = {
            "amount": amount,
            "currency": {"iso": currency},
            "mode": target.mode,
            "description": description,
            "customer": {
                "firstname": target.first_name,
                "lastname": target.last_name,
                "phone_number": {"number": target.phone, "country": target.country.lower()},
            },
        }
        if target.email:
            body["customer"]["email"] = target.email
        if merchant_reference:
            body["merchant_reference"] = merchant_reference

        created = _unwrap(self._request("POST", "/payouts", body), "v1/payout", "payout")
        payout_id = created.get("id")
        if payout_id is None:
            raise GatewayError("FedaPay created a payout with no id")

        # Created but not sent. From here on the id EXISTS, so a failure to
        # start is recoverable by starting it again — which is why the caller
        # persists the reference before this second call rather than after.
        self.start_payout(str(payout_id))
        return self.read_payout(str(payout_id))

    def start_payout(self, reference: str) -> None:
        """Release a created payout. Batch endpoint, called with one element.

        Idempotent in the only sense we need: starting an already-started
        payout is not how money is sent twice — the amount lives on the payout
        row FedaPay created, and there is exactly one of those per reference.
        """
        self._request("PUT", "/payouts/start", {"payouts": [{"id": _as_int(reference)}]})

    def read_payout(self, reference: str) -> PayoutState:
        body = _unwrap(self._request("GET", f"/payouts/{reference}"), "v1/payout", "payout")
        raw_status = str(body.get("status", "")).lower()
        status = _PAYOUT_STATUS.get(raw_status)
        if status is None:
            logger.warning(
                "Unknown FedaPay payout status %r on %s; treating as pending", raw_status, reference
            )
            status = PAYOUT_PENDING
        return PayoutState(
            reference=str(body.get("id", reference)),
            status=status,
            amount=int(body.get("amount") or 0),
            currency=_currency_iso(body),
            raw_status=raw_status,
            failure_reason=body.get("last_error_code"),
            fee=_fee_amount(body),
        )

    # --------------------------------------------------------------- webhook

    def verify_webhook(self, raw_body: bytes, headers: dict) -> dict:
        import json

        header_value = None
        for key, value in headers.items():
            if key.lower() == signature.SIGNATURE_HEADER:
                header_value = value
                break
        signature.verify_signature(raw_body, header_value, self.webhook_secret)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise GatewayError("Webhook body is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise GatewayError("Webhook body is not a JSON object")
        return payload


def _currency_iso(body: dict) -> str:
    """XOF out of whichever shape the currency came back in.

    FedaPay takes {"iso": "XOF"} on the way in and has been seen to answer with
    a nested object, a bare string, or only a currency_id. Falling back to XOF
    is safe for this gateway specifically — it settles in nothing else — and
    the caller compares the answer against the escrow's own currency anyway.
    """
    currency = body.get("currency")
    if isinstance(currency, dict):
        return str(currency.get("iso") or "XOF")
    if isinstance(currency, str) and currency:
        return currency
    return "XOF"


def _fee_amount(body: dict) -> int | None:
    """What FedaPay charged us for this movement, or None if it did not say.

    `fees` is confirmed present on both the transaction resource and the payout
    resource, so one reader covers both legs. It is still read defensively: an
    absent key, a null, or a value that will not coerce all mean the same
    thing — the gateway did not tell us — and THAT IS A FACT WORTH STORING as
    None rather than guessing at. Zero is a different fact. Returning 0 for an
    absent key would quietly turn "we do not know what this cost" into "this
    cost nothing", which is the one error a fee column exists to prevent.

    WE DELIBERATELY DO NOT DERIVE THE FEE from `amount_transferred` or
    `amount_debited`, though both are sitting right there in the same body. The
    arithmetic runs in different directions on the two legs: a collection has
    the fee taken out of `amount` before what is left reaches our balance,
    while whether a payout's fee is deducted from the amount or charged on top
    of it is NOT YET CONFIRMED — nobody has watched a real sandbox payout
    settle and checked which it is. A derivation would bake that unverified
    assumption about money into every row it wrote. It is an open question, not
    a settled one, so we record what the gateway states and nothing else.
    """
    raw = body.get("fees")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _as_int(reference: str) -> int | str:
    try:
        return int(reference)
    except (TypeError, ValueError):
        return reference
