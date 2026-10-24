"""The FeexPay client in isolation. The payout leg, which is the money leg.

NO DATABASE AND NO APP. httpx.MockTransport answers every call, so these tests
assert on the exact bytes we would really send, which is the half that matters:
a payout down the wrong network does not bounce, it fails days later with money
in limbo.

WHICH SHAPES HERE ARE OBSERVED AND WHICH ARE NOT. test_fedapay_gateway.py
carries a warning earned the hard way, that a mock is only as good as the
observation behind it and a suite can be green for months against an API nobody
has watched. So, explicitly:

OBSERVED, against the FeexPay sandbox on 19 October 2026, one full collection
and payout in each of Benin (MTN), Togo (Moov TG) and Cote d'Ivoire (MTN CI):
the endpoint paths for those three, the required body fields, the 10 to
1,000,000 amount range, the 30 character motif cap, the uppercase SUCCESSFUL
and PENDING statuses, `responsecode` mirroring `status`, and three different
reference formats out of one session.

OBSERVED in production on 21 October: the payout status path answering 404 for
an unknown reference with a good key and 401 with a bad one.

NOT OBSERVED, and marked so in every test that touches them: SENEGAL ENTIRELY,
both its endpoint paths and its absent network field. Also Celtiis BJ, Togocom
TG, Moov CI, Wave CI, Orange CI, the failure vocabulary, the fee fields, and
the webhook. The tests below pin what was inferred rather than asserting it is
right, so that measuring any of it is a one line diff somebody can see.
"""
import httpx
import pytest

from app.modules.payments.gateways import feexpay as fx
from app.modules.payments.gateways.base import (
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_SENT,
    GatewayError,
    PayoutTarget,
)

SHOP = "EGCxXP0ydLLspx0"

# The three reference formats seen in ONE sandbox session. Kept together
# because the point is the variety, not any one of them: anything that parses
# a FeexPay reference is wrong.
OBSERVED_REFERENCES = (
    "d8a20ee0-d448-4f7e-8fd8-c91003c3e075",
    "F85E4478DFBA427F90BA",
    "dKxiXGaSMjOi",
)


class _Recorder:
    """Captures the one request we made, and answers with what we tell it."""

    def __init__(
        self,
        response: httpx.Response | None = None,
        http_status: int = 200,
        **json_body,
    ):
        # http_status, NOT status: the body FeexPay returns has its own
        # `status` field, and naming the HTTP code the same thing made every
        # _Recorder(status="SUCCESSFUL") in this file return HTTP "SUCCESSFUL"
        # instead. Twenty eight tests failed at once, which is the good
        # version of that mistake.
        self.requests: list[httpx.Request] = []
        self._response = response
        self._http_status = http_status
        self._json = json_body or {"reference": OBSERVED_REFERENCES[1], "status": "SUCCESSFUL"}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._response is not None:
            return self._response
        return httpx.Response(self._http_status, json=self._json)

    @property
    def path(self) -> str:
        return self.requests[-1].url.path

    @property
    def body(self) -> dict:
        import json

        return json.loads(self.requests[-1].content)


def _gateway(handler, *, shop: str = SHOP, **kwargs) -> fx.FeexPayGateway:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return fx.FeexPayGateway("secret-key", shop, client=client, **kwargs)


def _target(country: str, mode: str, phone: str = "22966000000") -> PayoutTarget:
    return PayoutTarget(phone=phone, country=country, mode=mode)


def _send(gateway, country, mode, *, amount=2000, description="Kolabo contract abcd1234", ref="p1"):
    return gateway.send_payout(
        amount=amount,
        currency="XOF",
        description=description,
        target=_target(country, mode),
        merchant_reference=ref,
    )


