"""A connected social account is not a pending one, and is not a verified one.

WHAT WAS WRONG. A creator who logged in to Facebook, granted the permissions
and chose their Page came away with a row reading "En attente" / Pending: the
same badge as somebody who had typed a handle into a box and proved nothing.
That is wrong on the creator's own screen and wrong to a brand deciding what
to spend, and there was no third value to say so.

WHAT IS NOT BEING DONE ABOUT IT. The easy fix was to let an authorisation
write VERIFIED, and it is refused on purpose. A social login proves somebody
holds the credentials to an account; it says nothing at all about who they
are. "Verified" has to keep meaning "an admin checked an identity document"
everywhere in the product, or it means nothing anywhere, so the third state
exists instead. app.modules.profiles.models.CONNECTED carries the argument.

THE HALF OF THIS FILE THAT MATTERS MOST IS THE LAST SECTION. Adding a value
to a closed set is easy; the risk is a query somewhere that meant "not yet
approved" by testing == PENDING, or "good" by testing == VERIFIED, and that
silently changes meaning the moment a third value exists. The audit found two
such queries, both in admin.service, and the tests under "The queries the new
state could have changed" pin them to what they answered before this shipped.

NO NETWORK. The provider is a fake, exactly as in test_social_oauth.py, and
the fixture is called `auth_client` for the same load-bearing reason: the
autouse fixture in backend/conftest.py rebinds `profile_owner` for any test
using a fixture named `client`, and POST /profiles/oauth/{platform}/start has
no `user_id` in its path to rebind it to.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from urllib.parse import parse_qs, urlparse

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.core.security import create_access_token
from app.modules.admin.router import router as admin_router
from app.modules.auth.models import User
from app.modules.profiles import models, oauth, oauth_service
from app.modules.profiles.router import router as profiles_router

# In PLATFORMS_WITH_AUDIENCE, so a follower count read from the fake provider
# is actually recorded rather than dropped as unverifiable.
PLATFORM = "tiktok"


@pytest.fixture()
def auth_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    ts = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models

    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = ts()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(profiles_router, prefix="/profiles")
    # THE ADMIN ROUTER IN THE SAME APP, which the OAuth tests next door do not
    # need. Half of this file is about what the admin queue and the admin
    # dashboard count, and reaching them through the real routes is the only
    # version of that test which would catch a filter that drifted.
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    # The real handler, so a refusal carries its `code`. Same reasoning as the
    # fixture in test_social_oauth.py.
    app.add_exception_handler(AppError, app_error_handler)
    c = TestClient(app)
    c.session_factory = ts
    return c


def _user(client, phone, is_admin=False):
    db = client.session_factory()
    try:
        u = User(
            phone=phone,
            email=f"{phone.lstrip('+')}@kolabo.test",
            password_hash="x",
            country_code="BJ",
            role="influencer",
            is_verified=True,
            is_admin=is_admin,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture()
def admin(auth_client):
    """An admin account and its token.

    Built here rather than taken from conftest's `admin_headers`, which hangs
    off a fixture named `client` and would drag the profile_owner override in
    with it.
    """
    admin_id = _user(auth_client, "+22990004900", is_admin=True)
    return {"id": admin_id, "headers": _headers(admin_id)}


class FakeProvider:
    """A platform that answers instantly, with a Page list behind it.

    Enough to drive BOTH halves of a real connection: the exchange, and the
    picker that a creator with several Pages has to go through. read_audience
    restates Meta's rule rather than inventing one, because the rule is what
    decides whether a follower count is recorded at all: one Page is a fact,
    none and several are questions it refuses to answer by guessing.
    """

    platform = PLATFORM

    def __init__(self, pages=()):
        self.pages = list(pages)

    def authorize_url(self, state, code_verifier, redirect_uri):
        return f"https://fake.test/oauth/authorize?state={state}"

    def exchange_code(self, code, code_verifier, redirect_uri):
        return oauth.TokenSet(
            access_token="access-1",
            refresh_token="refresh-1",
            access_expires_in=3600,
            refresh_expires_in=86400,
            scope="pages_show_list",
            provider_user_id="provider-user-1",
        )

    def refresh(self, refresh_token):
        raise AssertionError("nothing in this file renews a token")

    def list_pages(self, tokens):
        return list(self.pages)

    def read_audience(self, tokens):
        if len(self.pages) != 1:
            return None
        page = self.pages[0]
        return oauth.AudienceSnapshot(handle=page.name, follower_count=page.follower_count)


ONE_PAGE = [oauth.PlatformPage(id="page-solo", name="Chez Adjo", follower_count=12400)]
FOUR_PAGES = [
    oauth.PlatformPage(id="page-beauty", name="Beaute by Adjo", follower_count=9100),
    oauth.PlatformPage(id="page-gossip", name="Cotonou Buzz", follower_count=184000),
    oauth.PlatformPage(id="page-food", name="Chez Adjo", follower_count=3100),
    oauth.PlatformPage(id="page-client", name="Client Account", follower_count=41000),
]


def _register(monkeypatch, pages=()):
    provider = FakeProvider(pages)
    monkeypatch.setattr(oauth_service, "providers", {PLATFORM: provider})
    return provider


def _authorise(client, user_id):
    """Walk a whole authorization: start, then the callback the platform sends."""
    started = client.post(
        f"/profiles/oauth/{PLATFORM}/start", json={}, headers=_headers(user_id)
    )
    assert started.status_code == 200, started.text
    state = parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]
    done = client.get(
        f"/profiles/oauth/{PLATFORM}/callback",
        params={"code": "the-code", "state": state},
        follow_redirects=False,
    )
    assert done.status_code == 200, done.text
    return done.json()["account"]


def _type_a_handle(client, user_id, platform=PLATFORM, handle="ama", **extra):
    body = {
        "platform": platform,
        "handle": handle,
        "method": "manual",
        "proof_url": f"https://{platform}.com/@{handle}",
    }
    body.update(extra)
    r = client.post(
        f"/profiles/{user_id}/social-accounts", json=body, headers=_headers(user_id)
    )
    assert r.status_code == 201, r.text
    return r.json()


def _accounts(client, user_id):
    return client.get(f"/profiles/{user_id}/social-accounts").json()


def _set_status(client, account_id, value):
    """Put a row into a state only an admin decision reaches, without one.

    The same trick test_profiles.py's _verify_social_account uses and for the
    same reason: these tests are about what OTHER code does to a row already
    in that state, not about how it got there. decide_social's own behaviour
    is driven through the real endpoint further down.
    """
    db = client.session_factory()
    try:
        account = (
            db.query(models.SocialAccount)
            .filter(models.SocialAccount.id == account_id)
            .first()
        )
        assert account is not None, "no such social account"
        account.status = value
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------
# The three states, each written by exactly one path
# --------------------------------------------------------------------------


def test_an_oauth_connection_lands_connected(auth_client, monkeypatch):
    """THE CHANGE, IN ONE TEST. The creator authorised us on the platform, so
    the row says so instead of claiming to be an unchecked handle."""
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004001")

    account = _authorise(auth_client, uid)
    assert account["status"] == "connected"
    assert account["method"] == "oauth"
    # And it is what was stored, not only what the callback said.
    assert _accounts(auth_client, uid)[0]["status"] == "connected"


def test_an_oauth_connection_is_not_verified(auth_client, monkeypatch):
    """THE LINE THIS WHOLE CHANGE EXISTS TO HOLD.

    Turning `status=models.CONNECTED` in oauth_service._account_for into
    `models.VERIFIED` would be a one word edit, it would look like a feature,
    and it would quietly redefine the only word in this product that promises
    a person was checked. A social login proves control of an account and
    nothing about who is holding it.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004002")

    assert _authorise(auth_client, uid)["status"] != "verified"


