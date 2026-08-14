"""Tests for Epic B (KOL-2): profiles and verification."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.modules.admin.router import router as admin_router
from app.modules.auth.models import User
from app.modules.profiles.router import router as profiles_router


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    from app.core.db import import_all_models
    import_all_models()
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # The real handler, not a lookalike: without it an AppError falls through
    # to FastAPI's default HTTPException handler, which serialises `detail`
    # and drops `code`. Every existing assertion in this file reads `detail`
    # or a status and is unaffected — the handler only adds the two siblings
    # (see app/core/errors.py, which lives outside main.py for this reason).
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(profiles_router, prefix="/profiles")
    app.include_router(admin_router, prefix="/admin")
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    test_client.session_factory = testing_session
    return test_client


def _make_user(client, phone="+22990000001", role="influencer"):
    db = client.session_factory()
    try:
        user = User(phone=phone, password_hash="x", country_code="BJ", role=role, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _add_packages(client, uid, n=3):
    """Enough active packages to satisfy the storefront requirement, at
    floor-respecting prices."""
    types = ["post", "reel", "story"]
    for i in range(n):
        r = client.post(f"/profiles/{uid}/packages", json={
            "platform": "instagram", "deliverable_type": types[i % len(types)],
            "title": f"IG {types[i % len(types)]} #{i + 1}",
            "price_amount": 30000, "currency": "XOF",
        })
        assert r.status_code == 201, r.text


def test_influencer_profile_completion_and_searchable(client):
    uid = _make_user(client)
    # Partial profile is not searchable and under 100 percent.
    r = client.put(f"/profiles/influencer/{uid}", json={"bio": "Creator", "categories": [], "rate_card": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["completion_percent"] == 33
    assert body["is_searchable"] is False
    # Bio and categories are 2 of 3. The legacy rate card no longer counts as
    # pricing (nothing on it can be ordered), so the profile stays unsearchable.
    r = client.put(
        f"/profiles/influencer/{uid}",
        json={"bio": "Creator", "categories": ["fashion"], "rate_card": {"post": 100}},
    )
    body = r.json()
    assert body["completion_percent"] == 67
    assert body["is_searchable"] is False
    # Three active packages complete the storefront.
    _add_packages(client, uid)
    got = client.get(f"/profiles/influencer/{uid}").json()
    assert got["completion_percent"] == 100
    assert got["is_searchable"] is True


def test_influencer_profile_requires_existing_user(client):
    r = client.put("/profiles/influencer/does-not-exist", json={"bio": "x", "categories": ["a"], "rate_card": {"p": 1}})
    assert r.status_code == 404


def test_business_profile_upsert(client):
    uid = _make_user(client, phone="+22990000002", role="business")
    r = client.put(f"/profiles/business/{uid}", json={"company_name": "Acme", "industry": "retail"})
    assert r.status_code == 200
    assert r.json()["company_name"] == "Acme"


def test_business_profile_round_trip(client):
    """PUT then GET returns the same data. The GET is new: the profile used to
    be write-only, so the settings page always came up blank after a save."""
    uid = _make_user(client, phone="+22990000012", role="business")
    saved = client.put(
        f"/profiles/business/{uid}",
        json={"company_name": "Acme", "industry": "retail", "description": "Retail brand in Cotonou"},
    ).json()
    got = client.get(f"/profiles/business/{uid}")
    assert got.status_code == 200
    assert got.json() == saved
    assert got.json()["description"] == "Retail brand in Cotonou"


def test_business_profile_get_without_profile_is_404(client):
    uid = _make_user(client, phone="+22990000013", role="business")
    assert client.get(f"/profiles/business/{uid}").status_code == 404


def test_verification_document_stored_encrypted_and_pending(client):
    uid = _make_user(client, phone="+22990000003", role="business")
    r = client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "business_registration"},
        files={"file": ("reg.pdf", b"real-document-bytes", "application/pdf")},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    # The stored bytes must be ciphertext, never the raw document.
    from app.modules.profiles.models import VerificationDocument
    db = client.session_factory()
    doc = db.query(VerificationDocument).first()
    stored = bytes(doc.ciphertext)
    db.close()
    assert b"real-document-bytes" not in stored


def test_verification_document_over_the_ceiling_is_refused(client):
    """The other unbounded write in this module. A document is encrypted and
    stored whole in a LargeBinary column, so it needs the same ceiling as an
    image and carries the same code. Checked on the PLAINTEXT: encrypting only
    makes the stored row bigger."""
    from app.modules.profiles.models import VerificationDocument
    from app.modules.profiles.service import MAX_MEDIA_BYTES

    uid = _make_user(client, phone="+22990000062", role="business")
    oversized = b"\x00" * (MAX_MEDIA_BYTES + 1)
    r = client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "identity"},
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert r.status_code == 413
    assert r.json()["code"] == "profile_file_too_large"
    assert r.json()["values"] == {"max": MAX_MEDIA_BYTES // (1024 * 1024)}
    # The other half: nothing was written.
    db = client.session_factory()
    assert db.query(VerificationDocument).count() == 0
    db.close()


def test_verification_document_under_the_ceiling_still_uploads(client):
    """The happy path is untouched."""
    from app.modules.profiles.models import VerificationDocument

    uid = _make_user(client, phone="+22990000063", role="business")
    r = client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "identity"},
        files={"file": ("id.pdf", b"an-ordinary-document", "application/pdf")},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    db = client.session_factory()
    assert db.query(VerificationDocument).count() == 1
    db.close()


def test_social_oauth_is_verified_manual_is_pending(client):
    uid = _make_user(client, phone="+22990000004")
    r = client.post(f"/profiles/{uid}/social-accounts", json={"platform": "instagram", "handle": "me", "method": "oauth"})
    assert r.status_code == 201
    assert r.json()["status"] == "verified"
    r = client.post(
        f"/profiles/{uid}/social-accounts",
        json={"platform": "tiktok", "handle": "me", "method": "manual", "proof_url": "https://proof"},
    )
    assert r.json()["status"] == "pending"


def test_manual_social_requires_proof(client):
    uid = _make_user(client, phone="+22990000005")
    r = client.post(f"/profiles/{uid}/social-accounts", json={"platform": "tiktok", "handle": "me", "method": "manual"})
    assert r.status_code == 400


def test_social_account_edit_round_trips_and_resets_verification(client):
    """Editing the handle of a verified account must send it back to pending:
    the badge was earned by the old handle, not whatever it now points at."""
    uid = _make_user(client, phone="+22990000030")
    acc = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "instagram", "handle": "old_handle", "method": "oauth",
    }).json()
    assert acc["status"] == "verified"
    r = client.put(f"/profiles/{uid}/social-accounts/{acc['id']}", json={"handle": "new_handle"})
    assert r.status_code == 200
    assert r.json()["handle"] == "new_handle"
    assert r.json()["status"] == "pending"
    listed = client.get(f"/profiles/{uid}/social-accounts").json()
    assert listed[0]["handle"] == "new_handle"
    assert listed[0]["status"] == "pending"


def test_social_account_edit_without_handle_change_keeps_verification(client):
    """Updating the follower count is not pointing at a different account, so
    the verified badge survives."""
    uid = _make_user(client, phone="+22990000031")
    acc = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "instagram", "handle": "ama", "method": "oauth",
    }).json()
    r = client.put(f"/profiles/{uid}/social-accounts/{acc['id']}", json={"follower_count": 9000})
    assert r.status_code == 200
    assert r.json()["status"] == "verified"
    assert r.json()["follower_count"] == 9000


def test_social_account_edit_discards_unverifiable_follower_count(client):
    """Same rule as connect: WhatsApp exposes no public metric, so an edited
    count is dropped rather than displayed."""
    uid = _make_user(client, phone="+22990000036")
    acc = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "whatsapp", "handle": "ama", "method": "manual", "proof_url": "https://p",
    }).json()
    r = client.put(f"/profiles/{uid}/social-accounts/{acc['id']}", json={"follower_count": 5000})
    assert r.status_code == 200
    assert r.json()["follower_count"] is None


def test_social_account_edit_requires_ownership(client):
    a = _make_user(client, phone="+22990000032")
    b = _make_user(client, phone="+22990000033")
    acc = client.post(f"/profiles/{a}/social-accounts", json={
        "platform": "tiktok", "handle": "ama", "method": "manual", "proof_url": "https://p",
    }).json()
    assert client.put(f"/profiles/{b}/social-accounts/{acc['id']}", json={"handle": "stolen"}).status_code == 403
    assert client.delete(f"/profiles/{b}/social-accounts/{acc['id']}").status_code == 403
    assert client.put(f"/profiles/{a}/social-accounts/missing", json={"handle": "x"}).status_code == 404


def test_social_account_delete_removes_it_from_the_list(client):
    uid = _make_user(client, phone="+22990000034")
    acc = client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "tiktok", "handle": "ama", "method": "manual", "proof_url": "https://p",
    }).json()
    assert client.delete(f"/profiles/{uid}/social-accounts/{acc['id']}").status_code == 204
    assert client.get(f"/profiles/{uid}/social-accounts").json() == []


def test_public_profile_shows_pending_accounts_with_status(client):
    """During the pilot every manual connection is pending (OAuth verification
    has not shipped), so a verified-only filter emptied the audience section
    for everyone. The page now shows every connected account with its status
    and the frontend badges the verified ones."""
    uid = _make_user(client, phone="+22990000035")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    client.post(f"/profiles/{uid}/social-accounts", json={
        "platform": "tiktok", "handle": "ama", "method": "manual",
        "proof_url": "https://p", "follower_count": 4200,
    })
    pub = client.get(f"/profiles/influencer/{uid}/public").json()
    assert len(pub["social_accounts"]) == 1
    assert pub["social_accounts"][0]["status"] == "pending"
    assert pub["social_accounts"][0]["follower_count"] == 4200


def test_admin_queue_requires_an_admin(client):
    r = client.get("/admin/verification-queue")
    assert r.status_code == 401


def test_admin_can_approve_document_and_decision_is_logged(client, admin_headers, admin_user_id):
    uid = _make_user(client, phone="+22990000006", role="business")
    client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "business_registration"},
        files={"file": ("reg.pdf", b"bytes", "application/pdf")},
    )
    queue = client.get("/admin/verification-queue", headers=admin_headers).json()
    assert len(queue["documents"]) == 1
    doc_id = queue["documents"][0]["id"]
    r = client.post(f"/admin/verification-documents/{doc_id}/decision", json={"decision": "approved"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    # The reviewer is the account that decided, not a header value.
    assert r.json()["reviewer_id"] == admin_user_id
    # Decision is recorded in the audit log.
    from app.modules.admin.models import AdminActionLog
    db = client.session_factory()
    log = db.query(AdminActionLog).first()
    db.close()
    assert log.admin_id == admin_user_id
    assert log.target_id == doc_id


def test_document_rejection_requires_reason(client, admin_headers):
    uid = _make_user(client, phone="+22990000007", role="business")
    client.post(
        f"/profiles/{uid}/verification-documents",
        data={"doc_type": "identity"},
        files={"file": ("id.png", b"bytes", "image/png")},
    )
    queue = client.get("/admin/verification-queue", headers=admin_headers).json()
    doc_id = queue["documents"][0]["id"]
    r = client.post(f"/admin/verification-documents/{doc_id}/decision", json={"decision": "rejected"}, headers=admin_headers)
    assert r.status_code == 400
    r = client.post(
        f"/admin/verification-documents/{doc_id}/decision",
        json={"decision": "rejected", "reason": "Document unreadable"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepngdata"


def test_profile_saves_and_loads_new_fields(client):
    uid = _make_user(client)
    r = client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "headline": "Lifestyle creator", "location": "Cotonou, BJ",
        "bio": "Hi", "categories": ["fashion"], "rate_card": {}, "follower_count": 12000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Ama K."
    assert body["headline"] == "Lifestyle creator"
    # Reload returns the saved values.
    got = client.get(f"/profiles/influencer/{uid}").json()
    assert got["display_name"] == "Ama K."
    assert got["location"] == "Cotonou, BJ"


def test_saving_without_avatar_keeps_the_existing_one(client):
    """The onboarding wizard does not send avatar_media_id. Omitting the field
    must not delete the avatar that enrichment downloaded from YouTube."""
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "avatar_media_id": media_id,
        "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    # A save that never mentions the avatar leaves it alone.
    r = client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "bio": "Hi again", "categories": ["fashion"], "rate_card": {},
    })
    assert r.status_code == 200
    assert r.json()["avatar_media_id"] == media_id
    assert client.get(f"/profiles/influencer/{uid}").json()["avatar_url"] == f"/profiles/media/{media_id}"


def test_explicit_null_avatar_still_clears_it(client):
    """Omission is a no-op, but an explicit null is how a creator removes their
    photo, so that must keep working."""
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    client.put(f"/profiles/influencer/{uid}", json={
        "avatar_media_id": media_id, "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    r = client.put(f"/profiles/influencer/{uid}", json={
        "avatar_media_id": None, "bio": "Hi", "categories": ["fashion"], "rate_card": {},
    })
    assert r.status_code == 200
    assert r.json()["avatar_media_id"] is None
    assert r.json()["avatar_url"] is None


def test_saving_without_bio_fr_keeps_the_existing_one(client):
    """Same class of bug as the avatar: a form that only knows the legacy `bio`
    column must not wipe the bilingual bios."""
    uid = _make_user(client)
    client.put(f"/profiles/influencer/{uid}", json={
        "bio_fr": "Bonjour, je suis créatrice à Cotonou.", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    r = client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    assert r.status_code == 200
    assert r.json()["bio_fr"] == "Bonjour, je suis créatrice à Cotonou."


def test_faq_saves_and_round_trips(client):
    uid = _make_user(client, phone="+22990000014")
    r = client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
        "faq": {"audience": "Mostly 18-24 in Cotonou", "brands": "Fashion and beauty"},
    })
    assert r.status_code == 200
    assert r.json()["faq"]["audience"] == "Mostly 18-24 in Cotonou"
    got = client.get(f"/profiles/influencer/{uid}").json()
    assert got["faq"] == {"audience": "Mostly 18-24 in Cotonou", "brands": "Fashion and beauty"}


def test_saving_without_faq_preserves_it(client):
    """Same contract as the avatar: a form that does not know about the faq
    (omits the key entirely) must not wipe the creator's answers."""
    uid = _make_user(client, phone="+22990000015")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
        "faq": {"audience": "Mostly Cotonou", "brands": "Local fashion"},
    })
    r = client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi again", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    assert r.status_code == 200
    assert r.json()["faq"] == {"audience": "Mostly Cotonou", "brands": "Local fashion"}


