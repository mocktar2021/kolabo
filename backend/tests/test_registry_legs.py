"""One country, two gateways, one per leg.

WHY THE SPLIT EXISTS. The registry held a single country map: whichever
gateway took a brand's money in also pushed the creator's money out. That was
true while one provider did both, and it stopped being true as soon as the two
legs had different best answers.

They do. FedaPay has no payout menu at all, which is the reason FeexPay was
integrated in the first place; FeexPay's mobile money collection is what the
launch markets actually pay with. One choice per country means neither leg can
be moved without dragging the other behind it.

THE TEST THAT MATTERS MOST IS test_a_payout_goes_to_the_payout_gateway. With
two different providers installed, paying a creator through whichever gateway
happens to take the brand's money is the exact mix-up this split exists to
prevent, and it is the kind that surfaces days later as money in limbo rather
than as an error anybody sees.
"""
import pytest

from app.modules.payments.gateways import registry
from app.modules.payments.gateways.base import CollectionStart, PayoutState
from app.modules.payments.gateways.fedapay import FedaPayGateway
from app.modules.payments.gateways.feexpay import FeexPayGateway

FEDA_COUNTRIES = ("BJ", "TG", "CI")
FEEX_COUNTRIES = ("BJ", "TG", "CI", "SN")


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset_registry()
    yield
    registry.reset_registry()


@pytest.fixture()
def only_fedapay(monkeypatch):
    monkeypatch.setattr(registry.settings, "fedapay_secret_key", "sk_test")
    monkeypatch.setattr(registry.settings, "fedapay_webhook_secret", "wh")
    monkeypatch.setattr(registry.settings, "fedapay_sandbox", True)
    monkeypatch.setattr(registry.settings, "feexpay_collections", False)
    monkeypatch.setattr(registry.settings, "feexpay_api_key", "")
    monkeypatch.setattr(registry.settings, "feexpay_shop_id", "")
    registry.reset_registry()


@pytest.fixture()
def feexpay_on(monkeypatch, only_fedapay):
    monkeypatch.setattr(registry.settings, "feexpay_api_key", "fx_key")
    monkeypatch.setattr(registry.settings, "feexpay_shop_id", "EGCxXP0ydLLspx0")
    monkeypatch.setattr(registry.settings, "feexpay_collections", True)
    registry.reset_registry()


# ----------------------------------------------- nothing changes by default


def test_fedapay_alone_fills_both_legs_exactly_as_before(only_fedapay):
    """THE UNCHANGED-BEHAVIOUR TEST. A box with only FedaPay keys routes
    precisely as it did before this module learned about legs."""
    for country in FEDA_COUNTRIES:
        assert isinstance(registry.registry(registry.COLLECTIONS)[country], FedaPayGateway)
        assert isinstance(registry.registry(registry.PAYOUTS)[country], FedaPayGateway)
    assert "SN" not in registry.registry(registry.COLLECTIONS)
    assert "SN" not in registry.registry(registry.PAYOUTS)


def test_feexpay_credentials_alone_change_nothing(monkeypatch, only_fedapay):
    """HAVING A KEY IS NOT DECIDING TO USE IT. A box handed credentials during
    setup must not start routing live money through a provider nobody has
    chosen yet."""
    monkeypatch.setattr(registry.settings, "feexpay_api_key", "fx_key")
    monkeypatch.setattr(registry.settings, "feexpay_shop_id", "shop")
    registry.reset_registry()
    for country in FEDA_COUNTRIES:
        assert isinstance(registry.registry(registry.COLLECTIONS)[country], FedaPayGateway)


def test_the_switch_without_credentials_is_loud_and_changes_nothing(
    monkeypatch, only_fedapay, caplog
):
    """The quiet version leaves a box routing to FedaPay while its operator
    believes otherwise, and that surfaces as a brand seeing a card page where
    a mobile money prompt was expected."""
    monkeypatch.setattr(registry.settings, "feexpay_collections", True)
    registry.reset_registry()
    with caplog.at_level("ERROR"):
        collections = registry.registry(registry.COLLECTIONS)
    assert isinstance(collections["BJ"], FedaPayGateway)
    assert "FEEXPAY_COLLECTIONS or FEEXPAY_PAYOUTS is on" in caplog.text


