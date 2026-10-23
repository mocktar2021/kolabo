"""The content licence the brand states, and what each option has to say.

WHAT A LICENCE BLOCK IS. The brand's answer to Article 10 of the collaboration
model counsel approved (claude/kolabo-contrat-collaboration-modele-fr.md): how
the Entreprise may use the Travaux once the Createur has made them. The model
offers three options and leaves "Option retenue : [ 1 / 2 / 3 ]" to be filled
in per contract, and the founder decided the brand states which one BEFORE the
contract exists, with all three kept on offer.

    Option 1  Diffusion par le Createur seul. The creator publishes on their
              own accounts. The brand gets no redistribution right and may
              only share or relay the original post.
    Option 2  Licence de rediffusion. The brand may reproduce and distribute
              the content on its own channels, paid advertising included, for
              a stated duration, on stated territories, on stated media.
    Option 3  Cession des droits patrimoniaux. The creator assigns the
              economic rights for a stated duration and territories. A
              separate consideration may be agreed.

WHY IT IS CAPTURED BEFORE THE CONTRACT AND NOT AT SIGNATURE. A creator prices
option 2 differently from option 1: being redistributable in paid advertising
for a year is not the same job as posting once on your own feed. So the licence
has to be visible to the creator while they still have a decision to make,
which means it travels on the brief, on the invitation and on the direct order,
and campaigns.service puts it on all three. A choice made after acceptance
would be a term introduced after the price was agreed.

WHERE A BLOCK LIVES. campaigns.licence_terms for a brief, because that is where
a brand states the rest of its terms. proposals.licence_terms for a direct
order, because there the brand's offer IS the proposal row. contracts
.licence_terms for the snapshot taken at generation, which is never rewritten.
The migration d3a6b9e24c71 carries that argument at length.

NOTHING READS A BLOCK BACK THROUGH THIS MODULE, and that is deliberate. The
only function here is the one that decides whether a STATED licence is
complete; the three places that read a stored one (the two campaigns
serialisers and contracts._licence_snapshot) take the column as it is. A
reader helper would be a second opinion about what an empty block means, and
there is only one: validated_block never returns one, so the columns hold a
complete block or null.

A MODULE OF ITS OWN rather than four more functions in service.py, the same
split this package already makes for negotiated and that profiles makes for
party_details: one bounded rule about one column, with a per-option field list
that wants reading whole. Deliberately pure, like negotiated.py: nothing here
touches the database or builds a row, which is what keeps the import running
one way (service -> licence) instead of in a circle, and what lets campaigns
.cart hold twenty basket lines to this rule before writing any of them.

NOTHING HERE IS A LEGAL OPINION. This checks that a stated licence is complete
on its own terms. Whether a particular wording achieves what the parties want
in a particular market is a question for counsel, and question 6 of the annex
to the model already puts it to her.
"""
from fastapi import status

from app.core.errors import AppError

# The three options, as the approved model numbers them. STRINGS AND NOT
# INTEGERS, because the model prints "Option retenue : [ 1 / 2 / 3 ]" and the
# value is a label that gets quoted into a document, never a quantity anybody
# does arithmetic on. The same reasoning contracts.legal_version is stored as a
# string: it is compared for equality against a published document and nothing
# else.
OPTION_CREATOR_ONLY = "1"
OPTION_REDISTRIBUTION = "2"
OPTION_ASSIGNMENT = "3"

# A closed set, in the model's own order, so the refusal below can name all of
# it. Open-ended would be wrong here in a way it is not wrong for a platform or
# a currency: these three ARE Article 10, and a fourth option is a change to a
# document counsel approved rather than a configuration value.
OPTIONS = (OPTION_CREATOR_ONLY, OPTION_REDISTRIBUTION, OPTION_ASSIGNMENT)

