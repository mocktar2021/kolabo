# Deploying a Kolabo environment

One VPS, Docker Compose, Caddy for TLS.

**Nothing in `deploy/` names an environment any more.** Both hostnames come from `WEB_HOSTNAME` and `API_HOSTNAME` in `deploy/.env`, which is per box and gitignored, so the same branch and the same compose file stand up the dev box and production. `deploy/Caddyfile` used to spell out `kolabo.mocktar.com`, and because it is tracked in git and bind mounted read only into the container, that one fact was the whole reason a second environment could not exist: the only ways to change it were to edit a tracked file on the server, which the next `git pull` silently reverts and takes TLS down with it, or to fork the deploy directory.

This page is written from the dev box as the worked example. Substitute your own two hostnames and it describes any environment; `claude/kolabo-production-setup-runbook.md` covers what production additionally needs.

| | dev box, as an example |
|---|---|
| Web | `https://kolabo.mocktar.com` (`WEB_HOSTNAME=kolabo.mocktar.com`) |
| API | `https://api.kolabo.mocktar.com` (`API_HOSTNAME=api.kolabo.mocktar.com`) |
| Payments | **FedaPay sandbox only.** No real money can move. |

**One command brings an environment up, on every box:**

```bash
cd kolabo/deploy && bash up.sh
```

`up.sh` runs `checks/preflight-env.sh` first and stops if it refuses, then composes. Five URLs in `deploy/.env` have to agree with the two hostnames, and each of them has been wrong at least once with no error message anywhere, so the check is inside the command rather than beside it in this file. The preflight refuses on anything empty, on a hostname carrying a scheme or a port, and on `CORS_ORIGINS`, `API_PUBLIC_BASE_URL`, `WEB_PUBLIC_BASE_URL`, `PAYMENT_RETURN_URL` or `VITE_API_URL` disagreeing with the pair. Run it on its own any time:

```bash
bash checks/preflight-env.sh
```

**The dev box is a development environment on a public hostname.** Those two facts pull in opposite directions: it is reachable by anyone, and it is configured for convenience. Everything under "Before you start" exists because of that tension, in particular the two committed default secrets, which protect nothing until you replace them. A production box is the same stack with `ENV=production`, which turns off the OTP codes in the logs, the mock payment fallback and the OpenAPI docs, and makes `config.py` refuse to boot on either committed default secret.

---

## 1. Why HTTPS is a requirement, not a nicety

You cannot test the payment flow on `localhost`. FedaPay redirects the payer back to `PAYMENT_RETURN_URL` and POSTs webhooks to `/webhooks/fedapay`, and both must be publicly reachable HTTPS URLs with a valid certificate. That is the main thing this deployment buys you.

Caddy obtains and renews the certificates from Let's Encrypt automatically — no certbot, no cron, no renewal to forget.

---

## 2. Before you start — the four secrets that matter

`backend/app/core/config.py` ships working defaults so a laptop runs with no setup. Two of them are real credentials committed to a git repository:

| Variable | Committed default | Why it matters on a public host |
|---|---|---|
| `JWT_SECRET` | `change-me` | Signs every session token. Anyone who has read this repo can forge a token for any account, **including an admin**. |
| `DOCUMENT_ENCRYPTION_KEY` | a real Fernet key | Encrypts verification documents at rest. Unchanged, the encryption is decorative. |
| `POSTGRES_PASSWORD` | `kolabo` | Not published to the host here, but it is the credential for every user and payment row. |
| `ADMIN_EMAILS` | empty | Empty means **nobody** is an admin. Safe by default, but you cannot resolve a dispute or trigger a sweep by hand until it is set. It holds the email addresses those accounts registered with; it was called `ADMIN_PHONES` before the email address became the login identity, and an `.env` still carrying the old name is **ignored rather than rejected**, which reads as an empty list and revokes every admin at the next boot. |

Generate them:

```bash
openssl rand -hex 32                                                    # JWT_SECRET
openssl rand -base64 24                                                 # POSTGRES_PASSWORD
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # DOCUMENT_ENCRYPTION_KEY
```

