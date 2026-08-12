"""FedaPay webhook signature verification.

There is no official FedaPay Python SDK, so this is a direct port of the
scheme their PHP and Node SDKs implement (fedapay-php lib/WebhookSignature.php).
It is Stripe-shaped but NOT Stripe: the scheme key is `s`, not `v1`, and the
secret is prefixed `wh_`, not `whsec_`. Reaching for the stripe package here
would fail in a way that looks like a bad secret.

    header:  X-FEDAPAY-SIGNATURE: t=1699999999,s=<hex>
    signed:  "<t>.<raw request body>"
    mac:     HMAC-SHA256, hex digest
    window:  300 seconds

WHY THE TIMESTAMP WINDOW IS NOT OPTIONAL. Without it a valid signature is
valid forever, so anyone who ever captures one request — a proxy log, a
mis-shared debugging paste, a compromised intermediary — can replay it at will.
Against a payments webhook that is not an abstract risk: replaying an
`approved` event is the exact input the funding path is looking for. The window
turns a permanent credential into a five minute one, and the idempotency key on
the event row (payments/models.GatewayEvent) closes what is left.
"""
import hashlib
import hmac
import time

from app.modules.payments.gateways.base import GatewayError

SIGNATURE_HEADER = "x-fedapay-signature"
EXPECTED_SCHEME = "s"
DEFAULT_TOLERANCE_SECONDS = 300


def _parse_header(header: str) -> tuple[int, list[str]]:
    """Pull the timestamp and every offered signature out of the header.

    EVERY signature, plural, not the first one: signature headers in this
    family are built to carry more than one during a secret rotation, so a
    deployment that has been given a new secret but is still receiving events
    signed with the old one keeps working. Taking only the first would make
    rotation an outage.
    """
    timestamp = -1
    signatures: list[str] = []
    for part in header.split(","):
        pair = part.strip().split("=", 1)
        if len(pair) != 2:
            continue
        key, value = pair[0].strip(), pair[1].strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                timestamp = -1
        elif key == EXPECTED_SCHEME:
            signatures.append(value)
    return timestamp, signatures


def verify_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> None:
    """Raise GatewayError unless this body was signed with this secret, recently.

    Returns None on success. Deliberately returns nothing at all: a function
    that returns a boolean invites `if verify(...)` to be written without the
    `if`, and the failure mode of that mistake is accepting every forged
    webhook silently. A raise cannot be ignored by omission.
    """
    if not secret:
        # Refusing is the only safe reading of an unset secret. Skipping
        # verification when the secret is missing would mean a deployment that
        # forgot to configure it accepts anything anyone sends — the failure
        # would be invisible precisely because everything appears to work.
        raise GatewayError("Webhook secret is not configured", retryable=False)
    if not signature_header:
        raise GatewayError("Missing webhook signature header", retryable=False)

    timestamp, signatures = _parse_header(signature_header)
    if timestamp < 0 or not signatures:
        raise GatewayError("Malformed webhook signature header", retryable=False)

    current = time.time() if now is None else now
    if tolerance and abs(current - timestamp) > tolerance:
        raise GatewayError(
            f"Webhook timestamp outside the {tolerance}s tolerance", retryable=False
        )

    signed_payload = str(timestamp).encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    # compare_digest on every candidate, and no early return on the first
    # mismatch — the comparison has to be constant time or the response time
    # leaks how many leading characters of a guessed signature were right,
    # which is enough to forge one byte at a time.
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise GatewayError("Webhook signature does not match", retryable=False)