def test_public_profile_omits_empty_faq_answers(client):
    """An empty answer is an unanswered question: the public page shows only
    what the creator actually wrote."""
    uid = _make_user(client, phone="+22990000016")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
        "faq": {"audience": "Mostly Cotonou", "brands": ""},
    })
    pub = client.get(f"/profiles/influencer/{uid}/public").json()
    assert pub["faq"] == {"audience": "Mostly Cotonou"}
    # The owner's own view still round-trips the empty answer, so the edit
    # form can show the question as unanswered.
    assert client.get(f"/profiles/influencer/{uid}").json()["faq"]["brands"] == ""


def test_public_profile_lists_only_revealed_reviews(client):
    """The public page shows the reviews behind the average: revealed only
    (double blind), with the reviewer named from their influencer profile."""
    uid = _make_user(client, phone="+22990000017")
    client.put(f"/profiles/influencer/{uid}", json={
        "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 100},
    })
    reviewer = _make_user(client, phone="+22990000018")
    client.put(f"/profiles/influencer/{reviewer}", json={"display_name": "Kofi A."})
    business_reviewer = _make_user(client, phone="+22990000019", role="business")

    from app.modules.trust_safety.models import Review
    db = client.session_factory()
    db.add(Review(escrow_id="esc-1", campaign_id="c-1", reviewer_user_id=reviewer,
                  reviewee_user_id=uid, stars=5, comment="Great work", revealed=True))
    # The other side has not reviewed yet, so this one stays hidden.
    db.add(Review(escrow_id="esc-2", campaign_id="c-2", reviewer_user_id=business_reviewer,
                  reviewee_user_id=uid, stars=1, comment="Not revealed yet", revealed=False))
    db.commit()
    db.close()

    pub = client.get(f"/profiles/influencer/{uid}/public").json()
    assert pub["review_count"] == 1
    assert len(pub["reviews"]) == 1
    review = pub["reviews"][0]
    assert review["stars"] == 5
    assert review["comment"] == "Great work"
    assert review["reviewer_display_name"] == "Kofi A."
    assert review["created_at"] is not None


