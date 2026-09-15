# Deploying the Kolabo dev environment

One VPS, Docker Compose, Caddy for TLS.

| | |
|---|---|
| Web | `https://kolabo.mocktar.com` |
| API | `https://api.kolabo.mocktar.com` |
| Payments | **FedaPay sandbox only.** No real money can move. |

**This is a development environment on a public hostname.** Those two facts pull in opposite directions: it is reachable by anyone, and it is configured for convenience. Everything under "Before you start" exists because of that tension — in particular the two committed default secrets, which protect nothing until you replace them.

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
cp .env.example .env
$EDITOR .env          # fill in every CHANGE THIS, and the FedaPay sandbox keys

docker compose -f docker-compose.prod.yml up -d --build
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
cd deploy && docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on backend start.

**Changing `VITE_API_URL` needs a rebuild, not a restart.** Vite substitutes it into the bundle at build time, so there is no runtime environment left to read. `docker compose -f docker-compose.prod.yml up -d --build web`.

### Backups

Nothing here backs up the database. For a dev environment that may be fine — but decide deliberately rather than by omission:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U kolabo kolabo | gzip > kolabo-$(date +%F).sql.gz
```

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
| CORS errors in the browser | `CORS_ORIGINS` must be exactly `https://kolabo.mocktar.com`, scheme included, no trailing slash. |
| Escrow funded but stuck `pending` | Webhook not reaching you *and* the payer never returned. Check the webhook URL and the dashboard's delivery log. |
| Creator never paid after release | Check the `payouts` table and the `sweeps` logs. `awaiting_method` means no wallet on file — expected, not an error. |

---

## 11. Known limitations of this environment

- **`init_db()` still runs `create_all` on boot** alongside Alembic. Belt-and-braces, but it can mask a missing migration by creating a table Alembic never learned about — the schema-drift risk the testing plan already flags. Fine for a dev box; resolve before production.
- **Single box, no redundancy.** Losing it loses the environment. Postgres data survives in a named volume unless you `docker compose down -v`.
- **No log aggregation, metrics or alerting.** Diagnosis is `docker compose logs`.
- **Payments are UEMOA-only** (Benin, Togo, Côte d'Ivoire). Ghana and Cameroon refuse by design — see `docs/PAYMENTS_FEDAPAY.md`.
- **`ENV=development`**, which is what keeps `mock_payments` available as a fallback. Setting `ENV=production` disables it, so funding refuses outright when no gateway is configured.
