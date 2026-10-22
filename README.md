# Kolabo

Bilingual (EN/FR) influencer marketing marketplace for Africa — connecting verified creators and businesses across Benin, Togo, Ghana, Côte d'Ivoire, Cameroon, Nigeria, and Senegal.

Full project plan: see `docs/` and the [Kolabo Project Initiation Document] (kept in the project owner's Documents folder). Backlog lives in Jira project **KOL** at mocktarltd.atlassian.net.

## Repo layout (monorepo)

```
backend/   FastAPI modular monolith (Python) — see backend/README.md
web/       React web app (Vite + TypeScript)
mobile/    React Native app (Expo)
docs/      Architecture notes
```

## Architecture in one paragraph

Single deployable backend ("modular monolith") with module boundaries matching the Jira epics (auth, profiles, discovery, campaigns, contracts, messaging, payments, trust_safety, admin). Country, language, currency, and payment-provider behavior is driven by configuration data (`backend/app/core/country_config.py` + DB tables), not hardcoded logic — adding a new country should be a data change, not a code change. See `docs/ARCHITECTURE.md`.

## Status

Scaffold stage. MVP build tracked in Jira KOL, Epics A–J.

## Getting started

```bash
docker compose up --build
```

Brings up Postgres + the backend API on `localhost:8000`. See `backend/README.md`, `web/README.md`, `mobile/README.md` for per-app setup.

