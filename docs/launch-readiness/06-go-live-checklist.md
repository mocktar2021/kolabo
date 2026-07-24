# Go-Live Checklist (Phase 1 Pilot: Benin and Togo)

This is the single gate. The pilot does not launch until every blocking item below is checked. Each line points back to the detailed checklist that owns it. Blocking items are marked BLOCKER.

## Legal (see 01-legal-compliance.md)

- [ ] Terms of Service and Privacy Policy reviewed by counsel, live in EN and FR. BLOCKER
- [ ] Influencer, business, and contract templates reviewed by counsel; placeholder banner removed only after sign off. BLOCKER
- [ ] Payment licensing question answered for Benin and Togo (license, licensed partner, or defer real payments). BLOCKER
- [ ] Data protection registration or notification duties confirmed and actioned. BLOCKER
- [ ] 18 and over restriction confirmed enforceable and enforced.

## Translation (see 02-translation-localization.md)

- [ ] Full EN and FR coverage across web, mobile, notifications, and contracts. BLOCKER
- [ ] Native French review complete for pilot markets. BLOCKER
- [ ] Currency, phone, and date formats correct for BJ and TG.

## Security (see 03-security.md)

- [ ] Real admin authentication and RBAC replace the X-Admin-Id placeholder. BLOCKER
- [ ] Independent penetration test completed and all high severity findings fixed and re-tested. BLOCKER
- [ ] Secrets managed outside git; secret scanning clean; TLS enforced. BLOCKER
- [ ] Database backups configured and a restore tested. BLOCKER
- [ ] Error monitoring and an incident response path in place.

## Payments (see project payment strategy)

- [ ] Mobile Money provider selected and integrated for BJ and TG, replacing the mock provider. BLOCKER
- [ ] End to end money test passed on the real provider in a controlled way (fund, release with commission, refund).
- [ ] Commission rate confirmed per market.

## Support and operations (see 04-support-operations.md)

- [ ] Support channels published in EN and FR with hours and response times. BLOCKER
- [ ] SOPs written for verification, disputes, fraud reports, and payouts. BLOCKER
- [ ] Escalation path to founder defined.

## Release (see 05-cicd-release.md)

- [ ] Branch protection on main with passing CI and one approval required. BLOCKER
- [ ] Staging validated; deploy and rollback runbook in place; migrations run on release. BLOCKER

## Product acceptance

- [ ] The full pilot loop passes on staging: register, verify, discover, create campaign, invite, propose, contract and e-sign, message, fund escrow, deliver, release payment, review, and report. BLOCKER
- [ ] Recruited pilot cohort ready (a small set of influencers and businesses per the rollout plan).

## Founder sign off

- [ ] Founder has reviewed all BLOCKER items and the residual risk, and approves go-live.
- [ ] Success criteria and the post launch review date are set (see Part 4 and Part 22 of the project document).
