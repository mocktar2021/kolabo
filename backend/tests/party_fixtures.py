"""What a fixture has to state before a contract can be generated.

WHY THIS FILE EXISTS. contracts.service.generate_from_proposal refuses to write
a contract unless BOTH sides have stated who they are contracting as, AND
somebody has stated how the brand may use the content. It reads
business_profiles.party_details and influencer_profiles.party_details, and a
missing profile row and a null column refuse identically
(contract_business_party_missing, contract_creator_party_missing); it then reads
the licence block off the proposal or the campaign and refuses with
contract_licence_terms_missing when neither states one. Four suites outside
test_contracts.py reach that code through the ordinary accept paths, and every
one of them seeds its users with no profile row at all and posts its briefs and
orders with no licence, which both gates read, correctly, as "nobody has stated
anything".

ONE MODULE RATHER THAN A LITERAL IN EVERY FIXTURE, because the shape of both
blocks is owned elsewhere and both are expected to move. A party block's
required set is per party_type; app/modules/profiles/party_details.py names
tax_identifier on a registered company as the one entry worth revisiting during
pilot recruitment, and profiles/models.py says a fourth party type costs no
migration at all. A licence block's required set is per option, and the wording
of Article 10 that decides it is with counsel now (question 6 of the annex to
claude/kolabo-contrat-collaboration-modele-fr.md). A block pasted into four
fixtures is four places that go stale together, and stale here does not surface
as a missing field. It surfaces as contract generation refusing, in suites that
are not about contracts at all.

WHAT THIS MODULE CANNOT DO FOR THE LICENCE, which is the one asymmetry between
the two blocks and is worth stating before somebody looks for the seeder that
is not here. A party block lands on a PROFILE, and a profile exists the moment
a fixture creates a user, so seed_party_details is callable from a user helper
and the four suites needed nothing else at all. A licence block lands on the
CAMPAIGN or on the ORDER, and neither exists when those helpers run: the brand
states its licence when it posts the brief or places the order, which is the
whole point of capturing it before a contract exists. So this file owns the
block and each of the four suites sends it from the single request helper it
already funnels every brief or order through. One line each, one copy of the
block, and no fixture pretending to write a row that is not there yet.

WHY NOT backend/conftest.py. That file holds what has to be autouse or shared
by every test file: the in-memory database default, the profile_owner override,
the admin account. Neither block is. Four suites need them, each one wants them
written inside the session its own user helper already has open, and a fixture
that fired for all seventy test files would be writing profile rows into suites
that assert on their absence (test_campaigns.py pins business_company_name as
null when the buyer has no business profile, and test_identity.py pins a
creator with no profile at all). So this is a module those four suites import,
not a fixture that fires whether or not it is wanted.

WHY NOT THROUGH THE API for the party blocks. PUT /profiles/{id}/party-details
would exercise the capture rules as well, which sounds stronger and is not:
none of these four suites mounts the profiles router, three of them mount no
router that could reach it, and adding one would make every fixture here depend
on a second module's validation to produce a brand and a creator. The column is
written directly, the same way these suites already write packages, escrows and
proposals. The licence is the other way round and for the same practical
reason: it is already on the request those suites make, so it goes through the
API and is validated on the way in. test_contracts.py owns the refusals and
test_profiles.py owns the party capture.

NOTHING IN HERE IS VERIFIED AND NO FIXTURE MAY IMPLY OTHERWISE. A party block is
self declared contract content, and profiles/party_details.py makes that point
at length; a licence is a statement the brand makes about what it wants, and
nothing checks that the wording achieves it. These are ordinary launch-market
names and ordinary French clause values only because a failure message quoting a
contract body with "x" in the legal name field is unreadable. Nothing has looked
up a registration number or a tax identifier here, and nothing has had a lawyer
read the duration, exactly as nothing does either in production.
"""
from app.modules.profiles import models as profiles
# The authoritative answer to "which of the two profile tables does this user's
# block live on". Imported rather than restated as a literal, because a fixture
# has to land the block on the same table contracts.service._party_snapshots
# will read it back from: a second copy of that string here would be a fixture
# that silently writes to the wrong side the day the selling role is renamed.
from app.modules.profiles.party_details import CREATOR_ROLE