class TestThePayoutShapeIsDifferentInEveryCountry:
    """The headline risk. There is no convention here to lean on.

    Benin names the operator in a `network` field on a shared endpoint, Togo
    names it with a SPACE in its own endpoint, and Cote d'Ivoire has no
    `network` field at all because the path carries it. An adapter written from
    any one of these works in exactly one country.
    """

    @pytest.mark.parametrize(
        "country,mode,expected_path,expected_network",
        [
            # Benin. Observed: MTN end to end. MOOV is the same endpoint and
            # field with the other declared value.
            ("BJ", "MTN", "/api/payouts/public/transfer/global", "MTN"),
            ("BJ", "MOOV", "/api/payouts/public/transfer/global", "MOOV"),
            # Togo. The space is not a typo and it is the detail that breaks an
            # adapter written from the Benin shape.
            ("TG", "MOOV TG", "/api/payouts/public/togo", "MOOV TG"),
            ("TG", "TOGOCOM TG", "/api/payouts/public/togo", "TOGOCOM TG"),
            # Cote d'Ivoire. No network field anywhere.
            ("CI", "MTN_CI", "/api/payouts/public/mtn_ci", None),
            ("CI", "MOOV_CI", "/api/payouts/public/moov_ci", None),
            ("CI", "WAVE_CI", "/api/payouts/public/wave_ci", None),
            ("CI", "ORANGE_CI", "/api/payouts/public/orange_ci", None),
        ],
    )
    def test_each_network_goes_to_its_own_endpoint_with_its_own_naming(
        self, country, mode, expected_path, expected_network
    ):
        rec = _Recorder()
        _send(_gateway(rec), country, mode)
        assert rec.path == expected_path
        assert rec.body.get("network") == expected_network

    def test_a_path_carrying_the_operator_is_sent_no_network_field_at_all(self):
        """Absent, not None. A declared-field-set endpoint can reject a null."""
        rec = _Recorder()
        _send(_gateway(rec), "CI", "MTN_CI")
        assert "network" not in rec.body

    def test_every_body_carries_the_shop(self):
        """Required on every call. Without it everything 400s, in both legs."""
        rec = _Recorder()
        _send(_gateway(rec), "BJ", "MTN")
        assert rec.body["shop"] == SHOP

    def test_the_kolabo_payout_id_rides_along_as_callback_info(self):
        """The whole of reconciliation.

        It came back null on the sandbox status read, so nothing may depend on
        reading it back, but it means every movement at FeexPay carries our own
        Payout id. Without it, matching their statement to our rows is amounts
        and timestamps, which stops working the first time two creators are
        paid the same figure in the same minute.
        """
        rec = _Recorder()
        _send(_gateway(rec), "BJ", "MTN", ref="payout-row-7")
        assert rec.body["callback_info"] == "payout-row-7"


class TestSenegalIsInferred:
    """SN is in the adapter on a deliberate founder call, 24 October 2026.

    Senegal is already open in the UI, so leaving it out means a Senegalese
    creator with no payout path at all, which is worse than a route that might
    be named wrong. These tests PIN the inference rather than claim it is
    correct: when somebody POSTs to these paths and learns the truth, the diff
    is visible here.

    The operators come from the production dashboard, which shows Orange, Free
    and Wave activated. The paths and the absent network field follow the Cote
    d'Ivoire pattern.
    """

    @pytest.mark.parametrize(
        "mode,inferred_path",
        [
            ("ORANGE_SN", "/api/payouts/public/orange_sn"),
            ("FREE_SN", "/api/payouts/public/free_sn"),
            ("WAVE_SN", "/api/payouts/public/wave_sn"),
        ],
    )
    def test_the_inferred_senegal_routes_are_exactly_these(self, mode, inferred_path):
        rec = _Recorder()
        _send(_gateway(rec), "SN", mode)
        assert rec.path == inferred_path
        assert "network" not in rec.body

    def test_senegal_is_marked_unmeasured_so_a_first_failure_explains_itself(self, caplog):
        """A 404 on an inferred route must not read as a refused payout."""
        rec = _Recorder()
        with caplog.at_level("WARNING"):
            _send(_gateway(rec), "SN", "ORANGE_SN")
        assert "UNMEASURED" in caplog.text

    def test_a_measured_route_logs_no_such_warning(self, caplog):
        rec = _Recorder()
        with caplog.at_level("WARNING"):
            _send(_gateway(rec), "BJ", "MTN")
        assert "UNMEASURED" not in caplog.text


