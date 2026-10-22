"""Contracts business logic (Epic E).

KOL-24: generate a contract from an accepted proposal, populating all agreed
terms without manual re-entry. Legal reviewed templates per country are not
available yet, so the body is built from a clearly labeled placeholder template
per language, and the PR flags that legal review is required before production.
KOL-25: e-sign the contract. Signatures are timestamped and attributable, both
signatures are required before the contract is fully signed (which is what
Epic G will check before unlocking payment), and once signed the contract is
immutable. A ContractEvent audit row is written for every lifecycle event.

THE DOCUMENT NOW NAMES ITS PARTIES. Until this change the body identified them
with two lines holding two UUIDs, which meant the signature at the bottom
validated against nothing: there was no legal name anywhere in the database to
compare the typed string to. The party identification block below follows the
structure of the model counsel approved
(claude/kolabo-contrat-collaboration-modele-fr.md, "ENTRE LES SOUSSIGNES"), and
it is rendered from a SNAPSHOT taken at generation rather than from a live join
onto the profiles. See _party_snapshots for why that distinction is the whole
point.

Nothing in that block is verified. Party details are self-declared contract
content, exactly as they would be on a paper contract: Kolabo records what each
side states about itself and does not check it. No copy here may imply
otherwise.
"""
import hashlib
from copy import deepcopy
from datetime import date

from fastapi import status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.identity import creator_identities
from app.modules.auth.models import User
from app.modules.campaigns import models as campaigns
from app.modules.campaigns import service as campaigns_service
from app.modules.contracts import models
from app.modules.notifications.service import notify
# MODELS ONLY. payments.service imports contracts.models, so reaching for its
# service here would close the circle; its models import nothing but Base.
# contracts/cancellation.py reads the escrow the same way for the same reason.
from app.modules.payments import models as payments
from app.modules.profiles.models import (
    ASSOCIATION,
    REGISTERED_COMPANY,
    SOLE_TRADER,
    BusinessProfile,
    InfluencerProfile,
)

# Language per country. Kept local to avoid coupling to optional country_config
# fields; Cameroon defaults to French for the contract body for now.
FRENCH_COUNTRIES = {"BJ", "TG", "CI", "SN", "CM"}

# The Terms version in force, stamped onto every contract as `legal_version`.
#
# THIS IS THE SECOND COPY OF THIS DATE AND THE FIRST ONE ON THE BACKEND. The
# only other is LEGAL_EFFECTIVE_DATE in web/src/pages/LegalPage.tsx, which is
# what the published Terms page stamps itself with. There is no terms
# acceptance record anywhere in this backend, no settings entry and no shared
# constant to read, so the choice was between a second literal here and
# contracts that cannot say which Terms they were signed under. A signed
# document that cannot name its own terms version is the worse of the two, and
# it cannot be fixed afterwards: the body is hashed at generation and the early
# contracts are exactly the ones a dispute is most likely to be about.
#
# THE TWO COPIES MUST MOVE TOGETHER. Whoever changes the date on the Terms page
# owns changing it here in the same commit, because the contract is claiming to
# have been signed under the Terms the site was publishing that day. The
# honest fix is one authoritative value the backend owns and the web app reads
# from the API; that is a separate change and it is not this one.
LEGAL_EFFECTIVE_DATE = "2026-10-03"

# What signing a cancelled contract is refused with. Its own sentence rather
# than the fully-signed one, because the two refusals point somewhere
# different: a signed contract is finished and unchangeable, a cancelled one
# is over, and the way forward is a new agreement rather than a retry. Named
# for the same reason cancellation.SIGNED_DETAIL is — the sentence is long
# enough that it reads better out of the raise.
CANCELLED_SIGN_DETAIL = (
    "This contract was cancelled and can no longer be signed. Agree new terms "
    "and generate a new contract."
)

