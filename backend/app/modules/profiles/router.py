"""Epic B (KOL-2): Profiles and Verification, plus packages and profile media.

AUTHENTICATION, AND WHY THE PATH `user_id` IS NOW IGNORED ON WRITES.

Until this change every endpoint here identified the profile owner by the id in
the URL and asked for nothing else. There was no bearer token, no ownership
check, no dependency of any kind on seventeen endpoints — so an anonymous
request could rewrite any creator's profile, and, worse, their PACKAGE PRICES,
which is the number a brand pays at checkout. That is a money defect, not a
data one, and it was reachable by anyone who could guess a uuid.

The fix does not compare the path id against the token and refuse a mismatch.
It takes the owner from the token and never reads the path id at all, which is
a stronger property: a comparison can be forgotten on the eighteenth endpoint,
whereas an id that is never consulted cannot be spoofed on any of them. Acting
on somebody else is not refused here — it is unrepresentable.

The `{user_id}` segment stays in the route for URL compatibility, so no web or
mobile call site changes in this PR. It is now decoration. Removing it is a
follow-up that touches both clients and belongs in its own change.

WHAT IS DELIBERATELY LEFT PUBLIC, and it is not an oversight:

  * `GET /influencer/{user_id}/public` — the creator's storefront. Discovery is
    public because a storefront exists to be seen; requiring a token here would
    mean a brand had to sign up before it could look at anybody, which is the
    opposite of the funnel.
  * `GET /media/{media_id}` — serves the images those public pages reference.
  * The three list reads (`packages`, `portfolio`, `social-accounts`) — every
    one of them returns what the public profile already renders, so a token
    would buy nothing and would break the pages that read them.
  * `GET /oauth/{platform}/callback` — a redirect arriving from a social
    platform, which CANNOT carry a token. It is the only unauthenticated WRITE
    in this router, and it is authenticated by something else entirely; see the
    block at the bottom of this file.

`onboarding-status` is NOT in that list. "What is still missing before you can
go live" is a private answer about somebody's account, not part of the
storefront.
"""
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.modules.auth.deps import get_current_user_id
from app.modules.profiles import oauth_service, schemas, service

router = APIRouter()


def profile_owner(caller_id: str = Depends(get_current_user_id)) -> str:
    """The account being written to: always the bearer of the token.

    A one line indirection rather than using `get_current_user_id` directly,
    for two reasons. It names the rule at every call site — the parameter reads
    `owner_id: str = Depends(profile_owner)`, which says whose profile is being
    changed rather than merely who is calling. And it is the single seam the
    test suite overrides, so the 168 existing profile tests keep exercising
    profile BEHAVIOUR without each of them having to mint a token; see
    backend/conftest.py, and test_profiles_auth.py for the guard's own tests.
    """
    return caller_id