def test_media_upload_and_serve(client):
    uid = _make_user(client)
    up = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")})
    assert up.status_code == 201
    media_id = up.json()["id"]
    assert up.json()["url"] == f"/profiles/media/{media_id}"
    served = client.get(f"/profiles/media/{media_id}")
    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["content-type"].startswith("image/png")


def test_media_rejects_non_image(client):
    uid = _make_user(client)
    r = client.post(f"/profiles/{uid}/media", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_media_over_the_ceiling_is_refused(client):
    """Web test-plan P7: a 20 MB photo comes back as a graceful refusal, not a
    500 and not a 20 MB row. MediaAsset.data is a Postgres blob, so an upload
    with no ceiling is a database row with no ceiling.

    The real payload, not a monkeypatched constant: this goes through the
    router, the UploadFile read and the service check exactly as a phone would.
    """
    from app.modules.profiles.models import MediaAsset
    from app.modules.profiles.service import MAX_MEDIA_BYTES

    uid = _make_user(client, phone="+22990000060")
    oversized = b"\x00" * (MAX_MEDIA_BYTES + 1)
    r = client.post(f"/profiles/{uid}/media", files={"file": ("big.png", oversized, "image/png")})
    assert r.status_code == 413
    assert r.json()["code"] == "profile_file_too_large"
    # The ceiling travels as a number, in the units the sentence quotes.
    assert r.json()["values"] == {"max": MAX_MEDIA_BYTES // (1024 * 1024)}
    # The other half: the row was never written.
    db = client.session_factory()
    assert db.query(MediaAsset).count() == 0
    db.close()


def test_media_under_the_ceiling_still_uploads(client):
    """The happy path is untouched: a file comfortably under the ceiling still
    comes back with its id and its serving url."""
    from app.modules.profiles.models import MediaAsset
    from app.modules.profiles.service import MAX_MEDIA_BYTES

    uid = _make_user(client, phone="+22990000061")
    ordinary = PNG_BYTES + b"\x00" * (MAX_MEDIA_BYTES // 2)
    r = client.post(f"/profiles/{uid}/media", files={"file": ("ok.png", ordinary, "image/png")})
    assert r.status_code == 201
    assert r.json()["id"]
    assert r.json()["url"] == f"/profiles/media/{r.json()['id']}"
    db = client.session_factory()
    assert db.query(MediaAsset).count() == 1
    db.close()


def test_package_crud(client):
    uid = _make_user(client)
    created = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "description": "A 30s reel", "price_amount": 50000, "currency": "xof",
    })
    assert created.status_code == 201
    pkg = created.json()
    assert pkg["currency"] == "XOF"  # normalized
    assert pkg["is_active"] is True
    # List
    assert len(client.get(f"/profiles/{uid}/packages").json()) == 1
    # Update
    upd = client.put(f"/profiles/{uid}/packages/{pkg['id']}", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "price_amount": 60000, "currency": "XOF", "is_active": False,
    })
    assert upd.json()["price_amount"] == 60000
    assert upd.json()["is_active"] is False
    # active_only filter hides it
    assert client.get(f"/profiles/{uid}/packages?active_only=true").json() == []
    # Delete
    assert client.delete(f"/profiles/{uid}/packages/{pkg['id']}").status_code == 204
    assert client.get(f"/profiles/{uid}/packages").json() == []