# The two refusals when a side has not stated who it is contracting as.
#
# TWO CODES AND TWO SENTENCES FOR ONE RULE, deliberately, because the person
# who has to act is different in each case and the refusal lands on the buyer
# either way. The buyer has chosen a creator, agreed terms and is trying to
# close; being told "party details are missing" without being told WHOSE is
# being told to go and guess. The client keys its translated sentence off the
# code, so these two have to stay distinct even though the rule is one rule.
#
# Each sentence names the profile the missing block lives on, and neither
# suggests the details will be checked, because they will not be.
BUSINESS_PARTY_MISSING_DETAIL = (
    "This contract cannot be generated yet: the business has not stated who it "
    "is contracting as. Add the company or trader details on the business "
    "profile, then accept the proposal again."
)
CREATOR_PARTY_MISSING_DETAIL = (
    "This contract cannot be generated yet: the creator has not stated who they "
    "are contracting as. They have to add their party details on their profile "
    "before a contract can be written from this proposal."
)


def _language_for(country_code: str) -> str:
    return "fr" if country_code in FRENCH_COUNTRIES else "en"


# ---------------------------------------------------------------------------
# The party identification block
#
# One renderer serves both sides, and the two questions it answers are kept
# apart on purpose:
#
#   * WHICH SIDE a block belongs to decides the heading above it and the
#     designation sentence under it ("the Business", "the Creator"). That is
#     fixed by the contract, not by the party.
#   * WHAT KIND OF ENTITY the party is decides which fields print. That is
#     `party_type`, and it varies independently of the side. A business is NOT
#     required to be a registered company (founder's decision: the unregistered
#     branch is a first-class option, not a lesser one), and an agency holding
#     a creator account can legitimately state a company. So the business side
#     can be a sole trader and the creator side can be a registered company,
#     and neither is an error to be defended against.
#
# The field sets and their order come from the party identification block of
# the approved French model, with two differences, both of them removals. The
# model's "Piece d'identite" line is NOT rendered, because the founder decided
# on 3 October that no identity documents are collected and a line asking for
# one would contradict that. Everything from "PREAMBULE" onwards in that model
# is out of scope here: this renders an identification block, it does not draft
# clauses.
#
# ACCENTED FRENCH, unlike the legacy placeholder banner a few lines down which
# is plain ASCII. The banner is a warning label and it is pinned by an existing
# test; this is the part of the document that names a human being and a company
# on something they sign. "Siege" and "Representee" in a party block would be
# wrong on a document going to counsel, and the rest of this backend already
# writes proper French to users (see auth/otp.py).
# ---------------------------------------------------------------------------

# The three party types come from profiles.models, which owns the closed set
# and documents what each one is. Imported rather than restated as literals
# here: a renderer with its own copy of a discriminator is a renderer that
# silently stops printing a type the day a fourth one is added, and the
# _FALLBACK_FIELDS branch below is the only safety net for that.
BUSINESS_SIDE = "business"
CREATOR_SIDE = "creator"

# French puts a space before a colon and English does not. One lookup rather
# than two label tables with the punctuation baked into every entry.
_LABEL_SEPARATOR = {"fr": " : ", "en": ": "}

_UNDERSIGNED_HEADING = {
    "fr": "ENTRE LES SOUSSIGNÉS",
    "en": "BETWEEN THE UNDERSIGNED",
}

_SIDE_HEADING = {
    "fr": {
        BUSINESS_SIDE: "D'une part, l'Entreprise :",
        CREATOR_SIDE: "D'autre part, le Créateur :",
    },
    "en": {
        BUSINESS_SIDE: "Of the one part, the Business:",
        CREATOR_SIDE: "Of the other part, the Creator:",
    },
}

_SIDE_DESIGNATION = {
    "fr": {
        BUSINESS_SIDE: "Ci-après dénommée « l'Entreprise ».",
        CREATOR_SIDE: "Ci-après dénommé « le Créateur ».",
    },
    "en": {
        BUSINESS_SIDE: 'Hereinafter "the Business".',
        CREATOR_SIDE: 'Hereinafter "the Creator".',
    },
}

_BOTH_PARTIES = {
    "fr": (
        "Ci-après dénommés ensemble « les Parties » et individuellement "
        "« une Partie »."
    ),
    "en": 'Hereinafter together "the Parties" and individually "a Party".',
}

# THE UUID STAYS, as the last field of each block. It is the only identifier
# in here that is stable and unique: a legal name is self-declared free text
# that two companies can share and one company can change, and it is what an
# admin opening a support ticket has to search by. The approved model carries
# the same line on the creator side ("Identifiant du compte Kolabo"), so this
# is the model's own field rather than an addition to it.
_ACCOUNT_ID_LABEL = {
    "fr": "Identifiant du compte Kolabo",
    "en": "Kolabo account id",
}

