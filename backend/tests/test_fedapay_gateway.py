"""The gateway layer in isolation: signatures, HTTP, and status mapping.

NO DATABASE AND NO APP HERE. These are the two pieces that are pure enough to
test as functions — the webhook signature and the FedaPay HTTP client — and
they are also the two pieces where a bug is worst: a signature check that
passes when it should fail accepts forged payment confirmations, and a status
mapping that reads "declined" as success funds an escrow nobody paid for.

Every FedaPay response body below is shaped from their published examples. The
client never touches the network: httpx.MockTransport answers, which means the
tests assert on the exact request we would really send.

AND WHERE THE EXAMPLES RAN OUT, THIS FILE ONCE GUESSED — which is worth
recording, because the guess passed for months. FedaPay does not document the
raw response of POST /transactions/{id}/token, so the mock returned
{"v1/token": {...}}, matching the envelope the transaction and payout
endpoints use. The real endpoint answers FLAT: {"token": ..., "url": ...}.
The suite was green against an API nobody had observed, and every checkout
against the real sandbox failed on the first attempt. A mock is only as good
as the observation behind it; where a shape is asserted here and not published
by the vendor, say so in the test.
"""
import json
import time

import httpx
import pytest

from app.modules.payments.gateways import fedapay as fp
from app.modules.payments.gateways import signature as sig
from app.modules.payments.gateways.base import (
    CANCELED,
    FAILED,
    PAYOUT_PENDING,
    PAYOUT_SENT,
    PENDING,
    SUCCEEDED,
    GatewayError,
    PayoutTarget,
)

SECRET = "wh_sandbox_testsecret"

# The token endpoint's real answer, observed against the FedaPay sandbox on
# 27 August 2026. Flat — no resource envelope. Kept as a module constant so
# the next person can see at a glance which shapes here are observed and which
# are inferred from the docs.
TOKEN_RESPONSE = {"token": "tok", "url": "https://process.fedapay.com/tok"}


def _sign(body: bytes, secret: str = SECRET, timestamp: int | None = None) -> str:
    import hashlib
    import hmac

    ts = timestamp if timestamp is not None else int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},s={mac}"


# --------------------------------------------------------------- signatures


def test_valid_signature_passes():
    body = b'{"name":"transaction.approved"}'
    sig.verify_signature(body, _sign(body), SECRET)


def test_signature_over_the_wrong_body_fails():
    """The signature covers the bytes, so changing one changes the answer.

    This is the test that would catch the classic implementation bug: parsing
    the JSON, re-serialising it, and hashing that. Key order and whitespace
    differ, so the recomputed mac differs, and the only way to make it "work"
    is to stop verifying.
    """
    body = b'{"name":"transaction.approved","amount":50000}'
    tampered = b'{"name":"transaction.approved","amount":500}'
    with pytest.raises(GatewayError):
        sig.verify_signature(tampered, _sign(body), SECRET)


def test_wrong_secret_fails():
    body = b"{}"
    with pytest.raises(GatewayError):
        sig.verify_signature(body, _sign(body, secret="wh_other"), SECRET)


def test_stale_timestamp_fails():
    """Replay protection. A captured signature stops working after 5 minutes.

    Without this a valid signature is a permanent credential, and replaying an
    `approved` event is exactly the input the funding path is waiting for.
    """
    body = b"{}"
    old = int(time.time()) - 3600
    with pytest.raises(GatewayError):
        sig.verify_signature(body, _sign(body, timestamp=old), SECRET)


def test_future_timestamp_outside_tolerance_fails():
    body = b"{}"
    ahead = int(time.time()) + 3600
    with pytest.raises(GatewayError):
        sig.verify_signature(body, _sign(body, timestamp=ahead), SECRET)


def test_missing_header_fails():
    with pytest.raises(GatewayError):
        sig.verify_signature(b"{}", None, SECRET)


@pytest.mark.parametrize("header", ["", "garbage", "t=abc,s=def", "s=onlysig", "t=123"])
def test_malformed_headers_fail(header):
    with pytest.raises(GatewayError):
        sig.verify_signature(b"{}", header, SECRET)


def test_unset_secret_refuses_rather_than_skipping():
    """An unconfigured secret must REFUSE, never wave the request through.

    The alternative — skip verification when no secret is set — means a
    deployment that forgot the variable accepts anything anyone posts, and the
    failure is invisible precisely because everything appears to work.
    """
    body = b"{}"
    with pytest.raises(GatewayError):
        sig.verify_signature(body, _sign(body), "")


def test_multiple_signatures_accepted_for_rotation():
    """Two `s=` values, one of them ours. Secret rotation must not be an outage."""
    body = b"{}"
    ts = int(time.time())
    good = _sign(body, timestamp=ts).split("s=")[1]
    header = f"t={ts},s=deadbeef,s={good}"
    sig.verify_signature(body, header, SECRET)