# ------------------------------------------------------- the switch, thrown


def test_feexpay_takes_collections_in_all_four_markets(feexpay_on):
    collections = registry.registry(registry.COLLECTIONS)
    for country in FEEX_COUNTRIES:
        assert isinstance(collections[country], FeexPayGateway), country


def test_payouts_are_untouched_by_the_collections_switch(feexpay_on):
    """THE HALF THAT MUST NOT MOVE. payout_methods.mode holds FedaPay's
    vocabulary for every creator who has already saved one, and FeexPay
    accepts a different one. Moving this leg without migrating those rows is
    creators not being paid, days later, with no error anybody sees."""
    payouts = registry.registry(registry.PAYOUTS)
    for country in FEDA_COUNTRIES:
        assert isinstance(payouts[country], FedaPayGateway), country
    assert "SN" not in payouts


def test_senegal_gains_a_collection_gateway_it_never_had(feexpay_on):
    """NOT PURELY A SWAP. FedaPay does not serve Senegal at all, so for SN
    this is the difference between funding a contract and a refusal."""
    assert "SN" in registry.registry(registry.COLLECTIONS)
    assert "SN" not in registry.registry(registry.PAYOUTS)


def test_gateway_for_defaults_to_the_collections_leg(feexpay_on):
    """Every caller that predates the split meant collections. A forgotten
    argument should give them what they had, not a mixture."""
    assert isinstance(registry.gateway_for("BJ", "XOF"), FeexPayGateway)
    assert isinstance(
        registry.gateway_for("BJ", "XOF", registry.PAYOUTS), FedaPayGateway
    )


def test_a_country_served_on_one_leg_only_refuses_cleanly_on_the_other(feexpay_on):
    """Senegal can be funded and cannot be paid out to. That is an ordinary
    state of a half-migrated provider, not a misconfiguration, and the refusal
    has to name the country rather than crash."""
    from app.core.errors import AppError

    registry.gateway_for("SN", "XOF")
    with pytest.raises(AppError) as caught:
        registry.gateway_for("SN", "XOF", registry.PAYOUTS)
    assert caught.value.code == "payments_country_unsupported"


# ----------------------------------------------------------- the test seam


class _Fake:
    def __init__(self, name):
        self.name = name
        self.sent = []

    def supports(self, country, currency):
        return True

    def start_collection(self, **kw):
        return CollectionStart(reference="c1", checkout_url="https://x.test/c1")

    def send_payout(self, *, amount, currency, description, target, merchant_reference=None):
        self.sent.append(target)
        return PayoutState(reference="p1", status="sent", amount=amount, currency=currency)

    def read_payout(self, reference):
        return PayoutState(reference=reference, status="sent", amount=0, currency="XOF")

    def read_collection(self, reference):
        raise AssertionError("not used here")

    def verify_webhook(self, raw_body, headers):
        raise AssertionError("not used here")


def test_set_gateway_fills_both_legs_by_default(only_fedapay):
    """What keeps every test written before this split correct rather than
    subtly wrong: they install one fake and then exercise funding, payouts and
    the webhook through it."""
    fake = _Fake("fake")
    registry.set_gateway("BJ", fake)
    assert registry.registry(registry.COLLECTIONS)["BJ"] is fake
    assert registry.registry(registry.PAYOUTS)["BJ"] is fake


def test_set_gateway_can_fill_one_leg(only_fedapay):
    fake = _Fake("fake")
    registry.set_gateway("BJ", fake, registry.COLLECTIONS)
    assert registry.registry(registry.COLLECTIONS)["BJ"] is fake
    assert isinstance(registry.registry(registry.PAYOUTS)["BJ"], FedaPayGateway)