def test_package_below_the_currency_floor_is_rejected(client):
    """Floors are a spam defence: a 1000 XOF "listing" is noise, not an offer.
    The check runs on the normalized currency, so lowercase xof hits it too."""
    uid = _make_user(client, phone="+22990000040")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "Too cheap",
        "price_amount": 1000, "currency": "xof",
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Minimum price for XOF is 5000."


def test_package_update_cannot_dip_below_the_floor(client):
    uid = _make_user(client, phone="+22990000041")
    pkg = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 30000, "currency": "XOF",
    }).json()
    r = client.put(f"/profiles/{uid}/packages/{pkg['id']}", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 4999, "currency": "XOF",
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Minimum price for XOF is 5000."
    # The stored price is untouched by the rejected update.
    assert client.get(f"/profiles/{uid}/packages").json()[0]["price_amount"] == 30000


def test_unknown_currency_has_no_floor(client):
    """Floors fight spam listings; they do not validate currencies. An unknown
    currency passes, so a new market can be piloted without a deploy."""
    uid = _make_user(client, phone="+22990000042")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "USD listing",
        "price_amount": 5, "currency": "USD",
    })
    assert r.status_code == 201


def test_package_update_requires_ownership(client):
    a = _make_user(client, phone="+22990000010")
    b = _make_user(client, phone="+22990000011")
    pkg = client.post(f"/profiles/{a}/packages", json={
        "platform": "tiktok", "deliverable_type": "video", "title": "TikTok",
        "price_amount": 40000, "currency": "XOF",
    }).json()
    r = client.put(f"/profiles/{b}/packages/{pkg['id']}", json={
        "platform": "tiktok", "deliverable_type": "video", "title": "TikTok",
        "price_amount": 1, "currency": "XOF",
    })
    assert r.status_code == 403