---

## 3. DNS

Two A records at your registrar, both pointing at the VPS's public IPv4:

```
kolabo.mocktar.com.      A    <server-ip>
api.kolabo.mocktar.com.  A    <server-ip>
```

Add `AAAA` records too if the box has IPv6. **Let DNS propagate before the first `up`** — Caddy asks Let's Encrypt for certificates on boot, and the HTTP-01 challenge fails if the name does not yet resolve to this machine. Let's Encrypt rate-limits to **5 failures per hostname per hour** and 5 certificates per week, which is easy to burn through while debugging.

Check first:

```bash
dig +short kolabo.mocktar.com api.kolabo.mocktar.com
```

---

## 4. Server preparation

A 2 GB / 1 vCPU box is enough (Hetzner CX22, DO basic, Contabo VPS S). Debian 12 or Ubuntu 24.04.

```bash
# Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh

# Only 80, 443 and SSH should be open. Nothing else in the stack publishes a
# port — Postgres in particular is reachable only on the compose network.
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

---

## 5. First deploy

```bash
git clone https://github.com/mocktar2021/kolabo.git
cd kolabo/deploy
bash bootstrap-env.sh   # generates the three secrets into a new .env, mode 600
$EDITOR .env            # ENV, the two hostnames, the five URLs, FedaPay keys