# The two names these blocks contract under. Constants rather than inline
# strings so a suite that wants to assert on what a generated body prints can
# name the expected value instead of repeating the literal.
BUSINESS_LEGAL_NAME = "Maison Zinsou SARL"
CREATOR_LEGAL_NAME = "Kossi Amegan"

# HOW THE BRAND SAYS IT MAY USE THE CONTENT, which is the other thing contract
# generation refuses without.
#
# OPTION 2, THE REDISTRIBUTION LICENCE, and the choice is deliberate on two
# counts. It carries the LONGEST required set of the three — a duration,
# territories and media, where option 1 requires nothing beyond the choice —
# which makes a fixture built on it the one that notices when that set grows,
# the same reason the business party block below is a registered company. And
# the annex to the approved model calls it "le cas le plus frequent en pratique
# puisque l'entreprise veut rediffuser en publicite payante", so it is also the
# ordinary deal rather than an exotic one.
#
# THE SAME DICT SERVES AS THE REQUEST AND AS THE STORED BLOCK, which is not a
# coincidence and is worth relying on: campaigns.licence.validated_block strips
# the edges of each value and keeps the keys the stated option requires, so a
# block that is already complete and already trimmed comes back out of capture
# unchanged. A suite can therefore post this and then assert the column equals
# it, which is what makes the snapshot tests readable.
#
# French, with accents, because that is what a contract in the launch markets
# says and because the values are quoted into the document verbatim. A duration
# of "x" would make every failure message about a licence unreadable, and an
# ASCII-folded one would quietly hide the fact that nothing anywhere normalises
# these strings.
LICENCE_TERMS = {
    "licence_option": "2",
    "licence_duration": "douze (12) mois à compter de la première publication",
    "licence_territories": "Bénin, Togo et Côte d'Ivoire",
    "licence_media": "réseaux sociaux de la marque, son site web et la publicité payante en ligne",
}


def licence_terms() -> dict:
    """The licence block a brief or an order states, as a request would send it.

    A COPY, so a suite that posts it and then mutates what it got back cannot
    reach the constant above and change what every other suite sends. The party
    helpers below take the same care for the same reason.

    Sent under the request key `licence_terms`, which is the same name the
    column, the response field and the error code's noun all use: one name in
    every direction, so a fixture reads the way the payload does.
    """
    return dict(LICENCE_TERMS)


def business_party_block(legal_name: str = BUSINESS_LEGAL_NAME) -> dict:
    """A registered company's block, carrying every field its type requires.

    REGISTERED_COMPANY rather than the sole trader shape a great many real
    buyers in the launch markets will be, and deliberately so: it is the branch
    with the longest required set (legal_form, registration_number,
    tax_identifier, representative_name and representative_capacity, on top of
    the four fields every block carries), which makes a fixture built on it the
    one that notices when that set grows. The sole trader branch is exercised on
    the creator side below, and test_contracts.py owns the per-type rendering.

    display_label is DERIVED from legal_name here, the same way
    party_details.derive_display_label derives it at capture, because this
    writes the column directly and nothing is going to derive it on the way in.
    The renderer falls back to it when there is no legal name to print, so a
    block that omitted it would be a block that can put a blank party on a
    contract.
    """
    return {
        "party_type": profiles.REGISTERED_COMPANY,
        "display_label": legal_name,
        "legal_name": legal_name,
        "legal_form": "SARL",
        "registration_number": "RB/COT/23 B 12345",
        "tax_identifier": "3201234567890",
        "country": "BJ",
        "address": "Lot 42, Haie Vive, Cotonou",
        "representative_name": "Adeline Zinsou",
        "representative_capacity": "Gerante",
    }


