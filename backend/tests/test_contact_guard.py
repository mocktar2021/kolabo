"""Contact details do not travel through Kolabo (app.core.contact_guard).

THE NEGATIVE BLOCK IS THE IMPORTANT ONE, and it is deliberately larger than
the positive block. A guard that misses a phone number costs one deal. A guard
that refuses a creator's quote costs the platform its credibility with both
sides at once: it teaches them that Kolabo is broken, and the next thing they
do is take the conversation somewhere that works — which is the exact outcome
the guard exists to prevent. So every sentence in NOT_CONTACT_DETAILS is a
real thing somebody in this marketplace writes, and every one of them must
come back clean.

The enforcement tests each assert two things: the 400, and that NOTHING WAS
WRITTEN. The second is the one worth having. A guard that refused the response
but left the row behind, or that quietly stripped the number and saved the
rest, would pass a status-code assertion and would be a worse product than no
guard at all — an altered message is a sentence the sender never wrote and the
recipient cannot trust.
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.contact_guard import EMAIL, HANDLE, PHONE, find_contact_details
from app.core.db import Base
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.campaigns import service as campaigns_service
from app.modules.contracts import models as contracts
from app.modules.messaging import conversations as messaging_conversations
from app.modules.messaging import service as messaging_service
from app.modules.messaging.models import Message
from app.modules.notifications import models as notifications  # noqa: F401
from app.modules.payments import disputes as payments_disputes
from app.modules.payments import models as payments
from app.modules.profiles import models as profiles  # noqa: F401


# ---------------------------------------------------------------------------
# The pure function
# ---------------------------------------------------------------------------

CONTACT_DETAILS = [
    # Plain addresses.
    ("ama.k@gmail.com", EMAIL),
    ("Envoie les fichiers à studio+brief@kolabo.africa merci", EMAIL),
    # Obfuscations. Nobody puts a word in brackets between two others by
    # accident, so the bracketed form needs no domain suffix to be believed.
    ("ama.k (at) gmail.com", EMAIL),
    ("ama[at]gmail[dot]com", EMAIL),
    ("ama {at} gmail (dot) com", EMAIL),
    ("ama at gmail dot com", EMAIL),
    ("contact (arobase) studio", EMAIL),
    ("amak (at) gmail", EMAIL),
    # Phone numbers, separated the way people actually write them here.
    ("06 12 34 56 78", PHONE),
    ("06.12.34.56.78", PHONE),
    ("06-12-34-56-78", PHONE),
    ("+229 97 00 00 00", PHONE),
    ("+22997000000", PHONE),
    ("0612345678", PHONE),
    ("Mon numéro: 97000000", PHONE),
    ("Tu peux joindre le 97 00 00 00 après 18h", PHONE),
    # Handing the conversation to another app.
    ("whatsapp me on 97 00 00 00", HANDLE),
    ("WhatsApp moi", HANDLE),
    ("Telegram: @ama_k", HANDLE),
    ("telegram @ama_k", HANDLE),
    ("Écris-moi sur WhatsApp", HANDLE),
    ("add me on Telegram", HANDLE),
    ("On peut continuer sur Signal", HANDLE),
    ("On en parle sur whatsapp", HANDLE),
    ("https://wa.me/22997000000", HANDLE),
    ("t.me/amak", HANDLE),
]


@pytest.mark.parametrize("text,kind", CONTACT_DETAILS)
def test_contact_details_are_found(text, kind):
    assert kind in find_contact_details(text)


# Every one of these is a sentence somebody writes on this platform in the
# ordinary course of doing a job. Not one of them may be refused. When a real
# false positive turns up, it belongs in this list before it is fixed.
NOT_CONTACT_DETAILS = [
    # Money, which in XOF means long numbers everywhere.
    "Budget 300000 XOF pour trois posts.",
    "Le tarif est de 1 000 000 XOF, commission incluse.",
    "On vise 12 000 000 FCFA sur le trimestre.",
    "Je facture 45 000 F par post, soit 135 000 F au total.",
    "Mon prix plancher est 15000000 FCFA pour la campagne entière.",
    "Le paiement de 2 500 000 XOF est déjà en escrow.",
    "1 000 000",
    "300000 XOF",
    "Total 7 500 000 francs CFA, TVA comprise.",
    # Dates, in every shape this product writes them.
    "Livraison le 02/08/2026 au plus tard.",
    "Deadline 02-08-2026, tournage le 2026-08-15.",
    "Publication prévue le 02.08.2026.",
    "Du 01/09/2026 au 30/09/2026.",
    # Identifiers and references.
    "Le contrat CT-2026-000123 est signé.",
    "Référence virement REF8829301145 reçue ce matin.",
    "Facture INV-2026-0042 jointe.",
    "Escrow 9f2c4a7e10b34d55 libéré.",
    "Voir kolabo.africa/contracts/2026-000123 pour le détail.",
    # Audience and performance numbers.
    "J'ai 250000 abonnés sur Instagram et 90000 sur TikTok.",
    "La dernière vidéo a fait 1 234 567 vues en dix jours.",
    "Taux d'engagement 4.2% sur les 30 derniers jours.",
    # Prose that happens to contain numbers, or the word "at".
    "3 posts, 2 reels et 1 story, livrés en 7 jours.",
    "On se voit à 14h30 pour le brief.",
    "La version 2 du contrat remplace la version 1.",
    "Let's meet at the studio at 10 and shoot at noon.",
    "I'll send the files at the end of the week.",
    "Available at kolabo.africa if you want the deck.",
    # Naming an app is not handing over an address.
    "The signal was bad during the live, we lost 20 minutes.",
    "Je n'utilise pas beaucoup WhatsApp en ce moment.",
    "On parlera du montage sur place demain.",
    "Je vais passer au studio vers midi.",
    # Ordinary working messages, which are most of the traffic.
    "Le brief est clair, je livre lundi.",
    "La lumière était mauvaise, je peux retourner jeudi ?",
    "Merci, j'ai bien reçu la première version.",
]


@pytest.mark.parametrize("text", NOT_CONTACT_DETAILS)
def test_ordinary_prose_is_not_contact_details(text):
    assert find_contact_details(text) == []


def test_nothing_in_nothing_out():
    """Optional fields hand this None all day; callers should not need a check."""
    assert find_contact_details(None) == []
    assert find_contact_details("") == []
    assert find_contact_details("   ") == []


def test_several_kinds_are_all_reported():
    """The refusal names everything it found, so the writer fixes it once."""
    found = find_contact_details("ama@gmail.com ou 97 00 00 00, ou telegram @amak")
    assert found == [EMAIL, PHONE, HANDLE]


# ---------------------------------------------------------------------------
# Enforcement, one surface at a time
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    try:
        yield session
    finally:
        session.close()


def _deal(db):
    """A brand, a creator, a published campaign, a contract and a held escrow.

    Everything the four guarded surfaces need between them. The contract is
    what opens messaging; the escrow is what a dispute freezes.
    """
    biz = User(
        phone="+22990000001", password_hash="x", country_code="BJ", role="business", is_verified=True
    )
    inf = User(
        phone="+22990000002", password_hash="x", country_code="BJ", role="influencer", is_verified=True
    )
    db.add_all([biz, inf])
    db.commit()
    db.refresh(biz)
    db.refresh(inf)

    campaign = campaigns.Campaign(
        business_user_id=biz.id,
        title="Launch push",
        budget_amount=300000,
        budget_currency="XOF",
        deliverables=[{"platform": "instagram", "type": "post", "quantity": 1}],
        status=campaigns.PUBLISHED,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    proposal = campaigns.Proposal(
        campaign_id=campaign.id,
        influencer_user_id=inf.id,
        version=1,
        rate_amount=300000,
        rate_currency="XOF",
        timeline_days=5,
        status=campaigns.SUBMITTED,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    contract = contracts.Contract(
        campaign_id=campaign.id,
        proposal_id=proposal.id,
        business_user_id=biz.id,
        influencer_user_id=inf.id,
        language="fr",
        body="placeholder",
        rate_amount=300000,
        rate_currency="XOF",
        timeline_days=5,
        deliverables=[],
        status=contracts.PENDING,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    now = payments.utcnow()
    escrow = payments.Escrow(
        contract_id=contract.id,
        campaign_id=campaign.id,
        business_user_id=biz.id,
        influencer_user_id=inf.id,
        amount=300000,
        currency="XOF",
        provider="test",
        provider_fund_ref="fund-1",
        status=payments.HELD,
        held_at=now,
        due_release_at=now + timedelta(days=7),
    )
    db.add(escrow)
    db.commit()
    db.refresh(escrow)

    return SimpleNamespace(
        business=biz.id, creator=inf.id, campaign=campaign.id, escrow=escrow.id
    )


def test_the_per_campaign_send_refuses_a_phone_number(db):
    deal = _deal(db)
    with pytest.raises(HTTPException) as exc:
        messaging_service.send_message(
            db,
            deal.campaign,
            deal.business,
            deal.creator,
            "Parfait. Appelle-moi au 06 12 34 56 78 pour caler la date.",
        )
    assert exc.value.status_code == 400
    assert "phone number" in exc.value.detail
    assert "Kolabo" in exc.value.detail
    # Refused, not redacted, and not half-saved.
    assert db.query(Message).count() == 0


def test_the_per_counterparty_send_refuses_a_handle(db):
    """Two ways to write a message must not mean one way to write a number."""
    deal = _deal(db)
    with pytest.raises(HTTPException) as exc:
        messaging_conversations.send_to(
            db, deal.creator, deal.business, "whatsapp me on 97 00 00 00, c'est plus simple"
        )
    assert exc.value.status_code == 400
    assert db.query(Message).count() == 0


def test_an_ordinary_message_still_goes_through(db):
    """The assertion that catches this feature turning into friction.

    A working message full of the numbers this marketplace runs on — a rate, a
    deadline, a count of deliverables — has to land.
    """
    deal = _deal(db)
    sent = messaging_service.send_message(
        db,
        deal.campaign,
        deal.business,
        deal.creator,
        "Ok pour 300000 XOF, 3 posts livrés avant le 02/08/2026. Contrat CT-2026-000123.",
    )
    assert sent["body"].startswith("Ok pour 300000 XOF")
    assert db.query(Message).count() == 1


def test_the_proposal_note_refuses_an_email(db):
    deal = _deal(db)
    payload = SimpleNamespace(
        rate_amount=250000,
        rate_currency="xof",
        timeline_days=5,
        note="Ok pour ce tarif. Envoie le brief à ama.k (at) gmail.com",
    )
    with pytest.raises(HTTPException) as exc:
        campaigns_service.submit_proposal(db, deal.campaign, deal.creator, payload)
    assert exc.value.status_code == 400
    assert "email address" in exc.value.detail
    # The chain is untouched: the version that was already there is still the
    # live one, and no new row was written.
    assert db.query(campaigns.Proposal).count() == 1
    assert db.query(campaigns.Proposal).one().status == campaigns.SUBMITTED


def test_the_dispute_statement_refuses_a_phone_number(db):
    deal = _deal(db)
    payload = SimpleNamespace(
        reason="not_delivered",
        statement="Rien n'a été livré. Appelle-moi au 97 00 00 00 pour qu'on règle ça.",
        media_ids=[],
    )
    with pytest.raises(HTTPException) as exc:
        payments_disputes.raise_dispute(db, deal.business, deal.escrow, payload)
    assert exc.value.status_code == 400
    assert db.query(payments.Dispute).count() == 0
    # And the escrow was never frozen on the back of a refused claim.
    assert db.query(payments.Escrow).one().status == payments.HELD


def test_a_dispute_message_refuses_a_handle(db):
    """The turn where somebody says "let's sort this out between us".

    Which is the moment the escrow decision they asked for stops being
    possible, so it is the one that most needs refusing.
    """
    deal = _deal(db)
    payments_disputes.raise_dispute(
        db,
        deal.business,
        deal.escrow,
        SimpleNamespace(
            reason="late",
            statement="La vidéo a deux semaines de retard sur le contrat.",
            media_ids=[],
        ),
    )
    dispute = db.query(payments.Dispute).one()

    with pytest.raises(HTTPException) as exc:
        payments_disputes.post_message(
            db,
            deal.creator,
            dispute.id,
            SimpleNamespace(body="Écris-moi sur WhatsApp, on règle ça entre nous.", media_ids=[]),
        )
    assert exc.value.status_code == 400
    assert db.query(payments.DisputeMessage).count() == 0
