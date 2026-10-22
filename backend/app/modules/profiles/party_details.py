"""Capture of the party details a contract prints, for both sides of the market.

WHAT A PARTY BLOCK IS. The self declared answer to "who is signing this": a
legal name, a country, an address, and whatever a particular kind of entity has
to state beyond those. It is stored on the profile as the user's current
details, and snapshotted onto a contract at generation
(contracts.business_party, contracts.influencer_party) so that a later profile
edit cannot restate a document somebody has already signed. The columns carry
the full argument; claude/kolabo-contract-parties-spec.md sections 3, 4 and 8
are the specification.

NOTHING IN HERE IS VERIFIED, AND THAT IS NOT A GAP TO BE CLOSED LATER BY THIS
MODULE. Kolabo collects no personal identity document (decided 3 October 2026)
and checks none of these fields against any register. The platform records what
each party states about itself, exactly as a paper contract does. So this file
validates SHAPE and COMPLETENESS and never truth: a registration number that
refers to no company passes, and must, because the alternative is pretending to
a brand that somebody looked it up.

A MODULE OF ITS OWN rather than four more functions in service.py, the same
split this package already makes for bio_ai, enrichment and oauth_service, and
that contracts makes for cancellation. One bounded rule about one column, with
a per-type field list that wants reading whole.

WHICH PROFILE A BLOCK LANDS ON is decided by the caller's role, and the two
columns are deliberately identical, so an agency creator who is a registered
company fills in the same form a buyer does.
"""
from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import User
# MODELS ONLY, and the import direction is worth a line. contracts/service.py
# already reads profiles.models.BusinessProfile, so this module reaching for
# contracts.service would close a circle; contracts.models imports nothing but
# Base and sqlalchemy, so this one cannot. Only the immutability rule below
# needs it, and all it asks is whether a row exists.
from app.modules.contracts import models as contracts_models
from app.modules.profiles import models, schemas

# THE ONE ROLE ON THE SELLING SIDE OF THIS MARKET. A user whose role is this
# keeps their party details on influencer_profiles; EVERYBODY ELSE IS A BUYER
# and keeps them on business_profiles.
#
# Restated here rather than imported, which is the same choice
# campaigns.service.AUTHOR_EXCLUDED_ROLE and auth.referrals.CREATOR_ROLES
# already made, and for the same reason: the rule is "is this the creator
# side", it is one string, and importing a constant out of campaigns or auth
# to get at it would couple this module to a package it has no other business
# with.
#
# WRITTEN AS "EVERYTHING ELSE IS A BUYER" ON PURPOSE. The day an agency or an
# ngo role is introduced, it is a buyer here without anybody remembering to add
# it to a whitelist, which is the failure mode campaigns/service.py calls out
# in the comment above its own copy.
CREATOR_ROLE = "influencer"

# The four fields EVERY party block carries, whatever its type, plus the label
# derived from one of them. Named so the reader of a stored block can see at a
# glance which keys are always there.
COMMON_FIELDS = ("party_type", "display_label", "country", "address", "legal_name")

# WHAT EACH TYPE HAS TO STATE BEYOND THE COMMON FIELDS. A block missing one of
# its own type's fields is refused with party_details_invalid; a field that
# belongs to another type is not stored at all, so an association block carries
# no empty legal_form for a renderer to wonder about.
#
# READ THE SOLE_TRADER ROW FIRST, because an empty tuple there is the whole
# product decision. Businesses on this platform are explicitly NOT limited to
# registered ones, and a natural person contracting under their own name states
# a name, an address and a country and nothing else. That is not a reduced
# version of the company form, it is the complete form for that kind of party,
# and any copy or layout that makes it read as the lesser option is a defect.
#
# tax_identifier IS REQUIRED OF A registered_company AND OPTIONAL FOR A
# sole_trader, which follows the spec's table exactly. It is the one entry here
# worth revisiting during pilot recruitment: a registered company with no tax
# identifier at all is rare but not impossible, and the day a real buyer is one,
# relaxing this is moving a single string from the required tuple to the
# optional one. Until then a company that has an IFU should state it, because
# the whole point of the block is that a contract can name the entity properly.
#
# AN ASSOCIATION IS ASKED FOR NO TAX IDENTIFIER, and that is not an oversight
# either: a non profit in the launch markets frequently has none, and a field
# most of them would have to leave blank is a field that teaches everybody to
# leave fields blank.
REQUIRED_BY_TYPE = {
    models.REGISTERED_COMPANY: (
        "legal_form",
        "registration_number",
        "tax_identifier",
        "representative_name",
        "representative_capacity",
    ),
    models.SOLE_TRADER: (),
    models.ASSOCIATION: (
        "registration_number",
        "representative_name",
        "representative_capacity",
    ),
}

