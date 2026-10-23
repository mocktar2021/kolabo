"""Schemas for the contracts module."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignIn(BaseModel):
    signature: str = Field(min_length=1, max_length=120)


class ContractOut(BaseModel):
    id: str
    campaign_id: str
    proposal_id: str
    business_user_id: str
    influencer_user_id: str
    language: str
    status: str
    rate_amount: int
    rate_currency: str
    timeline_days: int
    business_signed: bool
    influencer_signed: bool
    fully_signed: bool


class ContractListItem(ContractOut):
    """A row of GET /contracts/mine: the contract, plus what a card needs to be
    read at a glance without opening it. All three of the added identity fields
    are nullable — the campaign could predate the title column, and the other
    party may have written no profile yet, in which case the row carries a null
    rather than a phone number or a bare user id."""
    campaign_title: str | None
    counterparty_name: str | None
    counterparty_avatar_url: str | None
    created_at: datetime
    # held / released / refunded / disputed, or null when nothing has been
    # funded against this contract yet. It is here because a contract's own
    # status stops at "signed" and never says whether the job is FINISHED —
    # only the money does. See list_my_contracts, and the Active/Completed
    # split in web/src/lib/lifecycle.ts that reads it.
    escrow_status: str | None = None


class ContractDetailOut(ContractOut):
    """The contract, its text, WHO THE TWO PARTIES SAID THEY WERE, and the
    licence it was generated under.

    THE BLOCKS ARE SNAPSHOTS, not a join. They are copied onto the contract at
    generation and never rewritten, so editing a profile or a brief afterwards
    does not change a contract that already exists. That is the same rule
    PaymentIntent applies to amounts, and for the same reason: a join would
    silently show one thing on a document that was signed saying another.

    TYPED AS PLAIN DICTS, DELIBERATELY. A party block's shape varies by
    party_type: a registered company states a legal form, a registration
    number and a representative, a sole trader states none of the three. A
    licence block's varies by option: option 1 states nothing beyond the
    choice, option 2 states a duration, territories and media. That
    variability is why the columns are JSON rather than a dozen mostly null
    ones, and a response model enumerating every field would have to be kept
    in step with the capture schema in a second place. Both clients already
    carry the typed shapes, and the snapshots are frozen, so nothing
    downstream can reshape them.

    THE LICENCE IS HERE BECAUSE THE BODY DOES NOT PRINT IT. The party blocks
    are rendered into the text as well as carried here; Article 10 is
    deliberately not rendered yet, because the approved model is French only
    and whether an English contract carries a courtesy translation is an open
    question for counsel. Until she answers, this field is the only way either
    client can show a party the licence they are signing under, which is also
    why it must not wait: the column is filled from the first contract that
    carries it, and the body can never be amended afterwards.

    NULLABLE, and the clients must treat null as "generated before these
    details were collected" rather than as "this party stated nothing" or as
    option 1. Every contract made before this work has nothing to backfill
    from beyond a UUID, which is the whole reason the capture exists.

    NOT HERE: body_sha256 and legal_version. They are written at generation
    and nothing on either client displays them yet. They belong in whatever
    screen eventually shows a party that the text they signed has not
    changed, and adding them to a payload before anything reads them is how a
    field acquires a consumer nobody designed for."""
    body: str
    business_party: dict[str, Any] | None = None
    influencer_party: dict[str, Any] | None = None
    licence_terms: dict[str, Any] | None = None
