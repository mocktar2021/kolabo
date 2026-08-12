"""Payment gateways: the layer that actually moves money.

WHY THIS IS A PACKAGE AND NOT A FILE. payments/provider.py already had the
right idea — one interface, a mock behind it, escrow logic that never names a
vendor. What it did not have was room for the shape a real gateway turns out
to have: a collection is asynchronous (a redirect, then a webhook, then a
server-to-server re-read), a payout is a two-step create-then-start with its
own state machine, and which gateway answers at all depends on the country.
Three concerns, three modules, one registry in front of them.

    base.py       the contracts — result types and the Protocol
    signature.py  webhook signature verification, framework-free and unit-testable
    fedapay.py    the FedaPay HTTP client (BJ, TG, CI)
    registry.py   country -> gateway, and the refusal when nothing answers

provider.py is left exactly as it was. It is the synchronous seam the existing
suite swaps a MockProvider into, and nothing here changes that: a test that
reassigns payments.service.payment_provider still works, still moves no money,
and still never reaches this package.
"""