def test_package_quantity_and_duration_round_trip(client):
    """The Collabstr-style chips: ×10 and 30 Seconds come back exactly as
    saved, on the create response and on the list."""
    uid = _make_user(client, phone="+22990000050")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "10 IG Reels",
        "price_amount": 250000, "currency": "XOF",
        "quantity": 10, "duration_value": 30, "duration_unit": "seconds",
    })
    assert r.status_code == 201, r.text
    pkg = r.json()
    assert pkg["quantity"] == 10
    assert pkg["duration_value"] == 30
    assert pkg["duration_unit"] == "seconds"
    listed = client.get(f"/profiles/{uid}/packages").json()
    assert (listed[0]["quantity"], listed[0]["duration_value"], listed[0]["duration_unit"]) == (10, 30, "seconds")


def test_package_duration_value_without_unit_rejected(client):
    """The duration is a pair or nothing: "30" of nothing is not a spec."""
    uid = _make_user(client, phone="+22990000051")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "price_amount": 50000, "currency": "XOF", "duration_value": 30,
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "duration_value and duration_unit go together."
    # The mirror case: a unit with no value is just as meaningless.
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "price_amount": 50000, "currency": "XOF", "duration_unit": "seconds",
    })
    assert r.status_code == 400


def test_package_bad_duration_unit_rejected(client):
    """The unit is a closed set (seconds/minutes/hours) so the spec chips
    render from data, never from free text."""
    uid = _make_user(client, phone="+22990000052")
    r = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "reel", "title": "1 IG Reel",
        "price_amount": 50000, "currency": "XOF",
        "duration_value": 2, "duration_unit": "fortnights",
    })
    assert r.status_code == 422