# Stored when present, dropped when absent, never refused.
OPTIONAL_BY_TYPE = {
    models.REGISTERED_COMPANY: (),
    models.SOLE_TRADER: ("tax_identifier",),
    models.ASSOCIATION: (),
}


def _require_user(db: Session, user_id: str) -> User:
    """The caller's own row, which is also what says which side they are on.

    Loaded rather than assumed because `role` is the only thing that decides
    which of the two profile tables this block belongs on. auth's error code
    rather than a profiles one, exactly as service._require_user does it: it is
    the same rule, no such user, and a code names the rule rather than the
    module it fired in.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            code="auth_user_not_found",
            detail="User not found",
        )
    return user


def _one_line(value: str) -> str:
    """Whitespace collapsed to single spaces, for a value that is one line.

    A legal name and a label are single line values, and they arrive pasted
    out of a registration certificate as often as they are typed, which is how
    "SARL   KOLABO\\n" turns up. Collapsing is not cosmetic: display_label is
    derived from legal_name and is printed on a contract, so a stray newline in
    it breaks the rendered document rather than merely looking untidy.

    NOT USED ON `address`, deliberately. An address is genuinely multi line and
    flattening one would lose the only structure it has.
    """
    return " ".join(value.split())


def _clean_optional(value: str | None) -> str | None:
    """A trimmed value, or None when there is nothing left of it.

    An empty string and a missing key have to mean the same thing here, because
    every form in both clients sends every input it renders, so an untouched
    optional field arrives as "" rather than as an omission. Storing that ""
    would put a key on the block that says "this party stated an empty tax
    identifier", which is not a thing anybody stated.
    """
    if value is None:
        return None
    cleaned = _one_line(value)
    return cleaned or None


def derive_display_label(legal_name: str) -> str:
    """What a contract and a contract card print as this party's name.

    DERIVED, NEVER ACCEPTED FROM A CLIENT, which is why it is a function here
    and not a field on PartyDetailsIn. Two reasons, and the second is the one
    that matters. A label a client could set is a label that can disagree with
    the legal name directly beneath it on the same document, and "Kolabo"
    printed over "SARL UNRELATED HOLDINGS" is worse than either alone. And
    storing it at all, rather than computing it on every read, means the
    renderer and the list view have ONE field to read without branching on
    party_type to find a name.

    It is legal_name for all three types today, and the indirection still earns
    its place: it is the single seam where that stops being true, for instance
    if an entity that trades under a different name is ever allowed to print
    both.
    """
    return _one_line(legal_name)


def _invalid(detail: str, values: dict | None = None) -> AppError:
    """One refusal for every content rule on this payload.

    ONE CODE RATHER THAN SIX, and that is a deliberate trade. Both clients
    render a sentence per error code (web/src/lib/errorMessages.ts and its
    mobile twin, with a CI check that every code has both languages), and a
    per-field code would mean six French sentences and six English ones for
    what is, from the user's side, one message: this form is not complete for
    the kind of party you chose. The fields that are missing travel in `values`
    so the sentence can name them, which is how price_below_floor carries its
    floor and deliverable_not_on_platform its platform.

    The field names in `values` are MACHINE values and stay untranslated, for
    the reason profile_doc_type_unknown gives: a French rendering of them would
    be a list of names no endpoint accepts.
    """
    return AppError(
        status.HTTP_400_BAD_REQUEST,
        code="party_details_invalid",
        detail=detail,
        values=values,
    )


def _validated_block(payload: schemas.PartyDetailsIn) -> dict:
    """The block as it will be stored: checked, normalised, type-trimmed.

    The ORDER of the checks is the order a form is filled. party_type first,
    because it decides what the rest of the payload even means, then the fields
    everybody states, then the ones this type adds.
    """
    party_type = _one_line(payload.party_type)
    if party_type not in models.PARTY_TYPES:
        raise _invalid(
            "Choose what kind of party you are before filling in the rest.",
            {"types": ", ".join(models.PARTY_TYPES)},
        )

    # ISO 3166-1 alpha-2, uppercased here rather than refused in the wrong
    # case: "bj" is a country code somebody typed in lower case, not an error
    # worth a round trip. Only the two-letters-and-letters shape is enforced.
    #
    # NOT CHECKED AGAINST COUNTRY_CONFIG, and that is on purpose. That table is
    # the markets Kolabo SELLS in; this field is the country a party contracts
    # FROM, and a French agency buying a Beninese creator's work is an ordinary
    # transaction rather than a data error. The list of every country on earth
    # is the client's to render.
    country = _one_line(payload.country).upper()
    if len(country) != 2 or not country.isalpha():
        raise _invalid("Country must be a two letter country code.")

    # min_length on the schema stops a missing value; it does not stop a value
    # that is nothing but spaces, which is what an input somebody tabbed
    # through sends.
    address = payload.address.strip()
    if not address:
        raise _invalid("Enter the address that should appear on your contracts.")

    legal_name = _one_line(payload.legal_name)
    if not legal_name:
        raise _invalid("Enter the name that should appear on your contracts.")

    block = {
        "party_type": party_type,
        # Derived, and written in the same breath as the name it comes from so
        # the two can never drift.
        "display_label": derive_display_label(legal_name),
        "country": country,
        "address": address,
        "legal_name": legal_name,
    }

    missing = []
    for field in REQUIRED_BY_TYPE[party_type]:
        value = _clean_optional(getattr(payload, field))
        if value is None:
            missing.append(field)
        else:
            block[field] = value
    if missing:
        raise _invalid(
            "Some details are missing for the kind of party you chose.",
            {"fields": ", ".join(missing)},
        )

    for field in OPTIONAL_BY_TYPE[party_type]:
        value = _clean_optional(getattr(payload, field))
        if value is not None:
            block[field] = value

    # EVERYTHING ELSE THE CLIENT SENT IS DROPPED HERE, by simply not being
    # copied: a legal_form on a sole_trader block, a tax_identifier on an
    # association's, a display_label the client decided to send anyway. The
    # stored block holds the keys that belong to its type and no others, so a
    # renderer reading it can trust that a key's presence means the party
    # stated it.
    return block


def _stored_block(profile) -> dict | None:
    """The block on a profile row, or None.

    `or None` rather than returning the column raw: an empty dict is a value
    this column should never hold, and if one ever gets in there, reading it as
    "nothing stated" is right and reading it as a block with no fields is a
    renderer printing a contract with a blank party on it.
    """
    if profile is None:
        return None
    return profile.party_details or None


def _has_contract(db: Session, user_id: str, *, creator_side: bool) -> bool:
    """Whether any contract has ever been generated with this user as a party.

    ANY ROW AT ALL, including cancelled and void ones. A cancelled contract was
    a real document that two people read, and its party block says what kind of
    entity signed it, so the fact that the deal ended does not make the
    statement re-writable.

    Queried for the id alone and stopped at the first row: this runs on every
    party details save and the answer is a yes or a no, never a count.
    """
    column = (
        contracts_models.Contract.influencer_user_id
        if creator_side
        else contracts_models.Contract.business_user_id
    )
    return db.query(contracts_models.Contract.id).filter(column == user_id).first() is not None


def _profile_for_read(db: Session, user: User):
    """The row holding this user's party details, or None if there is not one."""
    if user.role == CREATOR_ROLE:
        return (
            db.query(models.InfluencerProfile)
            .filter(models.InfluencerProfile.user_id == user.id)
            .first()
        )
    return (
        db.query(models.BusinessProfile)
        .filter(models.BusinessProfile.user_id == user.id)
        .first()
    )


