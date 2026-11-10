"""What a generated contract actually prints, for the lines that say what was
agreed.

TWO THINGS THIS FILE EXISTS FOR, both found by reading a French contract
generated on production rather than by any test:

  1. "Échéance de la campagne : None". A direct order carries no campaign
     deadline, which is most of what this platform generates, and every one of
     those contracts printed the word None into a document somebody signs.
  2. "Livrables : 1 x video on tiktok". An English connector and two raw ids,
     on the single line that says what is being bought, inside a contract whose
     every other sentence had been translated.

Neither was a crash and neither failed anything, which is why both survived to
a screenshot. The assertions below are the ones that would have caught them.

They call _build_body directly with plain objects rather than going through the
database: the function reads seven attributes and two dicts, and a fixture that
builds a campaign, a proposal, two users and two profiles to check a string
would test the fixture.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.platforms import (
    DELIVERABLE_LABELS,
    DELIVERABLE_TYPES,
    PLATFORM_DELIVERABLES,
    PLATFORM_LABELS,
    deliverable_phrase,
)
from app.modules.contracts.service import _build_body

BUSINESS_PARTY = {
    "party_type": "sole_trader",
    "display_label": "Atelier Karité Cotonou",
    "legal_name": "Atelier Karité Cotonou",
    "country": "BJ",
    "address": "Lot 42, Akpakpa, Cotonou",
}
CREATOR_PARTY = {
    "party_type": "sole_trader",
    "display_label": "Nadia Kpossou",
    "legal_name": "Nadia Kpossou",
    "country": "BJ",
    "address": "Quartier Fidjrossè, Cotonou",
}


def body(language="fr", *, deadline=None, deliverables=None):
    campaign = SimpleNamespace(
        title="Vidéo TikTok créative",
        deliverables=deliverables
        if deliverables is not None
        else [{"quantity": 1, "type": "video", "platform": "tiktok"}],
        deadline=deadline,
    )
    proposal = SimpleNamespace(rate_amount=60000, rate_currency="XOF", timeline_days=7)
    return _build_body(
        language,
        campaign,
        proposal,
        SimpleNamespace(id="biz-1"),
        SimpleNamespace(id="creator-1"),
        business_party=BUSINESS_PARTY,
        influencer_party=CREATOR_PARTY,
    )


class TestTheBannerIsGone:
    """It read "MODELE PROVISOIRE. NON REVISE JURIDIQUEMENT." and stood at the
    top of every contract until counsel had read a generated document. Asserted
    as an absence so it cannot return by accident onto a document people sign.

    Contracts generated BEFORE it was removed still carry it: the body is
    hashed at generation and never rewritten, so this says nothing about them
    and must not be read as if it did."""

    @pytest.mark.parametrize("language", ["fr", "en"])
    def test_no_warning_label(self, language):
        out = body(language)
        assert "MODELE PROVISOIRE" not in out
        assert "PLACEHOLDER TEMPLATE" not in out
        assert "NOT LEGALLY REVIEWED" not in out
        assert "NON REVISE JURIDIQUEMENT" not in out

    def test_the_document_now_opens_on_its_own_first_line(self):
        """Nothing is left where the banner was: no leading blank line, no
        orphaned separator."""
        assert body("fr").startswith("Contrat pour la campagne : ")
        assert body("en").startswith("Contract for campaign: ")


class TestTheDeadlineLine:
    """A deadline nobody set is a line that should not be there."""

    @pytest.mark.parametrize("language", ["fr", "en"])
    def test_no_deadline_prints_no_line(self, language):
        out = body(language)
        assert "None" not in out
        assert "Échéance" not in out
        assert "Campaign deadline" not in out

    def test_a_real_deadline_still_prints(self):
        out = body("fr", deadline=date(2026, 12, 1))
        assert "Échéance de la campagne : 2026-12-01" in out

    def test_the_lines_around_it_are_untouched(self):
        """The deadline going missing must not take the rate or timeline with
        it: they sit in the same list literal."""
        out = body("fr")
        assert "Montant convenu : 60000 XOF" in out
        assert "Délai de livraison : 7 jours" in out


class TestTheDeliverablesLine:
    def test_french_contract_reads_french(self):
        assert "Livrables : 1 x Vidéo sur TikTok" in body("fr")

    def test_english_contract_reads_english(self):
        assert "Deliverables: 1 x Video on TikTok" in body("en")

    def test_the_exact_string_that_shipped_is_gone(self):
        """The regression, written as the output rather than as a rule."""
        assert "1 x video on tiktok" not in body("fr")

    def test_several_deliverables_are_listed(self):
        out = body(
            "fr",
            deliverables=[
                {"quantity": 1, "type": "reel", "platform": "instagram"},
                {"quantity": 3, "type": "story", "platform": "instagram"},
            ],
        )
        assert "Livrables : 1 x Reel sur Instagram, 3 x Story sur Instagram" in out

    def test_a_malformed_entry_leaves_no_hole(self):
        """An empty phrase is dropped, so the list cannot read ", , "."""
        out = body(
            "fr",
            deliverables=[
                {"quantity": 1, "type": "video", "platform": "tiktok"},
                {},
            ],
        )
        assert ", ," not in out
        assert "Livrables : 1 x Vidéo sur TikTok" in out


class TestDeliverablePhrase:
    @pytest.mark.parametrize(
        "language,quantity,dtype,platform,expected",
        [
            ("fr", 1, "video", "tiktok", "1 x Vidéo sur TikTok"),
            ("en", 1, "video", "tiktok", "1 x Video on TikTok"),
            ("fr", 3, "story", "instagram", "3 x Story sur Instagram"),
            ("fr", 2, "photo_post", "tiktok", "2 x Publication photo sur TikTok"),
            # UGC is run by the brand as its own advert and is never posted on
            # the creator's account, so it names no platform.
            ("fr", 1, "ugc_video", "ugc", "1 x Vidéo UGC"),
            ("en", 2, "ugc_photo", "ugc", "2 x UGC photo"),
        ],
    )
    def test_known_ids(self, language, quantity, dtype, platform, expected):
        assert deliverable_phrase(language, quantity, dtype, platform) == expected

    @pytest.mark.parametrize("quantity", [None, 0, -1, True, "two", 1.5])
    def test_a_quantity_that_is_not_a_count_is_dropped(self, quantity):
        """Never "None x", and never "True x" either: this value comes off a
        JSON column that nothing in the database constrains."""
        out = deliverable_phrase("fr", quantity, "video", "tiktok")
        assert out == "Vidéo sur TikTok"

    def test_an_unknown_type_degrades_rather_than_raising(self):
        """Contract generation runs when the creator presses Accept. A
        KeyError here would be a 500 landing on the one person who cannot fix
        it, over a label."""
        assert deliverable_phrase("fr", 1, "hologram", "tiktok") == "1 x Hologram sur TikTok"

    def test_an_unknown_platform_degrades_too(self):
        assert deliverable_phrase("fr", 1, "video", "bereal") == "1 x Vidéo sur Bereal"

    def test_an_unknown_language_falls_back_to_english(self):
        assert deliverable_phrase("zz", 1, "video", "tiktok") == "1 x Video on TikTok"


class TestTheLabelsAreComplete:
    """The guard that makes the table above maintainable rather than a thing
    somebody has to remember. A deliverable added to PLATFORM_DELIVERABLES
    without a label would otherwise print its id onto a signed document."""

    @pytest.mark.parametrize("language", ["fr", "en"])
    def test_every_deliverable_type_has_a_label(self, language):
        assert DELIVERABLE_TYPES - set(DELIVERABLE_LABELS[language]) == set()

    @pytest.mark.parametrize("language", ["fr", "en"])
    def test_no_label_describes_a_type_that_does_not_exist(self, language):
        assert set(DELIVERABLE_LABELS[language]) - DELIVERABLE_TYPES == set()

    def test_every_platform_has_a_label(self):
        assert set(PLATFORM_DELIVERABLES) - set(PLATFORM_LABELS) == set()

    def test_no_platform_label_is_orphaned(self):
        assert set(PLATFORM_LABELS) - set(PLATFORM_DELIVERABLES) == set()

    def test_both_languages_cover_the_same_ids(self):
        assert set(DELIVERABLE_LABELS["fr"]) == set(DELIVERABLE_LABELS["en"])