class TestTheAmountCeiling:
    """KOL-126, made visible. Nothing in the codebase knew about this.

    FeexPay moves 10 to 1,000,000 per movement, so in XOF a single payout
    cannot settle more than one million francs. That caps the largest contract
    Kolabo can complete, and before this adapter the limit existed only at the
    vendor.
    """

    def test_above_the_ceiling_is_refused_before_the_call(self):
        rec = _Recorder()
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(rec), "BJ", "MTN", amount=1_000_001)
        assert not rec.requests, "nothing should have been sent"
        assert "1000000" in str(caught.value).replace(",", "")

    def test_below_the_floor_is_refused_too(self):
        rec = _Recorder()
        with pytest.raises(GatewayError):
            _send(_gateway(rec), "BJ", "MTN", amount=9)
        assert not rec.requests

    def test_the_boundaries_themselves_are_allowed(self):
        """Inclusive at both ends, so an off-by-one here refuses real money."""
        for amount in (fx.MIN_AMOUNT, fx.MAX_AMOUNT):
            rec = _Recorder()
            _send(_gateway(rec), "BJ", "MTN", amount=amount)
            assert rec.body["amount"] == amount

    def test_the_refusal_is_not_retryable(self):
        """The number will not shrink on a second attempt, and the sweep
        retries up to payout_max_attempts. Five identical refusals is five
        pointless calls and a misleading attempt count on the Payout row."""
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(_Recorder()), "BJ", "MTN", amount=5_000_000)
        assert caught.value.retryable is False


class TestTheMotifCap:
    """30 characters, and the caller used to exceed it on every single payout.

    payouts._send passed "Kolabo payout for contract <8>", which is 35. Had
    this adapter passed it through, every payout in production would have 400'd
    on every network in every country.
    """

    def test_a_long_description_is_truncated_rather_than_refused(self):
        rec = _Recorder()
        _send(_gateway(rec), "BJ", "MTN", description="x" * 200)
        assert len(rec.body["motif"]) == fx.MOTIF_MAX_CHARS

    def test_the_shortened_call_site_description_fits_untouched(self):
        """The target shape for payouts._send, landing with the registry wiring.

        "Kolabo contract <8 chars>" is 24 characters, so the truncation above
        never fires and the contract prefix survives. The old sentence was 35
        and arrived as "...contract abc", throwing away most of the only
        human-readable identifier on the movement. Nothing routes payouts to
        FeexPay yet, so the 35 character version cannot reach it today; this
        pins the length the call site has to come down to before anything
        does.
        """
        description = f"Kolabo contract {'a' * 8}"
        assert len(description) <= fx.MOTIF_MAX_CHARS
        rec = _Recorder()
        _send(_gateway(rec), "BJ", "MTN", description=description)
        assert rec.body["motif"] == description


class TestStatusMapping:
    """An unknown word must never be read as success, and never as failure.

    Reading it as success pays nobody and marks them paid. Reading it as
    failure marks a creator unpaid on a string we have simply not seen before.
    Pending is the only honest answer and the sweep will ask again.
    """

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("SUCCESSFUL", PAYOUT_SENT),
            ("successful", PAYOUT_SENT),
            ("PENDING", PAYOUT_PENDING),
            # UNMEASURED: no payout has ever been made to fail on purpose, so
            # both plausible spellings are mapped.
            ("FAILED", PAYOUT_FAILED),
            ("FAILURE", PAYOUT_FAILED),
        ],
    )
    def test_known_statuses_map(self, raw, expected):
        rec = _Recorder(reference="r", status=raw)
        assert _send(_gateway(rec), "BJ", "MTN").status == expected

    def test_an_unknown_status_is_pending_and_logged(self, caplog):
        rec = _Recorder(reference="r", status="QUEUED_FOR_SETTLEMENT")
        with caplog.at_level("WARNING"):
            state = _send(_gateway(rec), "BJ", "MTN")
        assert state.status == PAYOUT_PENDING
        assert "QUEUED_FOR_SETTLEMENT" in caplog.text

    def test_a_missing_status_is_pending_not_success(self):
        rec = _Recorder(reference="r")
        assert _send(_gateway(rec), "BJ", "MTN").status == PAYOUT_PENDING

    def test_the_raw_status_is_kept_verbatim(self):
        """Stored on the Payout row. A normalised value loses the vendor's own
        word, which is the only thing support can quote back at them."""
        rec = _Recorder(reference="r", status="SUCCESSFUL")
        assert _send(_gateway(rec), "BJ", "MTN").raw_status == "SUCCESSFUL"