def creator_party_block(legal_name: str = CREATOR_LEGAL_NAME) -> dict:
    """A sole trader's block: a name, an address, a country, and nothing else.

    That is the COMPLETE form for a natural person contracting under their own
    name rather than a reduced version of the company one, which
    profiles/models.py is emphatic about, and it is what nearly every creator on
    this platform will be.

    tax_identifier is optional on this type and is left out. A fixture that
    filled in every optional field could not tell a required one from an
    optional one the day the sets change, and the whole value of this file is
    that it fails loudly in one place instead of quietly in four.
    """
    return {
        "party_type": profiles.SOLE_TRADER,
        "display_label": legal_name,
        "legal_name": legal_name,
        "country": "TG",
        "address": "Quartier Tokoin, Lome",
    }


def seed_business_party(db, user_id: str, legal_name: str = BUSINESS_LEGAL_NAME) -> dict:
    """State who a buyer contracts as, creating the profile row if there is none.

    UPDATE OR CREATE, not a blind insert: user_id is unique on this table and
    some suites already write a business profile of their own to get a company
    name onto an invitation card. Inserting a second row would fail the
    constraint, and overwriting the name they chose would break their
    assertions, so an existing row keeps its company_name and only gains the
    party block.

    company_name is NOT NULL and this is the one place a fixture has to invent
    one. It is set to the legal name from the block rather than to a
    placeholder, so the storefront name a creator reads on their contract card
    and the legal name printed inside the document agree. That matters here
    because contracts.service.list_my_contracts still resolves the card's name
    through a live join while the body reads the frozen snapshot; a fixture
    where the two disagree is a fixture that makes a real inconsistency look
    like a test bug.

    It COMMITS. Every call site opens its own short-lived session, writes its
    users and closes it, so work left pending here would be rolled back on
    close and the gate would refuse anyway, with nothing to show why.
    """
    profile = (
        db.query(profiles.BusinessProfile)
        .filter(profiles.BusinessProfile.user_id == user_id)
        .first()
    )
    if profile is None:
        profile = profiles.BusinessProfile(user_id=user_id, company_name=legal_name)
        db.add(profile)
    profile.party_details = business_party_block(legal_name)
    db.commit()
    return profile.party_details


def seed_creator_party(db, user_id: str, legal_name: str = CREATOR_LEGAL_NAME) -> dict:
    """State who a creator contracts as, creating the profile row if there is none.

    Update or create and commit, for the reasons seed_business_party gives. The
    creator side has nothing to invent: an influencer_profiles row needs only a
    user_id, which is why party_details.set_party_details is allowed to create
    one there and refuses to on the business side.
    """
    profile = (
        db.query(profiles.InfluencerProfile)
        .filter(profiles.InfluencerProfile.user_id == user_id)
        .first()
    )
    if profile is None:
        profile = profiles.InfluencerProfile(user_id=user_id)
        db.add(profile)
    profile.party_details = creator_party_block(legal_name)
    db.commit()
    return profile.party_details


def seed_party_details(db, user_id: str, role: str, legal_name: str | None = None) -> dict:
    """Give one user the block its side of the market states.

    Keyed on `role` because that is what decides which table the block lands
    on, and it is the same question party_details._profile_for_read asks:
    CREATOR_ROLE keeps its details on influencer_profiles and EVERYBODY ELSE IS
    A BUYER. Written that way round rather than as a whitelist, so that an
    agency or an ngo role arriving later is a buyer here without anybody
    remembering to come back and add it.
    """
    if role == CREATOR_ROLE:
        return seed_creator_party(db, user_id, legal_name or CREATOR_LEGAL_NAME)
    return seed_business_party(db, user_id, legal_name or BUSINESS_LEGAL_NAME)


def seed_both_parties(db, business_user_id: str, influencer_user_id: str) -> tuple[dict, dict]:
    """Both sides of one deal, for the suites whose fixture creates the pair.

    Returned in the order contracts.service._party_snapshots returns them, so a
    caller that wants to assert on what the contract should carry reads the two
    the same way round as the code that writes them.
    """
    return (
        seed_business_party(db, business_user_id),
        seed_creator_party(db, influencer_user_id),
    )