_REPRESENTED_BY = {"fr": "Représentée par", "en": "Represented by"}
_IN_CAPACITY = {"fr": "en qualité de", "en": "in the capacity of"}

# (label, party block key), in the order the approved model prints them.
#
# `tax_identifier` appears on the registered company branch only. The spec
# records it as an optional field on a sole trader block as well, but its
# rendering list for a sole trader is name, address and country alone, so a
# sole trader's tax identifier is captured and not printed. That is the spec
# as written rather than an oversight here, and it is flagged rather than
# silently resolved either way: printing a field the spec did not list on a
# document counsel has not seen is the worse of the two mistakes.
_PARTY_FIELDS = {
    "fr": {
        REGISTERED_COMPANY: (
            ("Raison sociale", "legal_name"),
            ("Forme juridique", "legal_form"),
            ("Immatriculation (RCCM ou équivalent)", "registration_number"),
            ("Identifiant fiscal", "tax_identifier"),
            ("Siège", "address"),
            ("Pays", "country"),
        ),
        SOLE_TRADER: (
            ("Nom et prénoms", "legal_name"),
            ("Adresse", "address"),
            ("Pays de résidence", "country"),
        ),
        ASSOCIATION: (
            ("Dénomination", "legal_name"),
            ("Immatriculation", "registration_number"),
            ("Siège", "address"),
            ("Pays", "country"),
        ),
    },
    "en": {
        REGISTERED_COMPANY: (
            ("Legal name", "legal_name"),
            ("Legal form", "legal_form"),
            ("Registration number (RCCM or equivalent)", "registration_number"),
            ("Tax identifier", "tax_identifier"),
            ("Registered office", "address"),
            ("Country", "country"),
        ),
        SOLE_TRADER: (
            ("Full name", "legal_name"),
            ("Address", "address"),
            ("Country of residence", "country"),
        ),
        ASSOCIATION: (
            ("Name", "legal_name"),
            ("Registration number", "registration_number"),
            ("Registered office", "address"),
            ("Country", "country"),
        ),
    },
}

# What a block of an UNKNOWN party_type prints. Not dead code and not
# defensiveness for its own sake: `party_type` is a plain string inside a JSON
# blob with a closed set enforced in Python, exactly like social_accounts
# .status, and that set has already grown once elsewhere in this repo. The day
# a fourth type is captured, generation must still produce a document that
# names both parties rather than raise a KeyError in the middle of writing a
# legal instrument. These three keys are the ones every block carries whatever
# its type.
_FALLBACK_FIELDS = {
    "fr": (("Partie", "display_label"), ("Adresse", "address"), ("Pays", "country")),
    "en": (("Party", "display_label"), ("Address", "address"), ("Country", "country")),
}

# The types that act through somebody. A sole trader signs for themselves, so
# a "represented by" line under their own name would be noise at best.
_REPRESENTED_TYPES = (REGISTERED_COMPANY, ASSOCIATION)

# The standing annex sentence, present on EVERY contract whether or not an
# annex feature exists and whether or not one has been attached.
#
# WHY IT IS HERE BEFORE THE FEATURE IS. The body is hashed at generation and
# never rehashed, so a contract cannot be amended once it is written. A
# sentence added when the upload button ships would be absent from every
# contract signed before that day, which is precisely the set of contracts the
# first dispute will come from. It costs one line now and cannot be bought
# back later.
#
# The wording is the spec's own (§7.8 item 2) and says only what the approved
# design says: the attached document is between the parties and does not touch
# the payment terms. Counsel approved the DESIGN on 3 October; the wording that
# implements it is on her list as drafting review (§7.9), so this sentence is
# expected to be replaced by hers and must not be treated as settled text.
_ANNEX_SENTENCE = {
    "fr": (
        "Tout document que les Parties annexent à la présente collaboration "
        "constitue une annexe entre elles et ne modifie pas les conditions de "
        "paiement énoncées ci-dessus."
    ),
    "en": (
        "Any document the parties attach to this collaboration is an annex "
        "between them and does not modify the payment terms recorded above."
    ),
}