def test_package_default_quantity_is_one(client):
    """A package that says nothing about quantity is a single deliverable,
    which is what every package sold before the field existed was."""
    uid = _make_user(client, phone="+22990000053")
    pkg = client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 30000, "currency": "XOF",
    }).json()
    assert pkg["quantity"] == 1
    assert pkg["duration_value"] is None and pkg["duration_unit"] is None


def test_portfolio_add_and_remove(client):
    uid = _make_user(client)
    media_id = client.post(f"/profiles/{uid}/media", files={"file": ("a.png", PNG_BYTES, "image/png")}).json()["id"]
    item = client.post(f"/profiles/{uid}/portfolio", json={"media_id": media_id})
    assert item.status_code == 201
    assert item.json()["url"] == f"/profiles/media/{media_id}"
    assert len(client.get(f"/profiles/{uid}/portfolio").json()) == 1
    assert client.delete(f"/profiles/{uid}/portfolio/{item.json()['id']}").status_code == 204
    assert client.get(f"/profiles/{uid}/portfolio").json() == []


def test_public_profile_aggregate(client):
    uid = _make_user(client)
    client.put(f"/profiles/influencer/{uid}", json={
        "display_name": "Ama K.", "bio": "Hi", "categories": ["fashion"], "rate_card": {"post": 1000},
    })
    client.post(f"/profiles/{uid}/packages", json={
        "platform": "instagram", "deliverable_type": "post", "title": "1 IG Post",
        "price_amount": 30000, "currency": "XOF",
    })
    pub = client.get(f"/profiles/influencer/{uid}/public")
    assert pub.status_code == 200
    body = pub.json()
    assert body["display_name"] == "Ama K."
    assert len(body["packages"]) == 1
    assert body["review_count"] == 0
    assert body["average_stars"] is None
    assert body["reviews"] == []
