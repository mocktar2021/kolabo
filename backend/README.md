# Kolabo backend

FastAPI modular monolith. See `../docs/ARCHITECTURE.md` for the reasoning behind the structure.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Or via Docker from the repo root: `docker compose up --build`.

## Structure

```
app/
  main.py              FastAPI app factory, mounts all module routers
  core/
    config.py          App-wide settings (env-driven)
    country_config.py  Country/currency/payment-provider/phone-format config — data, not hardcoded logic
  modules/
    auth/
    profiles/
    discovery/
    campaigns/
    contracts/
    messaging/
    payments/
    trust_safety/
    admin/
```

Each module has its own `router.py` (API endpoints), `schemas.py` (Pydantic models), and `service.py` (business logic) — kept separate so modules stay swappable/extractable later without cross-module coupling.
