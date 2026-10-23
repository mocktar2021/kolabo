"""Contract and signature models (Epic E).

A contract is generated from an accepted proposal, capturing a snapshot of the
agreed terms so later edits to the campaign or proposal do not change it. Once
both parties sign, the contract is immutable and payment can be unlocked.

THE SNAPSHOT NOW COVERS THE PARTIES THEMSELVES, not only the terms. Until
business_party and influencer_party arrived, the one thing a contract did NOT
freeze was who had signed it: the body carried two user ids, and every name
shown around the document was resolved live from a profile that its owner can
rename at any time. See the columns below and
claude/kolabo-contract-parties-spec.md.

AND IT COVERS THE CONTENT LICENCE. Article 10 of the approved model
(claude/kolabo-contrat-collaboration-modele-fr.md) is the clause the parties
have to choose between three options on, and until licence_terms below there
was nothing in this schema that recorded which one they chose.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


PENDING = "pending_signatures"
SIGNED = "signed"
VOID = "void"
# Called off by one of the two parties before it was fully signed and while no
# escrow existed against it (contracts.cancellation).
#
# Its own status rather than VOID, which has never been written by any code
# path and reads as "this document was never valid" — a statement about the
# paper. Cancelled is a statement about the deal: it was real, it was on the
# table, and somebody ended it before it bound anyone. The two want telling
# apart the first time a contract genuinely has to be voided for a defect.
#
# The row is kept, like every other ended thing here. A creator who signed and
# then watched the brand walk away has a record worth keeping, and the
# contract_events trail hangs off the row.
CANCELLED = "cancelled"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True, nullable=False)
    business_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    influencer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # WHO SIGNED THIS, AS THEY STATED IT, FROZEN AT GENERATION.
    #
    # One block per side, copied out of the signer's profile the moment the
    # contract is written, and never rewritten afterwards: not when a profile
    # is edited, not at signature, not at cancellation. Editing a profile
    # changes what the NEXT contract says and nothing whatever about one that
    # already exists.
    #
    # A COPY AND NOT A JOIN, which is the same decision PaymentIntent makes
    # about money and for the same reason its docstring gives: amounts are
    # copied off the contract "rather than read through a join at settlement"
    # because otherwise "a join would silently settle the new number against
    # the old payment". Identity has the identical failure. A join would
    # restate a contract signed in October in the name of a company that
    # reincorporated in March, and the signature beside it would then appear
    # to have been given by an entity that did not exist on the day.
    #
    # This is also why the two uuid columns above STAY and are not replaced by
    # these blocks. The uuid is the only stable identifier either side has, it
    # is what every other table joins on, and it is what an admin searches by;
    # the block is what the document says. Neither substitutes for the other.
    #
    # THE SHAPE, documented here rather than only at the schema that validates
    # it, because this column is the frozen copy and will be read by a renderer
    # long after whatever validated it has changed:
    #
    #   party_type      registered_company | sole_trader | association
    #   display_label   what to print as the party name, DERIVED server side
    #                   from legal_name at capture and never accepted from a
    #                   client. It exists so a renderer and a contract card
    #                   have one field to read without branching on the type.
    #   country         ISO 3166-1 alpha-2, the country the party contracts
    #                   from. Not restricted to the pilot markets: a buyer may
    #                   perfectly well be contracting from outside them.
    #   address         free text, one field, deliberately unstructured
    #   legal_name      the entity or the natural person
    #
    # then, by party_type: a registered_company adds legal_form,
    # registration_number, tax_identifier, representative_name and
    # representative_capacity; a sole_trader adds an optional tax_identifier;
    # an association adds registration_number, representative_name and
    # representative_capacity. Only the keys that belong to the stated type are
    # written, so an association block carries no empty legal_form for a
    # renderer to wonder about. profiles/party_details.py is where that is
    # enforced.
    #
    # NOTHING IN EITHER BLOCK HAS BEEN VERIFIED, AND NO READER MAY IMPLY IT
    # HAS. These are self declared contract content, exactly as they would be
    # on paper: the platform records what each party states about itself and
    # checks none of it. Kolabo collects no personal identity document (decided
    # 3 October 2026, and migration b1d7e3a05c92 is what emptied the store of
    # the ones it held), so there is nothing behind these fields that could
    # support a badge. A tick beside a registration number nobody has looked up
    # would be the single most expensive lie this product could tell a brand.
    #
    # Nullable because every contract generated before this existed has
    # nothing to backfill from beyond the two uuids already in its body, and
    # inventing a party block for a signed document is not something a
    # migration gets to do. Null means "generated before parties were
    # captured", never "the party stated nothing". New contracts always carry
    # both: contracts/service.py refuses to generate without them.
    business_party: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    influencer_party: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # HOW THE BRAND MAY USE THE CONTENT, AS THE PARTIES AGREED IT, FROZEN AT
    # GENERATION. Article 10 of the approved model, which offers three options
    # and leaves "Option retenue : [ 1 / 2 / 3 ]" to be filled in per contract.
    #
    #   licence_option         "1" | "2" | "3"
    #   licence_duration       free text, option 2 and 3 only
    #   licence_territories    free text, option 2 and 3 only
    #   licence_media          free text, option 2 only
    #   licence_consideration  free text, option 3 only, optional
    #
    # Only the keys belonging to the stated option are present, so an option 1
    # block carries no empty duration. campaigns/licence.py enforces that and
    # argues each option's required set from the model's own table.
    #
    # COPIED, NEVER JOINED, for the identical reason the two party blocks above
    # are copied. The brief a contract was generated from stays editable in
    # every respect this column does not lock, and the direct order's offer row
    # can be superseded by a later version; a join to either would silently
    # restate what a signed document permits. "The brand may redistribute this
    # for twelve months" is not a sentence anybody gets to add to a contract
    # after it was signed, and a join would add it retroactively to every
    # contract on the brief at once.
    #
    # WHERE IT IS COPIED FROM is the proposal's block if it has one, otherwise
    # the campaign's: an order states its licence on the brand's own offer, a
    # brief states it on the brief. contracts/service.py::_licence_snapshot is
    # that rule and the only place it is written down.
    #
    # NOT RENDERED INTO `body` YET, DELIBERATELY, which is the one asymmetry
    # with the party blocks. The approved model is French only, and whether an
    # English contract should carry a courtesy translation of Article 10 or
    # stay silent is an open question for counsel rather than one a renderer
    # settles by printing something. The data is here and frozen from the day
    # the first contract carried it, which is the part that cannot be bought
    # back later: the body is hashed at generation and never rehashed, so a
    # clause added when counsel answers is absent from every contract signed
    # before that day, while a column filled from the start can be printed,
    # exported or quoted whenever she does.
    #
    # Nullable because every contract generated before this existed has nothing
    # to backfill from. Null means "generated before licence terms were
    # captured" and must never be read as "no licence applies" or as option 1 —
    # those are statements the parties did not make. New contracts always carry
    # a block: contracts/service.py refuses to generate without one.
    licence_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # THE EVIDENCE THAT THE TEXT HAS NOT MOVED. sha256 of `body` as it stood at
    # generation, computed once and never recomputed.
    #
    # What signing records today is a free text string and a server timestamp.
    # Neither of them says anything about the DOCUMENT, so nothing in this
    # schema could answer the one question a dispute actually turns on: is this
    # the text they agreed to. A hash answers it in one comparison, from the
    # row itself, with no backup and no second system involved.
    #
    # NEVER REHASHED, which is the rule that makes it worth storing. A body
    # that is rehashed on read is a hash of whatever the body is now, which is
    # no evidence at all. In particular an annex attached later (spec section
    # 7) does NOT touch this value: it is a separate record with its own hash
    # and its own timestamps, and keeping the two trails independent is the
    # whole point.
    body_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    # WHICH PUBLISHED TERMS WERE IN FORCE when this contract was generated.
    #
    # There is no terms acceptance record anywhere in this backend: nothing
    # stores that a user agreed to anything, on any date. The effective date on
    # the published legal pages is the only version marker that exists, so it
    # is what gets copied here. It is a string rather than a Date because it is
    # a VERSION, not an event: it is compared for equality against a published
    # document, never sorted or arithmetic'd, and the day the versioning scheme
    # stops being a date this column keeps working.
    #
    # Null on every row generated before this column existed, and a reader must
    # say nothing rather than assume the current version applied to it.
    legal_version: Mapped[str | None] = mapped_column(String, nullable=True)
    rate_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_currency: Mapped[str] = mapped_column(String, nullable=False)
    timeline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    deliverables: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String, default=PENDING, nullable=False)
    business_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    business_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    influencer_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    influencer_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ContractEvent(Base):
    """Immutable audit trail of contract lifecycle events."""

    __tablename__ = "contract_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"), nullable=False, index=True)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
