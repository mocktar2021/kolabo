"""Request and response shapes for the gateway endpoints.

Separate from payments/schemas.py for the same reason gateway_models.py is
separate from models.py: that file describes the platform's own money — escrow,
disputes, statements — and this one describes the conversation with an outside
system. They change for different reasons and on different schedules.
"""
from pydantic import BaseModel, Field


class CheckoutStartIn(BaseModel):
    contract_id: str
    # Optional, and optional on purpose. FedaPay wants a first and last name on
    # the customer object; the platform stores a company profile, not a
    # person's legal name, and inventing one from the company name would put a
    # wrong name on a real payment receipt. So the client may pass what the
    # payer types on the checkout screen, and we fall back to a neutral
    # placeholder rather than to something that looks like data.
    payer_first_name: str | None = None
    payer_last_name: str | None = None
    # Where the gateway sends the payer afterwards. Mobile passes its own
    # kolabo:// deep link; web leaves it unset and gets the configured default.
    return_url: str | None = None


class PaymentIntentOut(BaseModel):
    id: str
    contract_id: str
    amount: int
    currency: str
    status: str
    provider: str
    # Null once the payment is terminal — a used-up checkout url is worse than
    # no url, because it takes a payer to an expired page instead of telling
    # them the payment is already done.
    checkout_url: str | None = None
    # Set only when the payment succeeded AND the escrow was created. The
    # client watches for this rather than for status alone: "succeeded" without
    # an escrow id is the amount-mismatch case, which needs a human.
    escrow_id: str | None = None
    failure_reason: str | None = None


class PaymentConfigOut(BaseModel):
    enabled: bool
    public_key: str = ""
    sandbox: bool = True
    countries: list[str] = Field(default_factory=list)
    # May this client fall back to the in-process mock funding path?
    #
    # True ONLY when no gateway is configured AND this is not production. It
    # exists because repointing the fund button at the hosted checkout broke
    # every keyless stack — a developer with no FedaPay account could no longer
    # fund an escrow at all, so the whole delivery-and-release flow became
    # untestable locally.
    #
    # The environment check is the part that matters. Without it, a production
    # deploy that forgot its keys would quietly mock-fund real escrows against
    # money nobody collected, which is precisely what the direct path was
    # disabled to prevent. In production this stays false and funding refuses,
    # loudly, as it should.
    mock_payments: bool = False


class PayoutMethodIn(BaseModel):
    country: str
    mode: str
    phone: str
    account_name: str | None = None


class PayoutMethodOut(BaseModel):
    country: str
    mode: str
    # MASKED, always. The full number goes to the gateway and never into a
    # response body: it is the one field on that row worth stealing, and a
    # creator confirming "yes, that is my wallet" only needs the last four
    # digits to be sure.
    phone_masked: str
    account_name: str | None = None