def _party_lines(language: str, side: str, party: dict | None, user_id: str) -> list[str]:
    """One side's identification block, rendered from its snapshot.

    Reads `legal_name` for the party's name rather than `display_label`, and
    the two are the same string by construction: `display_label` is DERIVED
    from `legal_name` at capture and stored so that the contract card and any
    list has one field to read without branching on `party_type`. Taking the
    name from `legal_name` here means that even if a client ever got a label of
    its own choosing into a profile, it could not rename a party on a document
    somebody signs. `display_label` is still the fallback, below, for the one
    case where there is no legal name to print.

    An empty field is DROPPED rather than printed empty. "Identifiant fiscal :"
    with nothing after it reads, on a signed document, as a field somebody was
    meant to fill in and did not; a line that is simply absent reads as a field
    that does not apply. The optional fields and anything a forward-added party
    type does not carry both land here.
    """
    separator = _LABEL_SEPARATOR[language]
    block = party or {}
    party_type = block.get("party_type")
    fields = _PARTY_FIELDS[language].get(party_type) or _FALLBACK_FIELDS[language]

    lines = [_SIDE_HEADING[language][side]]
    for label, key in fields:
        value = block.get(key)
        if key == "legal_name" and not value:
            # A contract that names nobody is worse than one that names the
            # party by the label derived from the name it does not have.
            value = block.get("display_label")
        if value is None or value == "":
            continue
        lines.append(f"{label}{separator}{value}")

    if party_type in _REPRESENTED_TYPES:
        representative = block.get("representative_name")
        capacity = block.get("representative_capacity")
        if representative and capacity:
            lines.append(
                f"{_REPRESENTED_BY[language]}{separator}{representative}, "
                f"{_IN_CAPACITY[language]} {capacity}"
            )
        elif representative:
            # Capacity missing is a capture-side gap, not a reason to leave the
            # signatory off the document entirely.
            lines.append(f"{_REPRESENTED_BY[language]}{separator}{representative}")

    lines.append(f"{_ACCOUNT_ID_LABEL[language]}{separator}{user_id}")
    lines.append(_SIDE_DESIGNATION[language][side])
    return lines


def _build_body(
    language: str,
    campaign: campaigns.Campaign,
    proposal: campaigns.Proposal,
    business: User,
    influencer: User,
    *,
    business_party: dict | None,
    influencer_party: dict | None,
) -> str:
    banner_en = "PLACEHOLDER TEMPLATE. NOT LEGALLY REVIEWED. Do not use in production until reviewed by qualified counsel per country."
    banner_fr = "MODELE PROVISOIRE. NON REVISE JURIDIQUEMENT. Ne pas utiliser en production avant revision par un conseil juridique qualifie par pays."
    deliverables = ", ".join(f"{d.get('quantity')} x {d.get('type')} on {d.get('platform')}" for d in (campaign.deliverables or []))
    banner = banner_fr if language == "fr" else banner_en
    # STAYS UNTIL COUNSEL HAS READ A GENERATED DOCUMENT. Naming the parties is
    # what makes the document worth reviewing; it is not the review. Removing
    # the banner is a one-line change the day she signs off and is tracked
    # separately from this work.
    lines = [
        banner,
        "",
        # Frozen here, which is why campaigns/editing.py locks `title` once a
        # contract exists. Without that lock the buyer could rename the brief
        # and the card would then disagree with the signed document.
        f"Contract for campaign: {campaign.title}",
        "",
        _UNDERSIGNED_HEADING[language],
        "",
        *_party_lines(language, BUSINESS_SIDE, business_party, business.id),
        "",
        *_party_lines(language, CREATOR_SIDE, influencer_party, influencer.id),
        "",
        _BOTH_PARTIES[language],
        "",
        f"Deliverables: {deliverables}",
        f"Agreed rate: {proposal.rate_amount} {proposal.rate_currency} (minor units)",
        f"Timeline: {proposal.timeline_days} days",
        f"Campaign deadline: {campaign.deadline}",
        "",
        "Both parties must sign electronically. Payment is unlocked only after both signatures are recorded.",
        "",
        # After the payment terms, because it says it does not modify them.
        _ANNEX_SENTENCE[language],
    ]
    return "\n".join(lines)