# Everything a block may carry besides the option itself, named as a group
# because one rule covers all of them: they are free text the parties state,
# and a field that does not belong to the stated option is not stored at all.
SUB_FIELDS = (
    "licence_duration",
    "licence_territories",
    "licence_media",
    "licence_consideration",
)

# WHAT EACH OPTION HAS TO STATE BEYOND THE CHOICE. Taken field for field from
# Article 10's table rather than from anybody's idea of what a licence needs.
#
# READ THE OPTION 1 ROW FIRST, because an empty tuple there is the point of
# having three options at all. "Le Createur publie les contenus sur ses propres
# comptes. L'Entreprise ne dispose d'aucun droit de rediffusion." There is
# nothing further to state: no duration, because no right is granted that could
# run out; no territories, because nothing is being distributed by the brand.
# That is the COMPLETE form of option 1 and not a reduced version of the other
# two, and any copy or layout that makes it read as the lesser choice is a
# defect. It is also the option a great many pilot deals will be.
#
# OPTION 2 REQUIRES ALL THREE, and the duration is the one worth arguing for. A
# rediffusion licence with no stated duration is a licence of unbounded
# duration: the brand may run the creator's face in paid advertising for as long
# as it likes, which is not what either side agreed and is the single most
# expensive blank on the page. Territories and media are required for the same
# reason one step down: "on our channels" is not a scope, and the model asks for
# "les supports suivants" explicitly.
#
# OPTION 3 REQUIRES TWO. The model's own wording for an assignment is "pour la
# duree et les territoires precises", and it says of the money only that a
# separate consideration "peut etre convenue" - so licence_consideration is
# optional here and nowhere else. A field most parties would leave blank is a
# field that teaches everybody to leave fields blank, which is the reasoning
# party_details.py applies to an association's tax identifier.
REQUIRED_BY_OPTION = {
    OPTION_CREATOR_ONLY: (),
    OPTION_REDISTRIBUTION: (
        "licence_duration",
        "licence_territories",
        "licence_media",
    ),
    OPTION_ASSIGNMENT: (
        "licence_duration",
        "licence_territories",
    ),
}

# Stored when present, dropped when absent, never refused.
#
# licence_consideration belongs to option 3 ALONE. On option 2 the price of the
# collaboration is the price of the licence, and a second consideration there
# would be a payment this platform knows nothing about sitting inside a document
# whose whole financial section is escrowed. On option 1 nothing is licensed at
# all. The model only mentions a separate consideration under option 3, so that
# is the only option that carries it.
OPTIONAL_BY_OPTION = {
    OPTION_CREATOR_ONLY: (),
    OPTION_REDISTRIBUTION: (),
    OPTION_ASSIGNMENT: ("licence_consideration",),
}

# Said in full because it has to teach as well as refuse. No dashes in either
# sentence: both go out to a reader.
UNKNOWN_OPTION_DETAIL = (
    "Say how the brand may use the content before sending this. Option 1 is "
    "the creator posting on their own accounts, option 2 is a licence for the "
    "brand to redistribute it, option 3 assigns the rights."
)
INCOMPLETE_DETAIL = (
    "Some licence details are missing for the option you chose. A licence has "
    "to say how long it lasts, where it applies and on which media, or it is "
    "not a licence anybody can rely on."
)


