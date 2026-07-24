# Security Readiness

Trust is the core promise of the platform, so security is a launch gate, not a later hardening pass. This list covers the minimum for a pilot handling identity documents and, once a provider is live, money.

## Authentication and access

- [ ] Replace the X-Admin-Id header placeholder with real admin authentication and role based access control before any admin touches production data. Owner: Backend. Launch blocker for admin operations.
- [ ] Enforce that the platform is for users 18 and over at registration. Owner: Backend.
- [ ] Password and OTP flows reviewed: rate limits in place, reset tokens expire, no user enumeration in error messages. Owner: Backend.
- [ ] JWT secret and the document encryption key are strong, unique per environment, and supplied via environment variables, never committed. Owner: DevOps.

## Data protection

- [ ] Identity documents remain encrypted at rest (Fernet) and access is limited and logged. Owner: Backend.
- [ ] Secrets are managed outside the repository (no keys, tokens, or provider credentials in git). Run secret scanning on the repo. Owner: DevOps.
- [ ] TLS enforced end to end. Owner: DevOps.
- [ ] Backups of the database are configured and a restore has been tested at least once. Owner: DevOps.

## Application security

- [ ] Dependency vulnerability scan on backend and web, with a plan to patch highs before launch. Owner: Engineering.
- [ ] Input validation and authorization checks reviewed on every write endpoint (a user cannot act on another user's campaign, contract, escrow, or message). Owner: Backend.
- [ ] Penetration test by an independent party covering auth, payments flow, and document access. Owner: Founder to commission. Launch blocker.
- [ ] Findings from the pen test triaged, with all high severity issues fixed and re-tested. Owner: Engineering.

## Monitoring and response

- [ ] Error monitoring and alerting in place for the backend. Owner: DevOps.
- [ ] A written incident response path: who is contacted, how users are informed, how a breach is handled. Owner: Founder plus engineering.

## Founder approval required

- [ ] Accept the residual risk profile after the pen test, or delay launch until specific items are closed.