class TestResponsecodeIsNeverRead:
    """`responsecode` mirrors `status`: -1 while pending, SUCCESSFUL when done.

    A non-zero code that does not mean failure is exactly the field that gets
    misread, so these two tests exist to prove nothing branches on it.
    """

    def test_a_minus_one_responsecode_does_not_make_a_success_pending(self):
        rec = _Recorder(reference="r", status="SUCCESSFUL", responsecode="-1")
        assert _send(_gateway(rec), "BJ", "MTN").status == PAYOUT_SENT

    def test_a_successful_responsecode_does_not_rescue_a_failed_status(self):
        rec = _Recorder(reference="r", status="FAILED", responsecode="SUCCESSFUL")
        assert _send(_gateway(rec), "BJ", "MTN").status == PAYOUT_FAILED

    def test_responsecode_is_never_used_as_a_failure_reason(self):
        rec = _Recorder(reference="r", status="SUCCESSFUL", responsecode="-1")
        assert _send(_gateway(rec), "BJ", "MTN").failure_reason is None


class TestFeeIsNoneNotZero:
    """base.py is explicit: None means the gateway did not say, zero means it
    said this movement was free. Reading a missing fee as free understates our
    own cost silently, and further with every row.

    The fee on this provider has NEVER been measured. The balance before and
    after was not read in the sandbox session, so the margin model still rests
    on published rates: 1.7% in and 1% out for Benin, and 3% in and 2.4% out
    for Togo, which is 5.4 points of a 15% commission.
    """

    def test_an_unreported_fee_is_none(self):
        rec = _Recorder(reference="r", status="SUCCESSFUL")
        assert _send(_gateway(rec), "BJ", "MTN").fee is None

    def test_a_reported_zero_is_zero(self):
        rec = _Recorder(reference="r", status="SUCCESSFUL", fee=0)
        assert _send(_gateway(rec), "BJ", "MTN").fee == 0

    @pytest.mark.parametrize("key", ["fee", "fees", "frais", "commission"])
    def test_a_fee_is_read_from_any_of_the_plausible_keys(self, key):
        """UNMEASURED. Which key FeexPay actually uses is unknown, so several
        are read. None of them defaults to a number."""
        rec = _Recorder(**{"reference": "r", "status": "SUCCESSFUL", key: 17})
        assert _send(_gateway(rec), "BJ", "MTN").fee == 17

    def test_an_unparseable_fee_is_none_and_logged(self, caplog):
        rec = _Recorder(reference="r", status="SUCCESSFUL", fee="gratuit")
        with caplog.at_level("WARNING"):
            state = _send(_gateway(rec), "BJ", "MTN")
        assert state.fee is None
        assert "gratuit" in caplog.text


class TestReferences:
    """Opaque strings, and there is no single key or format."""

    @pytest.mark.parametrize("reference", OBSERVED_REFERENCES)
    def test_every_observed_format_survives_unchanged(self, reference):
        rec = _Recorder(reference=reference, status="SUCCESSFUL")
        assert _send(_gateway(rec), "BJ", "MTN").reference == reference

    @pytest.mark.parametrize("key", ["reference", "transaction_id", "transactionId", "id", "ref"])
    def test_the_reference_is_found_under_any_of_the_keys_seen(self, key):
        rec = _Recorder(**{key: "abc123", "status": "SUCCESSFUL"})
        assert _send(_gateway(rec), "BJ", "MTN").reference == "abc123"

    def test_an_accepted_payout_with_no_reference_raises_loudly(self):
        """The one state no sweep can clean up.

        The money may well have moved, and with no reference there is nothing
        to re-read, so this must never be swallowed into a pending row that
        looks recoverable.
        """
        rec = _Recorder(status="SUCCESSFUL")
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(rec), "BJ", "MTN")
        assert "no reference" in str(caught.value)