def _clean(value: str | None) -> str | None:
    """A stated value with its edges stripped, or None when nothing is left.

    STRIPPED AND NOTHING ELSE. These strings are printed into a contract
    verbatim, so a duration stated in French stays French and a territory list
    keeps whatever punctuation the party used: nothing here lower-cases,
    title-cases, reorders or maps a value onto a vocabulary. party_details.py
    collapses internal whitespace on a legal name because a stray newline there
    breaks the rendered party block; that is a decision about one known
    single-line field, and it is deliberately not generalised to free text whose
    shape the parties choose.

    An empty string and a missing key have to mean the same thing, because
    every form in both clients sends every input it renders: an untouched
    optional field arrives as "" rather than as an omission, and storing that ""
    would put a key on the block saying this brand stated an empty territory.
    """
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _invalid(detail: str, values: dict | None = None) -> AppError:
    """One refusal for every content rule on this block.

    ONE CODE RATHER THAN FIVE, the same trade party_details_invalid makes and
    for the same reason. Both clients render a sentence per error code, with a
    CI check that every code has a French and an English one, and a code per
    field would be ten more sentences to keep in step in two languages for what
    is, from the user's side, one message: this licence is not complete for the
    option you chose. What is missing travels in `values` so the sentence can
    name it, which is how price_below_floor carries its floor.

    The field names in `values` are MACHINE values and stay untranslated, for
    the reason profile_doc_type_unknown gives: a French rendering of them would
    be a list of names no endpoint accepts.
    """
    return AppError(
        status.HTTP_400_BAD_REQUEST,
        code="licence_terms_invalid",
        detail=detail,
        values=values,
    )


def validated_block(payload) -> dict | None:
    """The licence block as it will be stored: checked, stripped, option-trimmed.

    Takes the licence_terms object off any request that carries one (a brief, a
    patch, a direct order, a basket line) and hands back the dict that goes in
    the column, or None when the brand has stated no licence at all.

    NONE IS A LEGITIMATE ANSWER HERE, and the gate is somewhere else. Capture is
    optional because the columns are nullable and because every brief and order
    written before this existed has nothing in them; what is NOT optional is
    generating a contract from nothing, which contracts/service.py refuses with
    contract_licence_terms_missing. The cost of that split is real and is worth
    naming: on a direct order the refusal lands on the CREATOR, who is the one
    accepting, for something only the brand can fix. Requiring a licence on
    every order instead would move the refusal to the brand where it belongs,
    and it is a change to what both clients must send rather than a line here,
    so it is a product decision and not this module's to take quietly. The same
    shape of argument _party_snapshots makes about its own backstop.

    SUB-FIELDS WITHOUT AN OPTION ARE REFUSED, not quietly dropped. A payload
    carrying a duration and no option is a form half filled in or a client that
    forgot a field, and storing the duration against no option would record a
    licence nobody can read while silently losing the only part that decides
    what the other fields mean. A payload carrying nothing at all is a brand
    that has not got to this yet, which is a different thing and is None.

    The ORDER of the checks is the order the form is filled: the option first,
    because it decides what the rest of the payload even means, then the fields
    that option requires, then the ones it merely allows.
    """
    if payload is None:
        return None

    option = _clean(payload.licence_option)
    stated = [field for field in SUB_FIELDS if _clean(getattr(payload, field, None)) is not None]

    if option is None:
        if not stated:
            return None
        raise _invalid(UNKNOWN_OPTION_DETAIL, {"options": ", ".join(OPTIONS)})
    if option not in OPTIONS:
        raise _invalid(UNKNOWN_OPTION_DETAIL, {"options": ", ".join(OPTIONS)})

    block = {"licence_option": option}

    missing = []
    for field in REQUIRED_BY_OPTION[option]:
        value = _clean(getattr(payload, field, None))
        if value is None:
            missing.append(field)
        else:
            block[field] = value
    if missing:
        raise _invalid(INCOMPLETE_DETAIL, {"fields": ", ".join(missing)})

    for field in OPTIONAL_BY_OPTION[option]:
        value = _clean(getattr(payload, field, None))
        if value is not None:
            block[field] = value

    # EVERYTHING ELSE THE CLIENT SENT IS DROPPED HERE, by simply not being
    # copied: a duration on an option 1 block, a consideration on an option 2
    # one. A stored block holds the keys that belong to its option and no
    # others, so a reader can trust that a key's presence means the brand
    # stated it. That matters more here than it does on a party block: a
    # consideration sitting on an option 2 licence would read, to a creator or
    # to counsel, as money agreed outside the escrow.
    return block