def get_party_details(db: Session, user_id: str) -> dict | None:
    """What this user has stated about itself, or None if it has stated nothing.

    NULL RATHER THAN A 404 when there is no profile row and when there is one
    with nothing in the column. Both mean the same thing to the only caller
    there is, a form deciding whether to render empty or prefilled, and making
    it tell a missing profile apart from an unfilled column would buy it
    nothing but a second error branch.
    """
    user = _require_user(db, user_id)
    return _stored_block(_profile_for_read(db, user))


def set_party_details(db: Session, user_id: str, payload: schemas.PartyDetailsIn) -> dict:
    """Store this user's party details and answer them back.

    A WHOLE REPLACEMENT, NOT A MERGE, which is the one place this parts company
    with upsert_influencer_profile's exclude_unset contract. That contract
    exists because a client form that does not know about a field must not wipe
    it. Here the required set CHANGES WITH party_type, so merging a
    sole_trader's three fields over a registered_company's eight leaves a block
    that is valid as neither: a company with no registration number, or a sole
    trader carrying a representative capacity from a shape it no longer has.
    One screen owns this block and sends all of it.

    The creator side CREATES its profile row when there is none, exactly as
    upsert_influencer_profile and _apply_enrichment do, because an
    influencer_profiles row needs nothing invented to exist. The business side
    cannot: business_profiles.company_name is NOT NULL, so conjuring a row
    means writing a company name the buyer never typed into the field that
    every creator sees as the counterparty name on their contract card. It is
    refused with the existing profile_not_found instead, which both clients
    already have a sentence for, and the buyer saves the company profile first.
    """
    user = _require_user(db, user_id)
    block = _validated_block(payload)
    creator_side = user.role == CREATOR_ROLE

    profile = _profile_for_read(db, user)
    if profile is None:
        if not creator_side:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                code="profile_not_found",
                detail="Save your company profile first, then say who signs your contracts.",
            )
        profile = models.InfluencerProfile(user_id=user.id)
        db.add(profile)

    # PARTY TYPE IS FROZEN ONCE A CONTRACT HAS BEEN GENERATED. Everything else
    # in the block stays editable forever: an entity moves offices, changes its
    # representative, finally gets its tax identifier, and the next contract
    # should say so while the ones already signed keep their snapshot.
    #
    # The type is different in kind. Changing it rewrites what sort of thing
    # signed the earlier documents, from a registered company to a natural
    # person or the other way round, and the party blocks frozen on those
    # contracts would then disagree with the profile they came from in the one
    # field that decides how every other field is read. Somebody who
    # incorporates genuinely has a new counterparty and support has to be the
    # one to sort it out, which is the sentence below.
    #
    # Only a CHANGE is refused. Re-submitting the same type with a new address,
    # which is what a form that PUTs every field it renders does on every save,
    # has not changed anything and passes.
    stored = _stored_block(profile)
    if (
        stored is not None
        and stored.get("party_type") != block["party_type"]
        and _has_contract(db, user.id, creator_side=creator_side)
    ):
        raise AppError(
            status.HTTP_409_CONFLICT,
            code="party_type_immutable",
            detail=(
                "A contract has already been generated for you, so the kind of party "
                "you are cannot be changed here. Contact support."
            ),
        )

    profile.party_details = block
    db.commit()
    db.refresh(profile)
    return _stored_block(profile)