bash up.sh              # preflights, refuses if wrong, then builds and starts
docker compose -f docker-compose.prod.yml logs -f
```

The first build takes a few minutes (the web image runs `tsc && vite build`, so a type error fails the build rather than shipping a broken bundle). Watch for Caddy reporting `certificate obtained successfully` for both hostnames.

> **`deploy/.env` is the one the server reads**, not `backend/.env`. The prod compose injects it through `env_file:` into the `backend` **and** `sweeps` containers. Editing `backend/.env` on your laptop changes nothing about what this box serves — and the symptom is `/payments/config` answering `"enabled": false` while you stare at a file that looks correct.

### What each service does

| Service | Role |
|---|---|
| `db` | Postgres 16. **No host port** — not on the public internet. |
| `backend` | `alembic upgrade head`, then uvicorn. Migrations run on every start; Alembic is idempotent. |
| `sweeps` | The four money jobs on a timer. See §8 — without it the money path is incomplete. |
| `web` | nginx serving the built SPA, with the fallback that makes `/checkout/return` work. |
| `caddy` | TLS for both hostnames. The only service that publishes ports. |

### If this box fronts more than Kolabo

The dev box's `caddy` is the shared TLS edge for three products: Kolabo's two hostnames plus FastaNow's three and Educazzi's three. **That arrangement is supported and none of it lives in this repository.**

Two per box pieces, both gitignored:

| Piece | What it does |
|---|---|
| `deploy/caddy-extra/*.caddy` | Site blocks for the other products. The last line of `deploy/Caddyfile` is `import /etc/caddy/extra/*.caddy`, and the directory is mounted read only into the container. `00-placeholder.caddy` is tracked and only exists so the glob always matches something. |
| `deploy/docker-compose.local.yml` | Puts caddy on the other projects' network, so `reverse_proxy api:8000` in those blocks resolves. Copy it from the `.example`. `up.sh` includes it automatically; a box without it behaves exactly as before. |

The network cannot go in `docker-compose.prod.yml`, because `external: true` makes compose refuse to start anything at all where that network does not exist, which is every other box.

**How this used to work, and why it stopped.** The extra site blocks were added straight into the tracked `Caddyfile` on the server, three separate times. `git pull` then refused to run, and the first deploy that forced past that refusal would have replaced an eight hostname config with a two hostname one and taken two other products offline, with nothing in this repository able to hint that they existed.

**Validate before you reload, because a bad config here takes down every product on the box**, not only Kolabo. This reads the same two mounts the real container gets and touches nothing that is running:

```bash
cd kolabo/deploy
docker run --rm --env-file .env \
  -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$PWD/caddy-extra:/etc/caddy/extra:ro" \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Caddy resolves an upstream container name when a request arrives rather than when the config loads, so a block naming a container on a network caddy has not joined validates and starts fine, and answers 502. A 502 on one product's hostname with the others healthy means the network, not the Caddyfile.

---

## 6. FedaPay dashboard setup

Do this at [sandbox.fedapay.com](https://sandbox.fedapay.com). All of it is on their side, none of it is in code.

1. Copy the sandbox **secret** and **public** keys into `deploy/.env`.
2. Add a webhook. The form has more on it than the URL, and three of the defaults are wrong for us:
   - **URL** `https://api.kolabo.mocktar.com/webhooks/fedapay`
   - **Type d'événements → "Recevoir tous les événements".** FedaPay's documentation does not enumerate the `payout.*` events at all, so a hand-picked list risks silently missing the notifications that say a creator was paid. Receiving everything is safe by construction: `webhooks.py` records and acknowledges event types it does not act on rather than erroring, which also turns `gateway_events` into a complete delivery log.
   - **"Désactiver la vérification SSL sur les requêtes HTTP ?" → off.** Caddy serves a real Let's Encrypt certificate. There is no reason to let FedaPay skip validating it, and this is a payments webhook.
   - **"Désactiver le webhook lorsque l'application génère des erreurs ?" → off.** Leave it on and FedaPay switches the endpoint off the first time it sees errors — which it will during setup, because every delivery returns 400 until `FEDAPAY_WEBHOOK_SECRET` is set. In production it is worse: this webhook is the safety net for a payer who pays and then closes the tab, so a transient outage auto-disabling it means escrows that silently never fund.
   - **Entêtes http → none.** Authentication is the HMAC signature over the raw body; a custom header would not be covered by it and would add nothing.
   - Copy the endpoint secret into `FEDAPAY_WEBHOOK_SECRET`. It is prefixed **`wh_`** (with the environment in it, e.g. `wh_sandbox…`) and is retrievable at any time from the webhook's own view via **Copy key** — it is not a one-time reveal.
3. **Préférences → Frais: turn both fee options off.** With "frais à la charge du client" on, FedaPay adds its own fee to the payer's total — a 25,000 XOF contract is presented as 26,042 — and `checkout.settle_intent` compares what arrived against what was asked for and refuses the difference. The payment succeeds at FedaPay and **no escrow is created**, which looks exactly like a bug in the app. Turning it off means the fee comes out of the merchant balance instead, which is the correct behaviour here and changes the platform's effective commission — see *Where the commission actually is* in `docs/PAYMENTS_FEDAPAY.md`.
4. `docker compose -f docker-compose.prod.yml up -d backend sweeps` to pick up the new values.

> `FEDAPAY_WEBHOOK_SECRET` is **not** `FEDAPAY_SECRET_KEY`. They are different values from different screens, and signing with the wrong one rejects every webhook with an error that reads like a network fault rather than a configuration one.

> **Nothing reports a missing webhook secret.** `GET /payments/config` derives `enabled` from the secret key alone and never mentions the webhook secret, so the deployment looks entirely healthy until the first webhook arrives and is rejected. Check it directly — see §7.

**There is no domain to whitelist.** An earlier version of this section said `kolabo.mocktar.com` had to be whitelisted under the account's allowed domains, and called that the single most common first-launch failure. It was wrong, and it sent somebody looking for a screen that does not exist. Verified 27 August 2026 against FedaPay's documentation: `callback_url` is sent **per transaction** in the create-transaction call, is documented as **optional**, and needs no pre-registration anywhere. The dashboard's sections are Accueil, Clients, Collectes, Remboursements, Retenues, Page de Paiement, Paiement, Paramètres d'Entreprise, Préférences, Gestion des Utilisateurs, API keys and Webhooks et Évènements — there is no allowed-domains screen among them.

---

## 7. Verify

```bash
curl https://api.kolabo.mocktar.com/health
# {"status":"ok","env":"development"}

curl https://api.kolabo.mocktar.com/payments/config
# {"enabled":true,"public_key":"...","sandbox":true,
#  "countries":["BJ","CI","TG"],"mock_payments":false}
```

`"enabled": false` with `"countries": []` means `FEDAPAY_SECRET_KEY` did not reach the **container**. Work inward — whichever of these first comes back empty is the answer:

```bash
grep -E '^FEDAPAY_' .env | sed 's/=.\+/=<set>/'                     # the file
docker compose -f docker-compose.prod.yml exec backend \
  printenv | grep -E '^FEDAPAY_' | sed 's/=.\+/=<set>/'             # the container
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.core.config import settings; print(bool(settings.fedapay_secret_key))"
```

Set in the file but not in the container means it was not recreated: settings are read at import, and Compose does not always recreate on an `env_file` change. `up -d --force-recreate backend sweeps`. Two formatting traps survive the first check unnoticed — **no spaces around `=`** (`KEY = value` makes the key `KEY␣`, which never matches) and **no quotes or inline comments** on the value.

And the one `/payments/config` cannot tell you:

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.core.config import settings; print('webhook secret:', bool(settings.fedapay_webhook_secret))"
```

Then walk the money path end to end:

| Step | Expected |
|---|---|
| Brand funds a signed contract, pays with **`0166000001`** | Return page settles, escrow `held` |
| Same, with **`0166000000`** — or any number that is not one of the two below | Intent `failed`, **`GET /payments/escrow/by-contract/{id}` → 404**. No escrow is the correct outcome. |
| Creator saves a wallet at `/settings/payouts` (`mtn_open`, `0166000001`) | Masked number shown back |
| Creator submits a deliverable, brand approves | Escrow `released`, `Payout` row `sent` |
| Approve with no wallet saved | Escrow still `released`, payout `awaiting_method` — owed, tracked, paid by the sweep once they add one |

### Sandbox numbers: exactly two succeed

FedaPay's sandbox runs a single **`momo_test`** operator rather than per-network test numbers, and its documentation is explicit:

> Scénario de succès : utilisez uniquement les numéros **64000001** et **66000001**

**Any other number fails.** There is no "insufficient funds" code, no "processing error" code, and no per-operator pattern — failure is simply the default for everything that is not one of those two.

Enter them with Benin's `01` prefix, because the hosted checkout page expects a full ten-digit national number:

| Number | Outcome |
|---|---|
| **`0166000001`** | success — **confirmed against this deployment, 28 August 2026** |
| `0164000001` | success (documented; not yet exercised here) |
| `0166000000`, or anything else | failure |

> An earlier version of this section listed `97000000` / `97000002` and a "processing error / insufficient funds" scheme. **No such numbers or scheme are documented by FedaPay** — that text came from an unverified source, and it cost a real hour at a checkout page that kept declining. If a number here is ever changed, change it because a payment was actually run with it.

Watch a payment arrive:

```bash
docker compose -f docker-compose.prod.yml logs -f backend | grep -i -E "webhook|intent|payout"
```

---

## 8. The sweeps container

Four jobs run every `SWEEP_INTERVAL_SECONDS` (default 300): auto-release, non-delivery refunds, dispute escalation, and **payout retries**.

That last one is why this container exists. `payments/payouts.py` is built so a network failure cannot fail a release — the escrow releases, the creator is owed, and a `FAILED` payout row is left for a sweep to retry. With nothing running the sweep, that is a promise nothing keeps: the creator stays owed forever and **no error appears anywhere**. The design only works if something runs it.

```bash
docker compose -f docker-compose.prod.yml logs -f sweeps
```

A quiet pass logs nothing at INFO — that is deliberate, so the pass that actually moved money is not buried under a hundred that did not.

**Not yet included:** the campaigns order-expiry job behind `POST /campaigns/orders/expire`. Its service callable was not verified when this was written, and a guessed import would crash the container on boot and take the four money sweeps down with it. One line in `JOBS` once confirmed.

---

## 9. Updating

```bash
cd kolabo && git pull
cd deploy && bash up.sh
```

Migrations run automatically on backend start.

**`git pull` refusing with "local changes would be overwritten" is the system working.** Somebody has edited a tracked file on this box. Find out what it was before you discard it, because on a box that fronts more than one product those edits may be the only copy of another product's routing:

```bash
git status --short
git diff -- deploy/ > ~/deploy-local-changes.patch && cat ~/deploy-local-changes.patch
```

Anything in that diff that is genuinely per box belongs in `deploy/caddy-extra/` or `deploy/docker-compose.local.yml`, both gitignored. Anything that is not belongs in a pull request.

**Changing `VITE_API_URL` needs a rebuild, not a restart.** Vite substitutes it into the bundle at build time, so there is no runtime environment left to read. `bash up.sh web`.

### Backups

Nothing here backs up the database. For a dev environment that may be fine, but decide deliberately rather than by omission:

```bash
mkdir -p ~/kolabo-backups
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U kolabo kolabo | gzip > ~/kolabo-backups/kolabo-$(date +%F).sql.gz
```

**Note the destination, because the earlier version of this line did not have one** and therefore wrote the dump into `deploy/`, inside the git working tree. That is how a `kolabo-2026-09-01.sql.gz` came to be sitting there untracked, one `git add -A` away from putting every user row, every verification document ciphertext and every social OAuth token into the repository's history. `.gitignore` now covers `deploy/*.sql.gz` as well, but the right answer is not to write it there in the first place.

**A dump alone is not a recovery plan.** Restoring it without the matching `DOCUMENT_ENCRYPTION_KEY` leaves every verification document and every stored social token permanently unreadable, so the key has to be backed up separately and somewhere else. And a backup nobody has restored is not a backup: take a dump, restore it into a scratch database, confirm a document decrypts. Until that has been done once, treat the environment as unprotected.

---

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| Caddy loops on certificates | DNS not resolving to this box yet, or 80/443 blocked. Fix DNS **first** — retries burn the Let's Encrypt rate limit. |
| `payments_gateway_not_configured` | `FEDAPAY_SECRET_KEY` unset, or the containers were not recreated after editing `deploy/.env`. |
| `/payments/config` says `enabled: false` while `deploy/.env` looks right | You edited `backend/.env`, or Compose did not recreate. See §7. |
| `payments_country_unsupported` for Benin | Should now be impossible with keys loaded — it means the registry is populated but has no `BJ`. Check `/payments/config`. |
| Config healthy but no payment ever settles from a webhook | `FEDAPAY_WEBHOOK_SECRET` unset or holding the API key instead of the `wh_` endpoint secret. Nothing surfaces this — check it directly (§7). Also check the server clock: verification allows 300 s of drift, so `timedatectl` before anything else. |
| **Payment succeeds at FedaPay but no escrow appears** | The amount that arrived is not the amount that was asked for, so `settle_intent` refuses and the intent goes `amount_mismatch` — by design, because paying 500 against a 50,000 contract is the cheapest fraud there is. Almost always **Préférences → Frais** with the client-bears-fee option on: FedaPay adds its fee to the payer's total. Turn both off (§6.3). Confirm in the backend log, which names the two amounts. |
| The checkout page declines every payment | The test number is not one of the two that succeed. `0166000001` or `0164000001`; everything else fails by design. See §7. |
| Webhook stopped being delivered at all | The webhook's "disable on errors" toggle is on and FedaPay switched it off. Turn the toggle off (§6.2) and re-enable the endpoint. |
| Checkout link no longer works | The token is single-use and expires after 24 hours. Start a new checkout rather than reusing the URL. |
| CORS errors in the browser | `CORS_ORIGINS` must include exactly `https://$WEB_HOSTNAME`, scheme included, no trailing slash. `bash checks/preflight-env.sh` checks this. |
| `caddy` exits immediately on start | `WEB_HOSTNAME` or `API_HOSTNAME` is unset in `deploy/.env`, so Caddy is parsing a site block with no address. Deliberate: the alternative to failing here is a box answering on the wrong name and getting a certificate to match. A bad file in `caddy-extra/` does the same thing; validate it with the command in §5 before reloading. |
| Another product on this box suddenly answers 502 while Kolabo is fine | caddy came back up without `docker-compose.local.yml`, so it is not on that product's network and the container name in its site block no longer resolves. Use `bash up.sh`, which includes that file, rather than a bare `docker compose` command. |
| Social connect finishes but the browser never returns to the page | `WEB_PUBLIC_BASE_URL` is unset or wrong, so `oauth_service.redirect_allowed` refuses the web app's own `redirect_to`, logs one line at WARNING and completes the connection anyway. `docker compose -f docker-compose.prod.yml logs backend \| grep -i redirect`. |
| Escrow funded but stuck `pending` | Webhook not reaching you *and* the payer never returned. Check the webhook URL and the dashboard's delivery log. |
| Creator never paid after release | Check the `payouts` table and the `sweeps` logs. `awaiting_method` means no wallet on file — expected, not an error. |

---

## 11. Known limitations of this environment

- ~~**`init_db()` still runs `create_all` on boot**~~ **Resolved.** Alembic is now the only thing that builds schema outside the test suite. Checked before removing it: all 37 tables in the model registry are created by a migration under `alembic/versions`, and the difference in both directions is empty. Two migration docstrings claim `notifications` is owned by no migration and exists only through `create_all`; both are wrong, the baseline `5f3a9c80d26f` creates it at line 117, and their inspector guards are harmless either way. A missing migration is now a missing table, loudly, instead of a table conjured from model metadata after `alembic upgrade head` has already reported success.
- ~~**The `postgres:16` and `caddy:2-alpine` tags are moving**~~ **Resolved.** Both are pinned by digest, to the images the dev box was already running on 24 September, so pinning them changed nothing at the time. Moving a pin forward is now a deliberate act with a pull request behind it: `docker pull postgres:16`, then `docker image inspect postgres:16 --format '{{index .RepoDigests 0}}'`, then that value into the compose file. The trade is that no upstream fix reaches either service until somebody does that, so it is worth doing on purpose every few months rather than never.
- **The build happens on the server.** `npm ci && vite build` on a small VPS is the likeliest way a deploy fails, and it fails by being OOM-killed rather than by saying so. There is no image artifact anywhere, so there is also no rollback: the previous version exists only as a git commit that has to be rebuilt. Moving the build into CI and having the server pull a tagged image is the fix, and it is its own change.
- **Single box, no redundancy.** Losing it loses the environment. Postgres data survives in a named volume unless you `docker compose down -v`.
- **No log aggregation, metrics or alerting.** Diagnosis is `docker compose logs`.
- **Payments are UEMOA-only** (Benin, Togo, Côte d'Ivoire). Ghana and Cameroon refuse by design — see `docs/PAYMENTS_FEDAPAY.md`.
- **`ENV` is now a required choice and `.env.example` ships it empty.** Three behaviours read it, all of them wrong in the unsafe direction on a box left saying `development`: `auth/otp.py` prints every OTP code to the container logs, `gateway_router.py` advertises `mock_payments` so checkout can settle without money moving, and `main.py` serves `/docs`, `/redoc` and `/openapi.json`. `config.py` separately refuses to boot with `ENV=production` while `JWT_SECRET` or `DOCUMENT_ENCRYPTION_KEY` is a committed default, which is the one check `checks/preflight-env.sh` deliberately does not duplicate.
- **No database backup exists.** §9 has the `pg_dump` one-liner and nothing runs it. This is the outstanding blocker for putting real users on any environment, dev box included.
- **The dev box's caddy is a single point of failure for three products.** Kolabo, FastaNow and Educazzi all terminate TLS through one container that this repository ships, so a Kolabo deploy that breaks the edge breaks all three. Supported now rather than accidental (§5), and still the wrong shape: the edge is shared infrastructure and wants to be its own small project that each product joins, rather than a service inside one of them. Production is a separate box and fronts Kolabo alone, so this is a dev box question only.