class TestUnknownRoutes:
    def test_an_unsupported_country_is_refused_without_a_call(self):
        rec = _Recorder()
        with pytest.raises(GatewayError, match="no payout route"):
            _send(_gateway(rec), "GH", "MTN")
        assert not rec.requests

    def test_a_mode_that_is_not_in_the_country_names_the_ones_that_are(self):
        """The creator chose this from a closed set, so a mismatch is a bug on
        our side and the message should be enough to find it."""
        rec = _Recorder()
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(rec), "BJ", "MTN_CI")
        assert not rec.requests
        assert "MTN" in str(caught.value) and "CELTIIS_BJ" in str(caught.value)

    def test_a_currency_outside_the_licence_is_refused(self):
        rec = _Recorder()
        with pytest.raises(GatewayError, match="licence"):
            _gateway(rec).send_payout(
                amount=2000,
                currency="GHS",
                description="d",
                target=_target("BJ", "MTN"),
            )
        assert not rec.requests


class TestCapability:
    def test_the_four_open_markets_are_the_supported_ones(self):
        """Deliberately the same four as core/country_config.py. The market
        list IS the payment list: a country where money cannot move is a signup
        that ends at a payout form which cannot pay."""
        assert fx.SUPPORTED_COUNTRIES == ("BJ", "TG", "CI", "SN")

    @pytest.mark.parametrize("country", ["BJ", "TG", "CI", "SN"])
    def test_xof_is_supported_in_every_open_market(self, country):
        assert _gateway(_Recorder()).supports(country, "XOF")

    @pytest.mark.parametrize(
        "country,currency", [("GH", "GHS"), ("CM", "XAF"), ("NG", "NGN"), ("BJ", "GHS")]
    )
    def test_nothing_outside_the_bceao_licence_is_supported(self, country, currency):
        assert not _gateway(_Recorder()).supports(country, currency)

    def test_payout_modes_is_the_closed_set_a_creator_is_validated_against(self):
        gateway = _gateway(_Recorder())
        assert gateway.payout_modes("BJ") == ("MTN", "MOOV", "CELTIIS_BJ")
        assert gateway.payout_modes("TG") == ("MOOV TG", "TOGOCOM TG")
        assert gateway.payout_modes("SN") == ("ORANGE_SN", "FREE_SN", "WAVE_SN")

    def test_an_unserved_country_offers_no_modes_rather_than_raising(self):
        """The payout form asks for every country; a refusal belongs at save
        time with a sentence, not here."""
        assert _gateway(_Recorder()).payout_modes("GH") == ()

    def test_every_mode_in_every_country_has_a_route(self):
        """payout_modes is derived from the route table, so this cannot drift,
        and that is the point: a mode offered with no route is a creator who
        can save a payout method that can never be used."""
        gateway = _gateway(_Recorder())
        for country in fx.SUPPORTED_COUNTRIES:
            modes = gateway.payout_modes(country)
            assert modes, f"{country} is supported but offers no payout network"
            for mode in modes:
                assert fx._PAYOUT_ROUTES[country][mode].path.startswith("/api/payouts/")


class TestHttpFailures:
    def test_a_timeout_is_retryable_because_we_do_not_know_what_happened(self):
        """And retryable here means RE-READ, not re-send: FeexPay offers no
        idempotency key, so a blind retry is how somebody gets paid twice."""

        def handler(request):
            raise httpx.TimeoutException("too slow", request=request)

        with pytest.raises(GatewayError) as caught:
            _send(_gateway(handler), "BJ", "MTN")
        assert caught.value.retryable is True

    def test_a_401_explains_the_ip_allowlist_before_anybody_rotates_a_key(self):
        """The payout API is gated on an IP allowlist scoped PER BOUTIQUE, so a
        correct key from an unregistered address fails exactly like a bad one.
        A payout that starts failing after a server move is this, every time.
        """
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(_Recorder(http_status=401, message="unauthorized")), "BJ", "MTN")
        message = str(caught.value)
        assert "IP list" in message and "per boutique" in message
        assert caught.value.retryable is False

    def test_a_500_is_retryable(self):
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(_Recorder(http_status=503)), "BJ", "MTN")
        assert caught.value.retryable is True

    def test_a_400_is_not_retryable_and_carries_their_wording(self):
        """Their validation errors name the offending field. Losing that turns
        a two minute fix into an afternoon."""
        rec = _Recorder(http_status=400, message="motif must be shorter than 30 characters")
        with pytest.raises(GatewayError) as caught:
            _send(_gateway(rec), "BJ", "MTN")
        assert caught.value.retryable is False
        assert "motif must be shorter" in str(caught.value)

    def test_a_non_json_body_is_a_retryable_fault_not_a_parse_crash(self):
        handler = _Recorder(response=httpx.Response(200, text="<html>502</html>"))
        with pytest.raises(GatewayError, match="not JSON"):
            _send(_gateway(handler), "BJ", "MTN")

    def test_a_json_array_is_rejected_rather_than_treated_as_a_mapping(self):
        handler = _Recorder(response=httpx.Response(200, json=[1, 2]))
        with pytest.raises(GatewayError, match="not an object"):
            _send(_gateway(handler), "BJ", "MTN")