@router.put("/influencer/{user_id}", response_model=schemas.InfluencerProfileOut)
def upsert_influencer_profile(
    user_id: str,
    payload: schemas.InfluencerProfileIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Create or update an influencer profile. See KOL-15."""
    return service.upsert_influencer_profile(db, owner_id, payload)


@router.get("/influencer/{user_id}/public", response_model=schemas.PublicProfileOut)
def public_influencer_profile(user_id: str, language: str | None = None, db: Session = Depends(get_db)):
    """Public creator page: profile, packages, portfolio, rating, socials.

    Unauthenticated on purpose — see the module docstring.

    `language` (fr or en) picks which bio to show, falling back to the other
    when the creator has only filled one.
    """
    return service.get_public_profile(db, user_id, language)


@router.get("/influencer/{user_id}", response_model=schemas.InfluencerProfileOut)
def get_influencer_profile(
    user_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Load your own creator profile for editing.

    The editing view, not the storefront: `/public` above is what a visitor
    reads. A creator only ever loads their own here.
    """
    return service.get_influencer_profile(db, owner_id)


@router.put("/business/{user_id}", response_model=schemas.BusinessProfileOut)
def upsert_business_profile(
    user_id: str,
    payload: schemas.BusinessProfileIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Create or update a business profile."""
    return service.upsert_business_profile(db, owner_id, payload)


@router.get("/business/{user_id}", response_model=schemas.BusinessProfileOut)
def get_business_profile(
    user_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Load a business profile for editing.

    The profile was write-only until now: the PUT existed without a GET, so
    the settings page had nothing to prefill and came up blank on every visit.
    """
    return service.get_business_profile(db, owner_id)


@router.get("/media/{media_id}")
def serve_media(media_id: str, db: Session = Depends(get_db)):
    """Serve a stored profile image.

    Unauthenticated: these are the images the public creator pages render.
    """
    asset = service.get_media(db, media_id)
    return Response(content=asset.data, media_type=asset.content_type)


@router.post("/{user_id}/media", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    user_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Upload a profile image (avatar or portfolio)."""
    content = await file.read()
    return service.save_media(db, owner_id, file.content_type or "application/octet-stream", content)


@router.get("/{user_id}/packages", response_model=list[schemas.PackageOut])
def list_packages(user_id: str, active_only: bool = False, db: Session = Depends(get_db)):
    """List a creator's fixed-price packages. Public — the storefront shows these."""
    return service.list_packages(db, user_id, active_only)


@router.post("/{user_id}/packages", response_model=schemas.PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(
    user_id: str,
    payload: schemas.PackageIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    return service.create_package(db, owner_id, payload)


@router.put("/{user_id}/packages/{package_id}", response_model=schemas.PackageOut)
def update_package(
    user_id: str,
    package_id: str,
    payload: schemas.PackageIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    return service.update_package(db, package_id, owner_id, payload)


@router.delete("/{user_id}/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    user_id: str,
    package_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    service.delete_package(db, package_id, owner_id)


@router.get("/{user_id}/portfolio", response_model=list[schemas.PortfolioItemOut])
def list_portfolio(user_id: str, db: Session = Depends(get_db)):
    """Public — the storefront renders these."""
    return service.list_portfolio(db, user_id)


@router.post("/{user_id}/portfolio", response_model=schemas.PortfolioItemOut, status_code=status.HTTP_201_CREATED)
def add_portfolio_item(
    user_id: str,
    payload: schemas.PortfolioItemIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    return service.add_portfolio_item(db, owner_id, payload.media_id)


@router.delete("/{user_id}/portfolio/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_portfolio_item(
    user_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    service.remove_portfolio_item(db, item_id, owner_id)


@router.post(
    "/{user_id}/verification-documents",
    response_model=schemas.VerificationDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_verification_document(
    user_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Upload a verification document, stored encrypted with status pending. KOL-16.

    The one endpoint here where the old behaviour was worst: an identity
    document could be filed against somebody else's account by anybody.
    """
    content = await file.read()
    return service.upload_verification_document(db, owner_id, doc_type, file.filename, content)


@router.post("/{user_id}/bio/generate", response_model=schemas.BioGenerateOut)
def generate_bio(
    user_id: str,
    payload: schemas.BioGenerateIn,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Draft a bio in French or English from the creator's own profile facts.

    Returns a draft; nothing is written to the profile until the creator saves.
    Authenticated also because it is rate limited per account and costs money
    to serve — an open endpoint that spends is an endpoint that gets spent.
    """
    return service.generate_bio(db, owner_id, payload)


@router.get("/{user_id}/social-accounts", response_model=list[schemas.SocialAccountOut])
def list_social_accounts(user_id: str, db: Session = Depends(get_db)):
    """Social accounts connected to this profile. Public — the storefront shows them."""
    return service.list_social_accounts(db, user_id)


@router.get("/{user_id}/onboarding-status", response_model=schemas.OnboardingStatusOut)
def onboarding_status(
    user_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """What is still missing before the creator profile can go live.

    Private, unlike the three lists above: this is a checklist about somebody's
    account, not part of what a visitor is shown.
    """
    return service.onboarding_status(db, owner_id)


@router.post(
    "/{user_id}/social-accounts",
    response_model=schemas.SocialAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def connect_social_account(
    user_id: str,
    payload: schemas.SocialAccountConnect,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Connect a social account. KOL-17.

    Every connection starts PENDING, whatever `method` the client sends: OAuth
    is not built, so it cannot verify anything. The badge comes from admin
    review — see service.connect_social_account.
    """
    return service.connect_social_account(db, owner_id, payload)


@router.put("/{user_id}/social-accounts/{account_id}", response_model=schemas.SocialAccountOut)
def update_social_account(
    user_id: str,
    account_id: str,
    payload: schemas.SocialAccountUpdate,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Edit a connected account. Changing the handle of a verified account
    resets it to pending: the badge was earned by the old handle."""
    return service.update_social_account(db, owner_id, account_id, payload)


@router.delete("/{user_id}/social-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_social_account(
    user_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Disconnect a social account from the profile."""
    service.delete_social_account(db, owner_id, account_id)


# --------------------------------------------------------------------------
# OAuth: connecting an account the platform itself vouches for.
#
# TWO ROUTES WITH DELIBERATELY DIFFERENT AUTHENTICATION, which is the whole
# reason this block carries a comment rather than sitting quietly above.
#
#   `start` is the ordinary rule of this router: the account being connected is
#   the bearer of the token, taken from `profile_owner`, and no path id is
#   consulted. That is where the handshake's identity is DECIDED, and it is the
#   only step at which a token exists.
#
#   `callback` cannot be authenticated and never will be. It is a redirect the
#   platform sends the creator's BROWSER to, so there is no Authorization
#   header to read: everything about the request is attacker-controllable
#   except the state row it names. What stands in for a token is that row —
#   unguessable, single-use, ten minutes long — and the identity it carries is
#   the one `start` wrote there under a real token. See
#   oauth_service.complete_authorization and models.OAuthState.
#
# THAT MAKES main.py's CLAIM ABOUT WEBHOOKS WRONG, and it was already wrong
# before this change: the comment above the webhook router calls it "THE ONLY
# UNAUTHENTICATED WRITE PATH IN THE API" while several unauthenticated reads
# and the whole public storefront sit in this file. This route makes it a
# second unauthenticated WRITE, so the comment is corrected in the same PR
# rather than left to age — a comment that names an invariant is only worth
# anything while it is true.
#
# ROUTE ORDER: both begin with the literal segment `oauth`, so none of the
# `/{user_id}/...` routes above can shadow them (a two-segment pattern cannot
# match a three-segment path, and `/{user_id}/bio/generate` needs `bio` in the
# middle). They sit at the bottom because they are new, not because the order
# matters.
# --------------------------------------------------------------------------


@router.post("/oauth/{platform}/start", response_model=schemas.OAuthStartOut)
def start_social_oauth(
    platform: str,
    payload: schemas.OAuthStartIn | None = None,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Begin connecting a social account: mint a state row, return where to go.

    Answers `oauth_platform_unsupported` for every platform today, because no
    provider has credentials or an approved developer app — see
    oauth.build_default_providers. That is the honest answer: a redirect to a
    URL that will bounce would be worse.

    The body is optional; it carries only `redirect_to`.
    """
    return oauth_service.start_authorization(
        db, owner_id, platform, payload.redirect_to if payload else None
    )


@router.get("/oauth/{platform}/callback", response_model=schemas.OAuthCallbackOut)
def finish_social_oauth(
    platform: str,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Finish the handshake the platform is redirecting a creator back from.

    UNAUTHENTICATED BY NECESSITY, and identified entirely by `state`. No token
    is read, no caller identity is consulted, and passing one would change
    nothing: whose profile the account lands on was decided by `start` and is
    written on the state row. A creator holding somebody else's callback URL
    connects an account to THEM, not to themselves — which is why the state has
    to be unguessable and is spent on first use.

    TWO ANSWERS, AND WHICH ONE ARRIVES DEPENDS ENTIRELY ON WHETHER THERE IS
    SOMEWHERE TO SEND THE CREATOR. Whoever reaches this route is sitting in a
    browser at the end of a consent screen, so when `start` was given an
    allowlisted `redirect_to` they get a 302 back to it, carrying
    `connected=<platform>` when it worked and `social_error=<code>` when it did
    not. When there is none they get exactly the JSON body this route has
    always returned. Until this change there was no client to go back to, so
    everybody got the JSON and a creator finishing a Facebook consent screen
    landed on a page of it.

    KEEPING THE JSON PATH IS THE DESIGN, not a leftover. It is what makes this
    additive: no existing caller sends a `redirect_to`, so no existing caller
    sees a redirect, every test written against the old contract still
    describes it, and the two clients opt in one at a time by starting to send
    one.

    A FAILURE REDIRECTS TOO, when there is a destination to redirect to.
    Declining a permission on the consent screen is an ordinary thing to do,
    and answering it with a JSON error page is the same defect as answering a
    success with one. The code in the query string is the AppError's own, so
    the client shows the sentence it already has; no error code is invented for
    this feature, and none needed adding to either translation catalogue.
    """
    try:
        result = oauth_service.complete_authorization(db, platform, code, state)
    except AppError as exc:
        target = oauth_service.failure_redirect(db, platform, state, exc.code)
        if target is None:
            raise
        return RedirectResponse(target, status_code=status.HTTP_302_FOUND)

    target = oauth_service.success_redirect(result["redirect_to"], platform)
    if target is None:
        # No destination, or one on a row old enough to predate the allowlist
        # and carrying something we will not honour. Either way the answer is
        # the JSON body, and it does not echo back a destination this API has
        # just declined to send anybody to.
        result["redirect_to"] = None
        return result
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


# --------------------------------------------------------------------------
# Choosing which Page a Facebook connection is actually selling.
#
# BOTH AUTHENTICATED, on the ordinary rule of this router: the creator is the
# bearer of the token, through `profile_owner`, and no path id is consulted.
# Unlike the callback above there is nothing unusual to say about these two.
# They are ordinary profile writes that happen to read a platform on the way.
#
# ROUTE ORDER: both start with the literal segment `oauth`, so no
# `/{user_id}/...` route above can shadow them. The list is three segments and
# the only three-segment patterns above need a literal `packages`, `portfolio`
# or `social-accounts` in the middle; the select is four segments, and nothing
# else in this router has four.
#
# `page_id` IS IN THE PATH AND IS STILL NOT TRUSTED. Where it travels says
# nothing about whether it is true. oauth_service.select_page re-reads the
# creator's own Page list with the creator's own stored token and matches
# against that, which is the only thing that makes the id mean anything.
# --------------------------------------------------------------------------


@router.get("/oauth/{platform}/pages", response_model=list[schemas.SocialPageOut])
def list_oauth_pages(
    platform: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """The Pages this creator manages on a platform, read live from it.

    NOT PUBLIC, unlike the three list reads further up this file. Those return
    what the storefront already renders. This returns every Page somebody
    manages, including the ones they have decided not to sell on and a client's
    account they merely administer, which is nobody's business but theirs.

    Read live rather than stored, because a stored list goes stale in exactly
    the way that matters: a Page somebody lost access to last week must not
    still be selectable today.
    """
    return oauth_service.list_pages(db, owner_id, platform)


@router.post(
    "/oauth/{platform}/pages/{page_id}", response_model=schemas.SocialAccountOut
)
def select_oauth_page(
    platform: str,
    page_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(profile_owner),
):
    """Record which Page this creator sells on, and its follower count with it.

    A POST rather than a PUT on the account, because the thing being named is
    the PAGE and the account row is where the answer lands. The creator is
    choosing one of several offers, not editing a field.

    Answers the updated account, so a client can render the new handle and the
    new follower count without a second request.
    """
    return oauth_service.select_page(db, owner_id, platform, page_id)
