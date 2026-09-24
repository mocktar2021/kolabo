from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.modules.admin.router import router as admin_router
from app.modules.auth.admins import sync_admins
from app.modules.auth.router import router as auth_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts.router import router as contracts_router
from app.modules.deliverables.router import router as deliverables_router
from app.modules.discovery.router import router as discovery_router
from app.modules.messaging.router import router as messaging_router
from app.modules.notifications.router import router as notifications_router
from app.modules.payments.gateway_router import router as payments_gateway_router
from app.modules.payments.router import router as payments_router
from app.modules.payments.webhooks import router as payment_webhooks_router
from app.modules.profiles.router import router as profiles_router
from app.modules.trust_safety.router import router as trust_safety_router

# THE API CONFIGURED NO LOGGING AT ALL, and every `_log.info` in this codebase
# was being thrown away because of it. Uvicorn sets levels on its OWN loggers
# ("uvicorn", "uvicorn.error", "uvicorn.access") and leaves the root logger
# alone, so an application logger with no handler falls through to Python's
# last-resort handler: WARNING and above, written to stderr with no timestamp,
# no level and no logger name.
#
# That is not a tidiness complaint. oauth.MetaOAuthProvider.read_audience logs
# "Meta connection manages %d Pages, so no follower count was recorded" at
# INFO, which is the one line that explains the bug this PR fixes, and it has
# never once reached a log file. Diagnosing a creator with four Pages and no
# follower count took a database query because of this, and the next
# best-effort path that declines to guess will be just as invisible.
#
# The same three arguments app/jobs/sweeps.py already passes, so the API
# container and the job container format their lines identically.
#
# THOSE ARGUMENTS NOW LIVE IN app.core.logging, ALONG WITH A SECOND ONE THIS
# FILE LEARNED THE HARD WAY. Turning application logging on here also turned on
# httpx's own per-request INFO record, which carries the full request url; every
# credential Kolabo sends to Meta or to Google travels as a QUERY PARAMETER, so
# every SUCCESSFUL outbound call was writing one out in clear text. That is not
# the error-path bug #183 fixed, it is the success path, and it fires every time
# rather than only when something breaks.
#
# The answer is not to turn logging back off. configure_logging() applies
# exactly the level and the format that used to be spelled out here, and then
# holds the HTTP client loggers at WARNING so their per-request chatter stops.
# Both entrypoints ask for it rather than each keeping a copy, so that the next
# fix cannot land in one process and miss the other. READ THAT MODULE'S
# DOCSTRING BEFORE RAISING ANY LOG LEVEL.
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NO LONGER CREATES ANY SCHEMA. `alembic upgrade head` in the container
    # command is the only thing that builds tables now; this seeds the country
    # table and configures the mappers. See app/core/db.py for why create_all
    # leaving here was a correctness fix and not a tidy-up.
    init_db()
    # Then make the admin list in the database agree with the configured one.
    # On EVERY boot, and it revokes as well as grants: removing somebody's
    # admin access is deleting their number and redeploying, not remembering
    # to also go and edit a row. See app.modules.auth.admins.
    db = SessionLocal()
    try:
        sync_admins(db)
    finally:
        db.close()
    yield


# OPENAPI DOCS ARE OFF IN PRODUCTION, and this is the third behaviour to hang
# off ENV rather than the first. auth/otp.py prints every OTP code to the logs
# when ENV is "development" and gateway_router advertises mock payments when ENV
# is not "production"; a box whose ENV is wrong is already in trouble, and this
# adds one more reason to get it right rather than a new kind of risk.
#
# WHAT IS ACTUALLY AT STAKE. /docs and /openapi.json publish every route, every
# request schema and every field name in the API, including the admin surface
# and the payout endpoints, to anyone who asks for the URL. None of that is a
# secret in the sense that knowing it grants access, and all of it is a map:
# the fastest way to find the one endpoint whose authorization is weaker than
# its neighbours is to read the list. The API is bilingual and public-facing,
# so the list is worth something to somebody.
#
# NOT SECURITY BY OBSCURITY IN PLACE OF AUTHORIZATION. Every route keeps the
# authorization it had. This removes a free index of them.
#
# openapi_url has to go too, not just docs_url. FastAPI serves the schema from
# its own path, and leaving it reachable while hiding the two HTML viewers is
# the version of this change that looks done and is not.
_docs_enabled = settings.env != "production"

app = FastAPI(
    title="Kolabo API",
    description="Bilingual influencer marketing marketplace for Africa",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Allow the browser based web app to call the API cross origin. Origins are
# configured via settings so dev and production can differ without code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A refusal that names itself, so the client can say it in the reader's own
# language. Registered for AppError only: Starlette walks the raised
# exception's MRO and takes the first handler it finds, so an AppError lands
# here while every un-migrated `raise HTTPException` keeps going to FastAPI's
# own handler and keeps its current response byte for byte. That is what lets
# the 200-odd refusals in this codebase move over one module at a time. See
# app/core/errors.py.
app.add_exception_handler(AppError, app_error_handler)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.env}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
app.include_router(discovery_router, prefix="/discovery", tags=["discovery"])
app.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
app.include_router(contracts_router, prefix="/contracts", tags=["contracts"])
app.include_router(deliverables_router, prefix="/deliverables", tags=["deliverables"])
app.include_router(messaging_router, prefix="/messaging", tags=["messaging"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
# A SECOND ROUTER ON THE SAME PREFIX, carrying checkout, payout methods and the
# payout sweep. payments/router.py is about the platform's own view of money —
# escrow, disputes, statements — and payments/gateway_router.py is about the
# conversation with an outside gateway. They came in together and they will
# change together; FastAPI does not mind sharing a prefix, and one 350-line
# router would have hidden the seam.
app.include_router(payments_gateway_router, prefix="/payments", tags=["payments"])
# ONE OF THE TWO UNAUTHENTICATED WRITE PATHS IN THE API, and mounted at the top
# level rather than under /payments to make that obvious in the route table.
#
# THIS COMMENT USED TO SAY "THE ONLY", and that was wrong twice over. It was
# already wrong about reads — the whole public creator storefront and three
# list endpoints in profiles/router.py answer with no token at all — and it is
# now wrong about writes: GET /profiles/oauth/{platform}/callback creates a
# social account and stores credentials without one. Both of those requests
# arrive from somewhere that cannot hold a bearer token, and each stands on
# something else instead:
#
#   * the gateway webhooks below: an HMAC signature over the raw body, a replay
#     window and an idempotency key, all in payments/webhooks.py. The caller is
#     a machine at FedaPay, and the signature is what says so.
#   * the OAuth callback: a state row that is unguessable, single-use and ten
#     minutes old at most, carrying the user id that a real token wrote when
#     the creator STARTED the authorization. See
#     profiles/oauth_service.complete_authorization.
#
# Anything that joins this list needs its own answer to "what stands in for the
# token", written down where somebody auditing the route table will find it.
app.include_router(payment_webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(trust_safety_router, prefix="/trust-safety", tags=["trust_safety"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
