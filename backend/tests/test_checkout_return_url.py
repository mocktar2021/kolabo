"""What we are allowed to hand a gateway as a place to send the payer back to.

WHAT WAS WRONG. `start_checkout` did `return_url or settings.payment_return_url`
— the caller's value on trust. CheckoutScreen.tsx passes
`Linking.createURL("payment-return")`, so mobile sent `kolabo://payment-return`,
and FedaPay validates `callback_url` and refuses a custom scheme:

    400 {"errors":{"callback_url":["n'est pas une URL valide"]}}

which came back as a GatewayError, a 502, and a banner telling the payer the
payment service was unreachable. It was reachable. EVERY MOBILE PAYMENT EVER
ATTEMPTED failed this way, and nothing here tested what we send, so nothing
caught it. The web path always worked because the web app sends an https url.

These are the cases in one place: what passes through, what is replaced, and
the exact strings both clients actually produce.
"""
import pytest

from app.core.config import settings
from app.modules.payments.checkout import _gateway_return_url

CONFIGURED = settings.payment_return_url


@pytest.mark.parametrize(
    "url",
    [
        # What the web app sends. The whole point of the http(s) branch.
        "https://kolabo.mocktar.com/checkout/return",
        # A local dev front end, and the shipped default in config.py.
        "http://localhost:5173/checkout/return",
        # A path and a query survive: we hand this straight to the gateway and
        # append ?intent= ourselves, so nothing may be normalised away here.
        "https://kolabo.mocktar.com/checkout/return/deep/path",
    ],
)
def test_a_web_url_is_passed_through_untouched(url):
    """The web path must be BYTE-IDENTICAL, not merely accepted.

    This function sits on the money path for both clients, and a fix aimed at
    mobile that quietly rewrote the web return url would move a working
    payment flow for no reason.
    """
    assert _gateway_return_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        # THE ACTUAL VALUE THAT BROKE IT. Linking.createURL in a real build.
        "kolabo://payment-return",
        # ...and under Expo Go, which is what a dev handset sends.
        "exp://192.168.1.20:8081/--/payment-return",
        # Not produced by our clients, but this is a caller-supplied field and
        # the rule is a whitelist rather than a blacklist of one scheme.
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ftp://example.com/return",
    ],
)
def test_a_scheme_the_gateway_refuses_falls_back(url):
    assert _gateway_return_url(url) == CONFIGURED


@pytest.mark.parametrize("url", [None, "", "   ", "not a url at all", "/checkout/return"])
def test_nothing_usable_falls_back(url):
    """Absent, blank, or relative — all the same answer.

    A relative path is in here on purpose: it is the plausible "fix" somebody
    reaches for when they see this function, and it is still not something a
    gateway on someone else's servers can resolve.
    """
    assert _gateway_return_url(url) == CONFIGURED


@pytest.mark.parametrize("url", ["https://", "http://", "https:///checkout/return"])
def test_a_web_scheme_with_no_host_falls_back(url):
    """The scheme alone is not enough, which is why netloc is checked too.

    `urlsplit("https:///path")` parses with the right scheme and an EMPTY host,
    so a check on the scheme by itself would let a url through that resolves
    to nowhere — and the failure would land at the gateway, on a payment, in
    production, which is exactly where this class of bug was found the first
    time.
    """
    assert _gateway_return_url(url) == CONFIGURED


def test_the_configured_fallback_is_itself_a_url_the_gateway_accepts():
    """The fallback is only a fallback if it does not have the same problem.

    Guards the deployment as much as the code: PAYMENT_RETURN_URL is set in
    deploy/.env, and a typo there would put every payment back where it
    started with no test to notice.
    """
    assert _gateway_return_url(CONFIGURED) == CONFIGURED
