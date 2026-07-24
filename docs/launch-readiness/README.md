# Kolabo Launch Readiness

This folder holds the cross cutting work that has to be done before the Phase 1 pilot goes live. None of it is a product feature, which is why it lives here as checklists rather than as code stories. It maps to the go-live and readiness criteria in the Project Initiation Document (Part 4 MVP, Part 10 cross cutting tasks, Part 19 legal, Part 22 first 90 days).

## Pilot scope this readiness set covers

- Markets: Benin (BJ) and Togo (TG). Other markets stay disabled in country config until their own readiness pass is done.
- Languages: English and French, both required at launch.
- Platform: responsive web plus the two mobile apps, backend, and admin.

## The checklists

1. [Legal and compliance](01-legal-compliance.md)
2. [Translation and localization](02-translation-localization.md)
3. [Security](03-security.md)
4. [Support and operations](04-support-operations.md)
5. [CI/CD and release](05-cicd-release.md)
6. [Go-live checklist](06-go-live-checklist.md) (the single gate that pulls from all of the above)

## How to use this

Each checklist has an owner column and a status box. An item is done only when its evidence link is filled in (a signed document, a merged PR, a report, a screenshot). The go-live checklist is the final gate: the pilot does not launch until every blocking item there is checked, with the founder signing off on the decisions that are marked as needing founder approval.

## Standing open items that block full launch

These are known from the build and are tracked so they are not forgotten.

- Mobile Money provider per country is not selected yet. Real payments cannot run until one is chosen and integrated; the platform currently uses a mock provider. See the payment strategy in the project document.
- Admin access uses an X-Admin-Id header placeholder. Real admin authentication and role based access control must replace it before admins operate on production data.
- Contract and terms templates carry a clearly marked placeholder banner and have not been legally reviewed.
- Trademark clearance for the Kolabo name came back cautionary. An OAPI, Ghana, and Nigeria registry search through counsel is still open.