def test_a_typed_handle_still_lands_pending(auth_client):
    """UNCHANGED, and it has to be: nothing on this path has checked anything,
    so a request body claiming `method: oauth` is the same worthless string it
    always was."""
    uid = _user(auth_client, "+22990004003")

    assert _type_a_handle(auth_client, uid)["status"] == "pending"

    claimed = auth_client.post(
        f"/profiles/{uid}/social-accounts",
        json={"platform": "instagram", "handle": "ama", "method": "oauth"},
        headers=_headers(uid),
    )
    assert claimed.status_code == 201, claimed.text
    assert claimed.json()["status"] == "pending"


def test_an_admin_decision_still_lands_verified(auth_client, admin):
    """The honest path to a badge, walked end to end and unchanged."""
    uid = _user(auth_client, "+22990004004")
    account = _type_a_handle(auth_client, uid)

    decided = auth_client.post(
        f"/admin/social-accounts/{account['id']}/decision",
        json={"decision": "approved"},
        headers=admin["headers"],
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "verified"
    assert decided.json()["reviewer_id"] == admin["id"]
    assert _accounts(auth_client, uid)[0]["status"] == "verified"


def test_an_admin_can_verify_a_connected_account(auth_client, monkeypatch, admin):
    """A connected account is a queue item like any other.

    Proving control does not answer the question decide_social settles, so a
    creator who authorised the platform still reaches a badge the same way
    somebody who typed a handle does. If this went red, connecting an account
    would have taken it permanently out of reach of verification.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004005")
    account = _authorise(auth_client, uid)
    assert account["status"] == "connected"

    decided = auth_client.post(
        f"/admin/social-accounts/{account['id']}/decision",
        json={"decision": "approved"},
        headers=admin["headers"],
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "verified"


def test_an_admin_rejection_still_lands_rejected(auth_client, monkeypatch, admin):
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004006")
    account = _authorise(auth_client, uid)

    decided = auth_client.post(
        f"/admin/social-accounts/{account['id']}/decision",
        json={"decision": "rejected", "reason": "The Page is not theirs"},
        headers=admin["headers"],
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "rejected"


# --------------------------------------------------------------------------
# Choosing a Page, which is the second half of a connection
# --------------------------------------------------------------------------


def test_choosing_a_page_leaves_the_account_connected_with_a_platform_source(
    auth_client, monkeypatch
):
    """The picker records the audience AND leaves the state saying `connected`.

    A creator with four Pages gets no follower count at connection time,
    because read_audience refuses to guess which of their businesses is their
    identity. Choosing one is the answer, and all three provenance columns go
    in together per #161. What must NOT happen is the state quietly becoming a
    badge on the way: a Page selection is proof of control, exactly like the
    authorisation it belongs to, and nothing more.
    """
    _register(monkeypatch, FOUR_PAGES)
    uid = _user(auth_client, "+22990004010")
    account = _authorise(auth_client, uid)
    # Four Pages, so nothing was recorded automatically.
    assert account["follower_count"] is None
    assert account["follower_source"] is None
    assert account["status"] == "connected"

    chosen = auth_client.post(
        f"/profiles/oauth/{PLATFORM}/pages/page-beauty", headers=_headers(uid)
    )
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()
    assert body["id"] == account["id"], "the row that already existed, not a new one"
    assert body["handle"] == "Beaute by Adjo"
    assert body["follower_count"] == 9100
    assert body["follower_source"] == "platform_api"
    assert body["follower_verified_at"] is not None
    assert body["status"] == "connected"
    # And not the biggest Page, which is the whole argument for asking.
    assert body["follower_count"] != 184000

    assert _accounts(auth_client, uid)[0]["status"] == "connected"


def test_choosing_a_page_re_earns_connected_for_a_demoted_row(auth_client, monkeypatch):
    """A creator who typed over their handle and then picked a Page again.

    The handle edit dropped the row to pending, which is right: what the
    platform had confirmed was the old handle. Selecting a Page reads the list
    live with the creator's own token, which is the same proof the connection
    rested on, so the row earns `connected` back.
    """
    _register(monkeypatch, FOUR_PAGES)
    uid = _user(auth_client, "+22990004011")
    account = _authorise(auth_client, uid)

    edited = auth_client.put(
        f"/profiles/{uid}/social-accounts/{account['id']}",
        json={"handle": "typed-over"},
        headers=_headers(uid),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "pending"

    chosen = auth_client.post(
        f"/profiles/oauth/{PLATFORM}/pages/page-food", headers=_headers(uid)
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["status"] == "connected"
    assert chosen.json()["handle"] == "Chez Adjo"


@pytest.mark.parametrize("decided", ["verified", "rejected"])
def test_choosing_a_page_never_overwrites_an_admin_decision(
    auth_client, monkeypatch, decided
):
    """Both directions of the same rule.

    Upwards: a Page selection must not be able to hand out a badge an admin
    never gave, which is the whole point of the third state.
    Downwards: it must not quietly undo a rejection either, or reconnecting
    would be a way round the review queue.
    """
    _register(monkeypatch, FOUR_PAGES)
    uid = _user(auth_client, "+22990004012" if decided == "verified" else "+22990004013")
    account = _authorise(auth_client, uid)
    _set_status(auth_client, account["id"], decided)

    chosen = auth_client.post(
        f"/profiles/oauth/{PLATFORM}/pages/page-beauty", headers=_headers(uid)
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["status"] == decided
    # The audience was still recorded: the two questions are separate.
    assert chosen.json()["follower_count"] == 9100


# --------------------------------------------------------------------------
# Editing a handle, and reconnecting after one
# --------------------------------------------------------------------------


def test_editing_the_handle_demotes_a_connected_account(auth_client, monkeypatch):
    """CONNECTED belongs to the account it was proved on.

    Without this the trick is easy and worth real money: authorise a small
    account, collect `connected`, then retype the handle as somebody far
    larger and keep a state saying the platform vouched for it. The same trick
    the follower_count branch already refuses, played on the other field.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004020")
    account = _authorise(auth_client, uid)
    assert account["status"] == "connected"

    edited = auth_client.put(
        f"/profiles/{uid}/social-accounts/{account['id']}",
        json={"handle": "someone_much_bigger"},
        headers=_headers(uid),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["handle"] == "someone_much_bigger"
    assert edited.json()["status"] == "pending"


def test_editing_the_handle_still_demotes_a_verified_account(auth_client):
    """The rule this one was extended from, unchanged."""
    uid = _user(auth_client, "+22990004021")
    account = _type_a_handle(auth_client, uid, handle="old_handle")
    _set_status(auth_client, account["id"], "verified")

    edited = auth_client.put(
        f"/profiles/{uid}/social-accounts/{account['id']}",
        json={"handle": "new_handle"},
        headers=_headers(uid),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "pending"


def test_editing_only_the_follower_count_leaves_connected_alone(auth_client, monkeypatch):
    """The number and the state answer different questions.

    Retyping a count makes the number self-reported again, which is the
    existing rule and is right. It says nothing about whether the creator
    still controls the account, so the state does not move.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004022")
    account = _authorise(auth_client, uid)
    assert account["follower_source"] == "platform_api"

    edited = auth_client.put(
        f"/profiles/{uid}/social-accounts/{account['id']}",
        json={"follower_count": 999999},
        headers=_headers(uid),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["follower_source"] == "self_reported"
    assert edited.json()["status"] == "connected"


def test_reconnecting_earns_connected_again(auth_client, monkeypatch):
    """A second authorisation is a second proof of control."""
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004023")
    account = _authorise(auth_client, uid)
    _set_status(auth_client, account["id"], "pending")

    again = _authorise(auth_client, uid)
    assert again["id"] == account["id"], "one row, not two"
    assert again["status"] == "connected"


@pytest.mark.parametrize("decided", ["verified", "rejected"])
def test_reconnecting_never_overwrites_an_admin_decision(auth_client, monkeypatch, decided):
    """Same rule as the picker, on the other entry point.

    A rejection in particular must not be undoable by pressing Connect again,
    or the review queue is decoration.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004024" if decided == "verified" else "+22990004025")
    account = _authorise(auth_client, uid)
    _set_status(auth_client, account["id"], decided)

    again = _authorise(auth_client, uid)
    assert again["id"] == account["id"]
    assert again["status"] == decided


# --------------------------------------------------------------------------
# The queries the new state could have changed
#
# THIS IS THE POINT OF THE PULL REQUEST. Adding a value to a closed set is
# easy. The danger is a query that means "not yet approved" by testing
# == PENDING, or "good" by testing == VERIFIED, and which silently answers
# something different once a third value exists. The audit found two, both in
# admin.service, and both are pinned here to what they answered before.
# --------------------------------------------------------------------------


def test_the_default_queue_still_holds_an_authorised_connection(
    auth_client, monkeypatch, admin
):
    """THE REGRESSION GUARD FOR THE AUDIT.

    An authorised account used to be written as PENDING and therefore stood in
    the default verification queue. It is CONNECTED now. Leave
    list_verification_queue filtering on PENDING alone and this row vanishes
    from the admin's worklist the day the feature ships, with nothing failing
    anywhere: the queue simply gets shorter and an account nobody has checked
    stops being offered for checking.
    """
    _register(monkeypatch, ONE_PAGE)
    connected_user = _user(auth_client, "+22990004030")
    typed_user = _user(auth_client, "+22990004031")
    connected = _authorise(auth_client, connected_user)
    typed = _type_a_handle(auth_client, typed_user)

    queue = auth_client.get("/admin/verification-queue", headers=admin["headers"]).json()
    ids = {row["id"] for row in queue["social_accounts"]}
    assert connected["id"] in ids, "a connected account is still waiting for review"
    assert typed["id"] in ids, "and so is a typed one, exactly as before"


def test_the_dashboard_still_counts_an_authorised_connection_as_waiting(
    auth_client, monkeypatch, admin
):
    """The count and the queue have to agree.

    pending_social_accounts is the size of the queue above, so the two read
    the same states or the dashboard sends an admin to a page with a different
    number of rows on it. The key keeps its name, and what it has always meant
    is "social accounts nobody has decided on yet".
    """
    _register(monkeypatch, ONE_PAGE)
    _authorise(auth_client, _user(auth_client, "+22990004032"))
    _type_a_handle(auth_client, _user(auth_client, "+22990004033"))

    summary = auth_client.get("/admin/dashboard", headers=admin["headers"]).json()
    assert summary["verification"]["pending_social_accounts"] == 2

    queue = auth_client.get("/admin/verification-queue", headers=admin["headers"]).json()
    assert len(queue["social_accounts"]) == 2


def test_a_decided_account_is_out_of_the_queue_and_the_count(
    auth_client, monkeypatch, admin
):
    """The other half of the filter, which is what stops it being a no-op.

    Widening the default queue to two states must not widen it to all of them:
    an account an admin has already verified or rejected is decided, and
    putting it back in front of them would be a worse bug than the one this
    change fixes.
    """
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004034")
    account = _authorise(auth_client, uid)
    auth_client.post(
        f"/admin/social-accounts/{account['id']}/decision",
        json={"decision": "approved"},
        headers=admin["headers"],
    )

    queue = auth_client.get("/admin/verification-queue", headers=admin["headers"]).json()
    assert queue["social_accounts"] == []
    summary = auth_client.get("/admin/dashboard", headers=admin["headers"]).json()
    assert summary["verification"]["pending_social_accounts"] == 0


def test_an_explicit_status_filter_is_still_literal(auth_client, monkeypatch, admin):
    """Only the DEFAULT widened. An admin who names a status gets that status.

    Which also means `connected` is now askable on its own, so the queue can
    be read as two piles if somebody wants to triage them differently.
    """
    _register(monkeypatch, ONE_PAGE)
    connected = _authorise(auth_client, _user(auth_client, "+22990004035"))
    typed = _type_a_handle(auth_client, _user(auth_client, "+22990004036"))

    only_pending = auth_client.get(
        "/admin/verification-queue", params={"item_status": "pending"}, headers=admin["headers"]
    ).json()
    assert [row["id"] for row in only_pending["social_accounts"]] == [typed["id"]]

    only_connected = auth_client.get(
        "/admin/verification-queue",
        params={"item_status": "connected"},
        headers=admin["headers"],
    ).json()
    assert [row["id"] for row in only_connected["social_accounts"]] == [connected["id"]]


def test_the_document_queue_is_untouched_by_any_of_this(auth_client, admin):
    """profiles.CONNECTED is a social account state and nothing else.

    A verification document has nothing it could be connected to, so its half
    of the same function still filters on PENDING alone, and this is the test
    that notices if somebody widens it out of symmetry.
    """
    uid = _user(auth_client, "+22990004037")
    uploaded = auth_client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "identity"},
        files={"file": ("id.png", b"bytes", "image/png")},
        headers=_headers(uid),
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["status"] == "pending"

    queue = auth_client.get("/admin/verification-queue", headers=admin["headers"]).json()
    assert [row["status"] for row in queue["documents"]] == ["pending"]
    summary = auth_client.get("/admin/dashboard", headers=admin["headers"]).json()
    assert summary["verification"]["pending_documents"] == 1


def test_the_public_profile_carries_the_new_state(auth_client, monkeypatch):
    """The storefront shows every connected account with its status, and has
    since the verified-only filter was removed. A third value rides that
    payload with no filtering of its own: this is the page a brand reads, and
    it is the whole reason the state was worth adding."""
    _register(monkeypatch, ONE_PAGE)
    uid = _user(auth_client, "+22990004040")
    auth_client.put(
        f"/profiles/influencer/{uid}",
        json={"bio": "Hi", "categories": ["fashion"], "rate_card": {}},
        headers=_headers(uid),
    )
    _authorise(auth_client, uid)

    social = auth_client.get(f"/profiles/influencer/{uid}/public").json()["social_accounts"]
    assert [row["status"] for row in social] == ["connected"]
    assert social[0]["follower_source"] == "platform_api"
