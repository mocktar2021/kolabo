from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import AppError, app_error_handler
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates tables from model metadata. Alembic migrations replace this in
    # Epic I (KOL-34).
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


app = FastAPI(
    title="Kolabo API",
    description="Bilingual influencer marketing marketplace for Africa",
    version="0.1.0",
    lifespan=lifespan,
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
