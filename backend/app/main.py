from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.contracts.router import router as contracts_router
from app.modules.discovery.router import router as discovery_router
from app.modules.messaging.router import router as messaging_router
from app.modules.notifications.router import router as notifications_router
from app.modules.payments.router import router as payments_router
from app.modules.profiles.router import router as profiles_router
from app.modules.trust_safety.router import router as trust_safety_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates tables from model metadata. Alembic migrations replace this in
    # Epic I (KOL-34).
    init_db()
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


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.env}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
app.include_router(discovery_router, prefix="/discovery", tags=["discovery"])
app.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
app.include_router(contracts_router, prefix="/contracts", tags=["contracts"])
app.include_router(messaging_router, prefix="/messaging", tags=["messaging"])
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(trust_safety_router, prefix="/trust-safety", tags=["trust_safety"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