# ------------------------------------------------------------------- client


def _gateway(handler) -> fp.FedaPayGateway:
    transport = httpx.MockTransport(handler)
    return fp.FedaPayGateway(
        secret_key="sk_test",
        webhook_secret=SECRET,
        sandbox=True,
        client=httpx.Client(transport=transport),
    )


def _collection_handler(token_response, seen=None):
    """A two-call collection: create the transaction, then fetch its token."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transactions"):
            if seen is not None:
                seen["create"] = json.loads(request.content)
                seen["auth"] = request.headers["authorization"]
            return httpx.Response(201, json={"v1/transaction": {"id": 4242, "status": "pending"}})
        if request.url.path.endswith("/transactions/4242/token"):
            return httpx.Response(200, json=token_response)
        raise AssertionError(f"unexpected {request.url}")

    return handler


def _start(gateway):
    return gateway.start_collection(
        amount=50000,
        currency="XOF",
        description="Kolabo contract abcd1234",
        callback_url="https://kolabo.app/checkout/return?intent=i1",
        payer_phone="+22997000000",
        payer_country="BJ",
        payer_first_name="Ada",
        payer_last_name="Lovelace",
        payer_email="ada@example.com",
        merchant_reference="i1",
    )


def test_start_collection_sends_the_right_body_and_returns_a_url():
    """The happy path, against the token shape FedaPay really sends.

    TOKEN_RESPONSE is flat. This assertion used to run against a wrapped
    {"v1/token": {...}} body that FedaPay does not produce, which is why the
    suite stayed green while every real checkout raised "Could not find a
    resource in the response (keys: ['token', 'url'])".
    """
    seen = {}
    started = _start(_gateway(_collection_handler(TOKEN_RESPONSE, seen)))

    assert started.reference == "4242"
    assert started.checkout_url == "https://process.fedapay.com/tok"
    assert started.expires_in_seconds == 24 * 3600
    assert seen["auth"] == "Bearer sk_test"
    body = seen["create"]
    # XOF has no minor unit and FedaPay takes whole numbers, so the integer we
    # hold must go over the wire UNSCALED. A stray *100 here would charge every
    # brand a hundred times the contract.
    assert body["amount"] == 50000
    # A nested object, not a bare string — FedaPay answers "XOF" with a
    # validation error that does not explain itself.
    assert body["currency"] == {"iso": "XOF"}
    assert body["customer"]["phone_number"] == {"number": "+22997000000", "country": "bj"}
    assert body["merchant_reference"] == "i1"


def test_wrapped_token_response_is_still_accepted():
    """Tolerated, not expected.

    The envelope is not a documented contract on any FedaPay endpoint and their
    own SDKs differ on whether they see it, so a wrapped token body must not
    break a checkout if it ever appears. This is the shape the suite used to
    assert as the only one; it is kept as the variant it always was.
    """
    handler = _collection_handler({"v1/token": {"token": "tok", "url": "https://pay/x"}})
    assert _start(_gateway(handler)).checkout_url == "https://pay/x"


@pytest.mark.parametrize(
    "token_response",
    [
        {"token": "tok"},          # flat, but no url
        {"v1/token": {"token": "tok"}},   # wrapped, but no url
        {},
        {"url": ""},
    ],
)
def test_token_response_without_a_url_is_refused(token_response):
    """No url means no checkout, and the failure has to say THAT.

    The transaction already exists at FedaPay when this raises, so the message
    names it — an orphan transaction with no local checkout url is the state a
    human has to reconcile, and the id is the only handle they have on it.
    """
    with pytest.raises(GatewayError) as exc:
        _start(_gateway(_collection_handler(token_response)))
    assert "checkout url" in str(exc.value)
    assert "4242" in str(exc.value)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("pending", PENDING),
        ("approved", SUCCEEDED),
        ("transferred", SUCCEEDED),
        ("declined", FAILED),
        ("canceled", CANCELED),
        ("refunded", FAILED),
    ],
)
def test_collection_status_mapping(raw, expected):
    def handler(request):
        return httpx.Response(
            200,
            json={"v1/transaction": {"id": 1, "status": raw, "amount": 1000, "currency": {"iso": "XOF"}}},
        )

    assert _gateway(handler).read_collection("1").status == expected


def test_unknown_collection_status_is_pending_not_success():
    """An unrecognised status must never be read as money having arrived.

    Failing would be just as wrong — it would resolve an escrow on a word we
    have simply not seen before — so the safe answer is "we do not know yet",
    which leaves the intent open for the next read.
    """
    def handler(request):
        return httpx.Response(
            200, json={"v1/transaction": {"id": 1, "status": "quantum", "amount": 1000}}
        )

    assert _gateway(handler).read_collection("1").status == PENDING


def test_bare_body_without_envelope_is_understood():
    """FedaPay's envelope is not a documented contract, so we accept both shapes."""
    def handler(request):
        return httpx.Response(200, json={"id": 7, "status": "approved", "amount": 25000})

    state = _gateway(handler).read_collection("7")
    assert state.status == SUCCEEDED and state.amount == 25000