class TestReadPayout:
    def test_it_reads_the_status_path(self):
        rec = _Recorder(reference="dKxiXGaSMjOi", status="SUCCESSFUL", amount=2000)
        state = _gateway(rec).read_payout("dKxiXGaSMjOi")
        assert rec.path == "/api/payouts/status/public/dKxiXGaSMjOi"
        assert state.status == PAYOUT_SENT
        assert state.amount == 2000

    def test_a_status_read_with_no_amount_does_not_echo_a_hopeful_figure(self):
        """The create call may fall back to what we asked for. A status read
        must not: a zero somebody investigates beats a number we invented."""
        rec = _Recorder(reference="r", status="PENDING")
        assert _gateway(rec).read_payout("r").amount == 0


class TestTheLegsThatAreNotWiredRefuse:
    """Collections and the webhook raise rather than half working.

    Both are deliberate and both are documented in the module. Collections
    because FeexPay's proven endpoint pushes a prompt to a handset and returns
    no checkout URL, which the funding flow requires. The webhook because its
    signature scheme has never been observed, and guessing one either rejects
    every real callback or accepts forged ones.
    """

    def test_start_collection_refuses_rather_than_returning_a_blank_url(self):
        """A CollectionStart with an empty checkout_url would be stored, reused
        by checkout.py's duplicate-funding guard, and sent to a brand as a link
        to nowhere."""
        with pytest.raises(GatewayError, match="not wired up"):
            _gateway(_Recorder()).start_collection(
                amount=2000,
                currency="XOF",
                description="d",
                callback_url="https://example.test/return",
                payer_country="BJ",
                payer_first_name="A",
                payer_last_name="B",
            )

    def test_read_collection_refuses(self):
        with pytest.raises(GatewayError, match="not wired up"):
            _gateway(_Recorder()).read_collection("ref")

    def test_verify_webhook_refuses_instead_of_guessing_a_scheme(self):
        with pytest.raises(GatewayError) as caught:
            _gateway(_Recorder()).verify_webhook(b"{}", {"x-feexpay-signature": "whatever"})
        assert "not been observed" in str(caught.value)

    def test_it_refuses_even_with_a_webhook_secret_configured(self):
        """A configured secret must not be mistaken for a verified scheme."""
        gateway = _gateway(_Recorder(), webhook_secret="wh_something")
        with pytest.raises(GatewayError):
            gateway.verify_webhook(b"{}", {})


class TestEnvironment:
    def test_sandbox_and_live_are_different_hosts(self):
        assert fx.SANDBOX_BASE_URL != fx.LIVE_BASE_URL
        assert fx.LIVE_BASE_URL == "https://api-v2.feexpay.me"

    def test_sandbox_is_the_default(self):
        """A deployment handed live keys without being told to use them stays
        in the test environment instead of moving real money. Same rule
        FEDAPAY_SANDBOX follows."""
        assert fx.FeexPayGateway("k", SHOP).base_url == fx.SANDBOX_BASE_URL

    def test_going_live_is_explicit(self):
        assert fx.FeexPayGateway("k", SHOP, sandbox=False).base_url == fx.LIVE_BASE_URL

    def test_the_bearer_token_is_sent(self):
        rec = _Recorder()
        _send(_gateway(rec), "BJ", "MTN")
        assert rec.requests[-1].headers["authorization"] == "Bearer secret-key"