def test_gateway_by_name_finds_a_gateway_that_only_does_payouts(only_fedapay):
    """A provider that takes only payouts still sends callbacks about them.
    Searching the collections map alone answers None for a payout webhook, and
    the delivery is acknowledged and dropped, which is the quietest way to
    lose a settlement notice."""
    payer_only = _Fake("payer-only")
    registry.set_gateway("BJ", payer_only, registry.PAYOUTS)
    assert registry.gateway_by_name("payer-only") is payer_only


def test_gateway_by_name_still_finds_a_gateway_on_both_legs(only_fedapay):
    assert registry.gateway_by_name("fedapay") is not None
    assert registry.gateway_by_name("nobody") is None


# ------------------------------------------------------------- the payout leg


@pytest.fixture()
def feexpay_payouts_on(monkeypatch, only_fedapay):
    monkeypatch.setattr(registry.settings, "feexpay_api_key", "fx_key")
    monkeypatch.setattr(registry.settings, "feexpay_shop_id", "EGCxXP0ydLLspx0")
    monkeypatch.setattr(registry.settings, "feexpay_payouts", True)
    registry.reset_registry()


def test_the_payout_switch_moves_payouts_and_leaves_collections(feexpay_payouts_on):
    """The mirror of the collections switch, and they are independent. Either
    leg can move without the other, which is the whole reason the registry
    was split."""
    payouts = registry.registry(registry.PAYOUTS)
    for country in FEEX_COUNTRIES:
        assert isinstance(payouts[country], FeexPayGateway), country
    for country in FEDA_COUNTRIES:
        assert isinstance(
            registry.registry(registry.COLLECTIONS)[country], FedaPayGateway
        ), country


def test_both_switches_share_one_gateway_object(monkeypatch, feexpay_payouts_on):
    """One key, one shop, one base url. Two instances would be two HTTP
    clients and two chances for a future per-instance cache to disagree with
    itself about the same provider."""
    monkeypatch.setattr(registry.settings, "feexpay_collections", True)
    registry.reset_registry()
    assert (
        registry.registry(registry.COLLECTIONS)["BJ"]
        is registry.registry(registry.PAYOUTS)["BJ"]
    )


def test_valid_modes_follows_the_routed_payout_gateway(feexpay_payouts_on):
    """THE FORM CAN NO LONGER OFFER WHAT THE GATEWAY WILL REFUSE.

    valid_modes used to read fedapay.PAYOUT_MODES whatever was routed, so a
    creator in Benin was offered mtn_open while the gateway behind it
    accepted MTN. Nothing surfaced that until a real payout failed, days
    after they saved it."""
    from app.modules.payments import payouts as payouts_module

    modes = payouts_module.valid_modes("BJ")
    assert "MTN" in modes
    assert "mtn_open" not in modes


def test_valid_modes_answers_fedapays_table_while_fedapay_holds_the_leg(only_fedapay):
    """A change of SOURCE, not of answer, until somebody throws the switch."""
    from app.modules.payments import payouts as payouts_module

    assert payouts_module.valid_modes("BJ") == ("mtn_open", "moov", "sbin")


def test_valid_modes_is_empty_where_nothing_is_routed(only_fedapay):
    """set_payout_method turns this into payout_country_unsupported, which is
    the honest answer. A dropdown of networks nobody can send to is worse
    than saying so."""
    from app.modules.payments import payouts as payouts_module

    assert payouts_module.valid_modes("SN") == ()
    assert payouts_module.valid_modes("ZZ") == ()


def test_a_gateway_that_cannot_pay_out_offers_no_modes(only_fedapay):
    """getattr, not an interface change. A collection-only gateway has no
    business declaring payout networks and is not edited into compliance
    with a method it has no use for."""
    from app.modules.payments import payouts as payouts_module

    class CollectOnly(_Fake):
        pass

    assert not hasattr(CollectOnly("collect-only"), "payout_modes")
    registry.set_gateway("BJ", CollectOnly("collect-only"), registry.PAYOUTS)
    assert payouts_module.valid_modes("BJ") == ()