def test_send_payout_creates_then_starts_then_reads():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/payouts"):
            assert json.loads(request.content)["mode"] == "mtn_open"
            return httpx.Response(201, json={"v1/payout": {"id": 99, "status": "pending"}})
        if request.method == "PUT" and request.url.path.endswith("/payouts/start"):
            # The batch endpoint, called with exactly one element, and the id
            # as an integer rather than the string we carry internally.
            assert json.loads(request.content) == {"payouts": [{"id": 99}]}
            return httpx.Response(200, json={})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"v1/payout": {"id": 99, "status": "sent", "amount": 42500, "currency": {"iso": "XOF"}}},
            )
        raise AssertionError(f"unexpected {request.method} {request.url}")

    state = _gateway(handler).send_payout(
        amount=42500,
        currency="XOF",
        description="Kolabo payout",
        target=PayoutTarget(phone="97000000", country="BJ", mode="mtn_open"),
        merchant_reference="p1",
    )

    assert state.status == PAYOUT_SENT
    assert [c[0] for c in calls] == ["POST", "PUT", "GET"]


def test_payout_processing_is_pending_not_sent():
    """`processing` means in flight. Calling it sent would mark money as landed."""
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201, json={"v1/payout": {"id": 5, "status": "pending"}})
        if request.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"v1/payout": {"id": 5, "status": "processing", "amount": 1}})

    state = _gateway(handler).send_payout(
        amount=1,
        currency="XOF",
        description="d",
        target=PayoutTarget(phone="97000000", country="BJ", mode="mtn_open"),
    )
    assert state.status == PAYOUT_PENDING


def test_4xx_is_not_retryable_and_5xx_is():
    """The distinction the payout sweep runs on.

    A 400 saying the phone number is malformed will say the same thing forever;
    a 503 is worth trying again. Retrying the first is a loop that bills us per
    attempt and never succeeds.
    """
    def bad_request(request):
        return httpx.Response(400, text='{"message":"phone_number is invalid"}')

    def server_error(request):
        return httpx.Response(503, text="upstream down")

    with pytest.raises(GatewayError) as four:
        _gateway(bad_request).read_collection("1")
    assert four.value.retryable is False
    # The provider's own words are carried through: their validation errors
    # name the field, and losing that turns a two-minute fix into an afternoon.
    assert "phone_number" in str(four.value)

    with pytest.raises(GatewayError) as five:
        _gateway(server_error).read_collection("1")
    assert five.value.retryable is True


def test_timeout_is_retryable():
    def handler(request):
        raise httpx.TimeoutException("too slow", request=request)

    with pytest.raises(GatewayError) as exc:
        _gateway(handler).read_collection("1")
    assert exc.value.retryable is True


def test_supports_only_the_uemoa_three():
    """Ghana and Cameroon are NOT covered, and the code has to say so.

    Both are on the five-country pilot list and neither is a FedaPay market in
    any currency. The registry turns this False into a refusal a brand can
    read; see gateways/registry.py. If this test ever starts passing for GH or
    CM, it is because somebody added a second gateway — and this assertion
    should move, not be deleted.
    """
    gateway = fp.FedaPayGateway(secret_key="sk")
    assert gateway.supports("BJ", "XOF")
    assert gateway.supports("TG", "XOF")
    assert gateway.supports("CI", "XOF")
    assert not gateway.supports("GH", "GHS")
    assert not gateway.supports("CM", "XAF")
    assert not gateway.supports("NG", "NGN")
    # Right country, wrong currency: FedaPay settles in XOF only.
    assert not gateway.supports("BJ", "GHS")


def test_verify_webhook_returns_the_payload():
    gateway = fp.FedaPayGateway(secret_key="sk", webhook_secret=SECRET)
    body = b'{"name":"transaction.approved","entity":{"id":1}}'
    payload = gateway.verify_webhook(body, {"X-FEDAPAY-SIGNATURE": _sign(body)})
    assert payload["name"] == "transaction.approved"


def test_verify_webhook_rejects_a_forgery():
    gateway = fp.FedaPayGateway(secret_key="sk", webhook_secret=SECRET)
    body = b'{"name":"transaction.approved"}'
    with pytest.raises(GatewayError):
        gateway.verify_webhook(body, {"X-FEDAPAY-SIGNATURE": "t=1,s=deadbeef"})