def _body_hash(body: str) -> str:
    """The hash stored as `body_sha256`, over the body's UTF-8 bytes.

    This is the only thing that later proves the stored text is the text that
    was signed. The signature itself is a free-text string beside a server
    timestamp, which says that somebody signed SOMETHING; the hash is what
    says what. Computed once, at generation, and never recomputed: a hash
    refreshed from the current body would agree with it by definition and
    prove nothing at all.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _party_snapshots(
    db: Session, business_user_id: str, influencer_user_id: str
) -> tuple[dict, dict]:
    """Both party blocks, COPIED off the profiles for this one contract.

    Refuses generation when either side is missing, with a distinct code per
    side. That refusal is a backstop and not the place a user should discover
    this: by the time it fires, a buyer has chosen a creator and agreed terms,
    and if the creator never filled their block the failure lands on the buyer.
    Making party details a precondition earlier, on the creator's own
    onboarding and before a business publishes, is the product fix and is a
    separate decision.

    A COPY, NEVER A JOIN, and never the profile's own dict object either. This
    is the reasoning payments/models.py already applies to money: PaymentIntent
    copies the amounts off the contract rather than reading them through a join
    at settlement, because otherwise "a join would silently settle the new
    number against the old payment". The same failure with identities is worse
    than with amounts, because it is silent and retroactive: a company that
    renames itself, or a creator who corrects their address, would rewrite who
    every historical contract says signed it, including ones already disputed.

    deepcopy rather than the dict SQLAlchemy handed back, because that dict
    belongs to the profile row and is tracked on it. Assigning it straight onto
    the contract would leave two rows sharing one mutable object: a later edit
    to the profile in the same session would mutate the contract's snapshot in
    place, and the mutation tracking could flush it to the contract's column as
    well. The snapshot exists to be unaffected by exactly that.
    """
    business_party = (
        db.query(BusinessProfile.party_details)
        .filter(BusinessProfile.user_id == business_user_id)
        .scalar()
    )
    if not business_party:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_business_party_missing",
            detail=BUSINESS_PARTY_MISSING_DETAIL,
        )
    influencer_party = (
        db.query(InfluencerProfile.party_details)
        .filter(InfluencerProfile.user_id == influencer_user_id)
        .scalar()
    )
    if not influencer_party:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_creator_party_missing",
            detail=CREATOR_PARTY_MISSING_DETAIL,
        )
    return deepcopy(business_party), deepcopy(influencer_party)


def _out(contract: models.Contract) -> dict:
    business_signed = contract.business_signed_at is not None
    influencer_signed = contract.influencer_signed_at is not None
    return {
        "id": contract.id,
        "campaign_id": contract.campaign_id,
        "proposal_id": contract.proposal_id,
        "business_user_id": contract.business_user_id,
        "influencer_user_id": contract.influencer_user_id,
        "language": contract.language,
        "status": contract.status,
        "rate_amount": contract.rate_amount,
        "rate_currency": contract.rate_currency,
        "timeline_days": contract.timeline_days,
        "business_signed": business_signed,
        "influencer_signed": influencer_signed,
        "fully_signed": contract.status == models.SIGNED,
    }


def generate_from_proposal(
    db: Session,
    business_user_id: str,
    proposal_id: str,
    *,
    allow_business_offer: bool = False,
) -> dict:
    """Accept the live offer in a negotiation and write the contract from it.

    `allow_business_offer` is for ONE caller: campaigns/orders.accept_direct_order,
    where the creator is the one accepting and the offer on the table is
    legitimately the buyer's. Everywhere else the rule below holds. It is a
    parameter rather than something inferred from the actor because the actor
    is the business on both paths — accept_direct_order passes the buyer's id
    deliberately, so identity cannot tell the two apart.
    """
    proposal = db.query(campaigns.Proposal).filter(campaigns.Proposal.id == proposal_id).first()
    if proposal is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_proposal_not_found",
            detail="Proposal not found",
        )
    campaign = db.query(campaigns.Campaign).filter(campaigns.Campaign.id == proposal.campaign_id).first()
    if campaign is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_campaign_not_found",
            detail="Campaign not found",
        )
    if campaign.business_user_id != business_user_id:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            # campaigns' code, not a contract one: the rule is that this
            # campaign is not yours, and it is enforced identically in
            # campaigns/service.py. Two codes for one rule is two sentences to
            # keep in step in two languages.
            code="campaign_not_yours",
            detail="Not your campaign",
        )

    # A dead campaign has no deal left in it to write down. campaigns/editing.py
    # cancel_campaign only refuses when a contract ALREADY exists, and it does
    # not touch the proposals hanging off the brief — so after a cancellation
    # every proposal on it is still `submitted`, and without this guard the
    # buyer could turn one into a contract afterwards. The creators were
    # notified the brief was off; the contract would be written against them
    # anyway, and payments.assert_fundable asks only about the contract's own
    # status, never about the campaign behind it, so it would fund normally.
    #
    # Written as "must be PUBLISHED" rather than "must not be CANCELLED"
    # because the set of states that are not open is going to grow — a
    # completed state is coming — and only the open one is worth naming.
    if campaign.status != campaigns.PUBLISHED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_campaign_not_open",
            detail="This campaign is no longer open, so no new contract can be created from it.",
        )

    # And its deadline, which until this guard nothing anywhere enforced.
    # campaigns/service.py::submit_proposal carries the reasoning for the rule;
    # what makes it matter HERE is what this path does. The other three refuse
    # a proposal, which costs somebody an evening. This one turns an old bid
    # into a signed, fundable agreement, so it is both the last place the rule
    # can be applied and the one place where missing it ends in real money
    # moving against a brief whose date went by months ago.
    #
    # Inclusive of the deadline's own day, exactly as the campaigns-side guards
    # are. NULL passes untouched: a direct order carries no deadline at all
    # (service._place_order writes none), and neither do the briefs written
    # before a deadline was required to publish.
    if campaign.deadline is not None and campaign.deadline < date.today():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="campaign_deadline_passed",
            detail="This brief's deadline has passed, so it is no longer taking proposals.",
        )

    # A proposal id names a negotiation, not a frozen offer. Since the business
    # can now counter, the chain moves on — sometimes by the business's own
    # hand — and the id on the page can be a round or two behind. The contract
    # is written from the LAST version in the chain, so nobody ever signs terms
    # that were already replaced.
    latest = campaigns_service.latest_in_chain(db, proposal.campaign_id, proposal.influencer_user_id) or proposal

    existing = (
        db.query(models.Contract)
        .filter(models.Contract.proposal_id.in_({proposal_id, latest.id}))
        .first()
    )
    if existing is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="contract_already_exists",
            detail="A contract already exists for this proposal",
        )
    if latest.status != campaigns.SUBMITTED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_proposal_not_submitted",
            detail="Only a submitted proposal can be accepted",
        )

    # Accepting is ANSWERING, so the live version has to be the other side's.
    # The caller here is the business, so it has to be the creator's. Without
    # this the buyer can accept its own direct order, or its own counter on a
    # brief: that marks the chain accepted and writes a contract the creator
    # never agreed to, and the creator's decline then fails with
    # order_not_open (campaigns/orders.py) — they cannot even turn it down.
    # campaigns/orders.py::_require_business_offer is this same rule facing
    # the other way, and order_own_counter is its refusal for the creator.
    if not allow_business_offer and latest.author_role != campaigns.AUTHOR_INFLUENCER:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_own_offer",
            detail="You cannot accept your own offer. The other party has to accept it.",
        )

    # The window the order was placed under. Only a direct order carries an
    # expires_at — NULL for anything born of a brief, deliberately — and a
    # counter INHERITS it rather than restarting the clock, so a negotiated
    # order can lapse mid-chain and still be sitting here as `submitted`:
    # expire_stale_orders is admin-triggered and may not have run.
    #
    # order_expired rather than a contract-prefixed code of its own. It is the
    # same rule on the same column as campaigns/orders.py, and this refusal can
    # only ever fire on a direct order, so "order" is the right noun on both
    # surfaces — the same reasoning that has campaign_not_yours shared above.
    if latest.expires_at is not None and latest.expires_at <= models.utcnow():
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="order_expired",
            detail="This order has expired.",
        )

    business = db.query(User).filter(User.id == business_user_id).first()
    influencer = db.query(User).filter(User.id == latest.influencer_user_id).first()
    language = _language_for(business.country_code)

    # BEFORE THE CHAIN IS MARKED ACCEPTED, with every other guard above. The
    # ordering is the rule, not a detail: marking the proposal accepted is what
    # makes the creator's decline fail with order_not_open, so a refusal that
    # happened after it would take the creator's way out with it. Every guard
    # in this function is written to leave the negotiation exactly as it found
    # it, and this one is no different.
    business_party, influencer_party = _party_snapshots(db, business.id, influencer.id)

    # Accepting the proposal is what triggers contract generation.
    latest.status = campaigns.PROPOSAL_ACCEPTED

    body = _build_body(
        language,
        campaign,
        latest,
        business,
        influencer,
        business_party=business_party,
        influencer_party=influencer_party,
    )
    contract = models.Contract(
        campaign_id=campaign.id,
        proposal_id=latest.id,
        business_user_id=business.id,
        influencer_user_id=influencer.id,
        language=language,
        body=body,
        # The snapshot, stored beside the rendered text rather than only inside
        # it. The body is the document a person reads; these two are the same
        # facts in a shape an admin console, an export or a dispute can read
        # field by field without parsing prose back out of a contract.
        business_party=business_party,
        influencer_party=influencer_party,
        body_sha256=_body_hash(body),
        legal_version=LEGAL_EFFECTIVE_DATE,
        rate_amount=latest.rate_amount,
        rate_currency=latest.rate_currency,
        timeline_days=latest.timeline_days,
        deliverables=campaign.deliverables,
        status=models.PENDING,
    )
    db.add(contract)
    db.flush()
    db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=business_user_id, event="generated"))
    notify(db, influencer.id, "contract_ready", f"A contract is ready to sign for {campaign.title}",
           link=f"/contracts/{contract.id}", params={"key": "contract_ready", "campaign": campaign.title})
    db.commit()
    db.refresh(contract)
    return _out(contract)


def get_contract(db: Session, contract_id: str, user_id: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_not_found",
            detail="Contract not found",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    out = _out(contract)
    out["body"] = contract.body
    return out


def sign_contract(db: Session, contract_id: str, user_id: str, signature: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_not_found",
            detail="Contract not found",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    # Refused HERE, and not only in contracts/cancellation.py. A signature
    # completes the pair, the pair flips the status to SIGNED, and SIGNED is
    # the only thing payments.assert_fundable asks about before an escrow is
    # funded. So without this guard a contract cancelled after one party had
    # signed is brought back by the other party's signature and becomes
    # collectable in real money — an ended deal, funded, with a
    # contract_events trail saying it was called off.
    if contract.status == models.CANCELLED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_sign_cancelled",
            detail=CANCELLED_SIGN_DETAIL,
        )
    if contract.status == models.SIGNED:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            code="contract_signed_immutable",
            detail="Contract is fully signed and immutable",
        )

    now = models.utcnow()
    if user_id == contract.business_user_id:
        if contract.business_signed_at is not None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                # One code for both sides. It is the same rule — you sign once —
                # and which half of the contract the caller is on is not
                # something the sentence says or needs to.
                code="contract_you_already_signed",
                detail="You have already signed",
            )
        contract.business_signature = signature
        contract.business_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_business"))
    else:
        if contract.influencer_signed_at is not None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                # One code for both sides. It is the same rule — you sign once —
                # and which half of the contract the caller is on is not
                # something the sentence says or needs to.
                code="contract_you_already_signed",
                detail="You have already signed",
            )
        contract.influencer_signature = signature
        contract.influencer_signed_at = now
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="signed_influencer"))

    if contract.business_signed_at is not None and contract.influencer_signed_at is not None:
        contract.status = models.SIGNED
        db.add(models.ContractEvent(contract_id=contract.id, actor_user_id=user_id, event="fully_signed"))
        notify(db, contract.business_user_id, "contract_signed", "Your contract is fully signed",
               link=f"/contracts/{contract.id}", params={"key": "contract_signed"})
        notify(db, contract.influencer_user_id, "contract_signed", "Your contract is fully signed",
               link=f"/contracts/{contract.id}", params={"key": "contract_signed"})

    db.commit()
    db.refresh(contract)
    return _out(contract)


def get_contract_by_proposal(db: Session, proposal_id: str, user_id: str) -> dict:
    contract = db.query(models.Contract).filter(models.Contract.proposal_id == proposal_id).first()
    if contract is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="contract_none_for_proposal",
            detail="No contract for this proposal",
        )
    if user_id not in (contract.business_user_id, contract.influencer_user_id):
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            code="contract_not_a_party",
            detail="Not a party to this contract",
        )
    return _out(contract)


def list_my_contracts(db: Session, user_id: str) -> list[dict]:
    """Every contract the caller is a party to, newest first, each carrying the
    campaign it is for and the OTHER party by name.

    A card that shows only a rate and a timeline makes somebody open each
    contract to remember which job it was. So the list resolves, in batch, the
    campaign title and the counterparty the same way every other list names a
    person: a creator by display name and photo (core.identity), a business by
    its company name and no photo, and null rather than a phone number when the
    other side has written no profile yet.

    THE COUNTERPARTY IS WHICHEVER PARTY THE CALLER IS NOT, derived per row
    rather than from the caller's role. A user has one role, so a business
    always reads creators here and a creator always reads businesses — but
    deriving it from the row means the two can never fall out of step.

    IT ALSO CARRIES THE ESCROW STATUS, because that is the only thing that
    says whether a contract is FINISHED. A contract's own status never becomes
    "completed" — it stops at signed — so a list that showed only that had no
    way to separate the three jobs somebody is still working on from the
    thirty they finished last quarter. Released or refunded is an ending;
    held or disputed is not; null means nobody has funded it yet. The web app
    splits Active from Completed on exactly that (web/src/lib/lifecycle.ts).

    STILL A LIVE JOIN, and that is now a known inconsistency rather than an
    oversight. The contract BODY names its parties from a snapshot taken at
    generation and a rename cannot touch it; this card resolves the name again
    on every read, so a renamed company shows its new name on an old
    contract's card while the document under it says the old one. Pointing the
    card at contracts.business_party/influencer_party is the fix and it is a
    change to this list's payload and to both clients, so it is deliberately
    not bundled into the same pass as the body.

    Batched, not per row: the titles are one query, the escrow statuses one,
    the creator identities two (core.identity), the company names one. A page
    of contracts is a handful of campaigns and a handful of counterparties,
    and this keeps it that way however long the list grows.
    """
    rows = (
        db.query(models.Contract)
        .filter(or_(models.Contract.business_user_id == user_id, models.Contract.influencer_user_id == user_id))
        .order_by(models.Contract.created_at.desc())
        .all()
    )
    if not rows:
        return []

    campaign_titles = dict(
        db.query(campaigns.Campaign.id, campaigns.Campaign.title)
        .filter(campaigns.Campaign.id.in_({c.campaign_id for c in rows}))
        .all()
    )
    # escrows.contract_id is UNIQUE, so this is at most one row per contract
    # and the dict cannot lose one.
    escrow_statuses = dict(
        db.query(payments.Escrow.contract_id, payments.Escrow.status)
        .filter(payments.Escrow.contract_id.in_({c.id for c in rows}))
        .all()
    )
    # Split the counterparties by which kind of name they need. When the caller
    # is the business the other party is a creator, with an identity; when the
    # caller is the creator it is a business, with a company name and no avatar.
    creator_ids = {c.influencer_user_id for c in rows if c.business_user_id == user_id}
    business_ids = {c.business_user_id for c in rows if c.business_user_id != user_id}
    identities = creator_identities(db, creator_ids)
    company_names = (
        dict(
            db.query(BusinessProfile.user_id, BusinessProfile.company_name)
            .filter(BusinessProfile.user_id.in_(business_ids))
            .all()
        )
        if business_ids
        else {}
    )

    result = []
    for c in rows:
        item = _out(c)
        item["campaign_title"] = campaign_titles.get(c.campaign_id)
        item["created_at"] = c.created_at
        # None when the contract has never been funded, which is a live state
        # and not an ending — the brand simply has not paid in yet.
        item["escrow_status"] = escrow_statuses.get(c.id)
        if c.business_user_id == user_id:
            identity = identities.get(c.influencer_user_id) or {}
            item["counterparty_name"] = identity.get("display_name")
            item["counterparty_avatar_url"] = identity.get("avatar_url")
        else:
            # A business has a company name and no avatar in this system.
            item["counterparty_name"] = company_names.get(c.business_user_id)
            item["counterparty_avatar_url"] = None
        result.append(item)
    return result
