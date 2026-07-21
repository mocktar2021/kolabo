# Kolabo Architecture Notes

Summary of the decisions from Part 17 of the project initiation document.

## Principles

1. **Modular monolith, not microservices.** One deployable backend service for the MVP and pilot. Module boundaries (see `backend/app/modules/`) mirror the Jira epics so they can be extracted into separate services later only if load genuinely demands it.
2. **Country/language/currency/payment-provider are configuration data, not code.** See `backend/app/core/country_config.py`. Launching an 8th country should mean adding a config row plus a payment-provider integration, not rebuilding the platform.
3. **Mobile-first, low-bandwidth-first.** Paginate everything, compress images server-side, avoid over-fetching, design for mid/low-tier Android devices first.
4. **Trust is enforced by the platform, not assumed.** Escrow, verification, contracts, and ratings are core modules, not add-ons.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL |
| Web | React + TypeScript (Vite) |
| Mobile | React Native (Expo) — single codebase for iOS + Android |
| Auth | JWT + OTP (SMS gateway TBD — Africa's Talking / Termii under evaluation) |
| Payments | Mobile Money provider APIs behind an internal abstraction layer (`backend/app/modules/payments/`) |
| Hosting | TBD — AWS or GCP, single region to start |

## Module map (backend/app/modules/)

| Module | Jira epic |
|---|---|
| auth | KOL-1 |
| profiles | KOL-2 |
| discovery | KOL-3 |
| campaigns | KOL-11 |
| contracts | KOL-5 |
| messaging | KOL-6 |
| payments | KOL-7 |
| trust_safety | KOL-8 |
| admin | KOL-9 |

Launch-readiness work (legal, translation, security, ops — KOL-10) is process, not code, and isn't represented as a module.

## Open items

- Mobile Money provider selection per country (Part 18) — not yet finalized, `payments` module should stay provider-agnostic behind its abstraction layer.
- Backend hosting provider and region — not yet chosen.
- SMS gateway — not yet chosen.
