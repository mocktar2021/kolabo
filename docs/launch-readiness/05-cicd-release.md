# CI/CD and Release Readiness

This covers how code gets from a pull request to the pilot environment safely, and how the database schema is managed now that migrations exist.

## Continuous integration

- [ ] CI runs on every pull request: backend tests (pytest) and web build. Already in place via GitHub Actions. Owner: DevOps.
- [ ] A pull request cannot merge to main with a failing CI check. Owner: DevOps. Set branch protection on main.
- [ ] At least one review approval required before merge to main. Owner: DevOps.

## Database migrations

- [ ] Alembic is the source of truth for the production schema (introduced in Epic I). Owner: Backend.
- [ ] The release process runs alembic upgrade head before the app starts serving. Owner: DevOps.
- [ ] Every schema change ships as a migration in the same pull request as the model change. Owner: Backend.
- [ ] A migration rollback path is understood for each release (downgrade or a forward fix). Owner: Backend.

## Environments and deployment

- [ ] A staging environment mirrors production configuration for a final check before launch. Owner: DevOps.
- [ ] Environment specific secrets (JWT secret, document encryption key, database URL, provider credentials) are set per environment and not shared. Owner: DevOps.
- [ ] A documented deploy and rollback runbook exists. Owner: DevOps.
- [ ] Health check endpoint is monitored after each deploy. Owner: DevOps.

## Housekeeping

- [ ] Delete stale branches after merge, including the initial default branch cleanup. Owner: Founder or DevOps.

## Founder approval required

- [ ] Approve branch protection rules on main.
