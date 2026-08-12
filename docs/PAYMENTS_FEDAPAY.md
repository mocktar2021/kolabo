# Payments: gateway selection and the FedaPay integration

**Status:** implemented, sandbox only. No live keys are configured anywhere in
this repository and none should be committed to it.

---

## 1. The decision

**FedaPay**, for Benin, Togo and Côte d'Ivoire.

The candidates were FedaPay and KKiaPay. Both are Benin-based, both cover UEMOA
mobile money, and on headline pricing KKiaPay is competitive. The decision was
not made on price, because one of them cannot do the thing this product is.

### The rule that decided it

> **A marketplace has to be able to pay a third party from code.**

Kolabo holds a brand's money in escrow, takes a 15% commission, and pays the
balance to a creator who is not the merchant. That is a disbursement to a third
party, triggered by our own business logic, on our own schedule.

| | FedaPay | KKiaPay |
|---|---|---|
| Collect from a payer | ✅ `POST /v1/transactions` + hosted checkout | ✅ widget + SDKs |
| **Send money to a third party's wallet** | ✅ `POST /v1/payouts` → `PUT /v1/payouts/start` | ❌ **no such API** |
| Verify a transaction server-side | ✅ `GET /v1/transactions/{id}` | ✅ `POST /api/v1/transactions/status` |
| Webhook authentication | ✅ HMAC-SHA256 signature + timestamp | ⚠️ static shared secret in a header |
| Fixed monthly cost | 0 XOF | 14,900 XOF/month (Intégration plan) |

KKiaPay's only payout endpoint is `POST /merchant/payouts/schedule`. Its fields
are `algorithm` (`roof` / `rate`), `destination_type` and `destination` — it
**configures automatic settlement of your own merchant balance into your own
registered account**. It is a treasury feature. There is no
`amount + phone + reason` "pay this person now" call in any official KKiaPay
SDK or documentation page. Their "Push Up" product (10,000 XOF/month) may be
the bulk-disbursement offering, but it has **no public API documentation at
all** — endpoints, payload and whether it is API-driven are unknown.

Building escrow on that would have meant paying every creator by hand from a
dashboard, which does not survive contact with a pilot, let alone scale.

### Against the decision matrix

- **Rule A — the Marketplace Rule.** ✅ **Triggered, and decisive.** Kolabo is a
  multi-party marketplace: `payments/service._release` computes a commission and
  disburses the balance to a third party. FedaPay's two-step payout is the only
  candidate API that can do it.
- **Rule B — Scale & High-Volume Card.** ❌ Not triggered. Pre-pilot, no
  predictable >1,000,000 XOF/month, and mobile money — not cards — is the
  primary rail in all three markets.
- **Rule C — Zero-Overhead / Early Stage.** ✅ Triggered, and points the same
  way. Pre-revenue, 0 XOF fixed monthly against KKiaPay's 14,900 XOF, and the
  web client is React.
- **Rule D — Custom Mobile App / Native SDKs.** Would favour KKiaPay, **but the
  rule is explicitly subordinate to Rule A**, which applies. It is also close to
  moot here: `mobile/` is Expo / React Native, not Flutter, and KKiaPay's
  React Native SDK is a widget wrapper, not a payout API. The RN pattern for a
  hosted checkout is a WebView or a system browser hand-off either way.

### Financial impact

Illustrative, at a pilot volume of **30 collaborations/month × 50,000 XOF =
1,500,000 XOF**:

| | FedaPay | KKiaPay |
|---|---|---|
| Collection (1.8% vs 1.5%) | 27,000 XOF | 22,500 XOF |
| Monthly subscription | 0 | 14,900 XOF |
| Creator payouts (30 × 300 XOF tier) | 9,000 XOF | *not possible via API* |
| **Total** | **≈36,000 XOF** | **≈37,400 XOF + manual payouts** |

FedaPay is marginally cheaper at pilot volume and the gap closes as volume
grows. **The cost comparison is not the reason for the decision** — it is here
to show that choosing the architecturally viable option costs nothing.

> **Assumption, not a confirmed fact:** these rates are the publicly listed
> Benin rates at the time of writing. FedaPay publishes per-country pricing only
> for Benin; Togo and Côte d'Ivoire rates are unverified. KKiaPay's own docs
> and pricing page contradict each other on mobile money fees (3% vs 1.5%).
> **Confirm both fee schedules in writing before modelling unit economics.**

---

## 2. What this does NOT cover — read this before the pilot

**FedaPay serves 3 of the 5 pilot countries.**

| Country | Currency | FedaPay | Status |
|---|---|---|---|
| Benin | XOF | ✅ collect + payout | live path |
| Togo | XOF | ✅ collect + payout | live path |
| Côte d'Ivoire | XOF | ✅ collect + payout | live path |
| **Ghana** | GHS | ❌ not a FedaPay market | **payments refuse** |
| **Cameroon** | XAF | ❌ not a FedaPay market | **payments refuse** |
| Nigeria | NGN | ❌ | payments refuse |
| Senegal | XOF | ⚠️ collect and payout do not meet | payments refuse |

Senegal is excluded deliberately even though FedaPay lists Senegalese methods:
its published matrix has **collection** on `free_sn` only and **payout** on
`wave_sn` / `orange_sn`. The two halves do not meet, so a Senegalese
collaboration cannot complete end to end.

**How the gap is handled.** `payments/gateways/registry.py` routes by country
and **refuses loudly** for anything uncovered — `payments_country_unsupported`,
rendered to the brand as "Online payments are not available in *X* yet."
Registration stays open in those countries; only the money path refuses. The
alternative was falling back to the mock provider, which would show a Ghanaian
brand a receipt for money nobody collected and leave a creator waiting on a
payout that can never arrive.

**Adding Ghana or Cameroon is a second gateway**, not a config change: a class
implementing `gateways/base.PaymentGateway` (Paystack or Flutterwave for GHS; a
CEMAC-capable provider for XAF) plus one line in `_build_registry`. No escrow
logic changes, because none of it names a vendor.

**Open decision for the founder:** narrow the payment-enabled pilot to the
UEMOA three, or budget a second PSP integration before launch.

---

## 3. Architecture

```
                    ┌──────────────────────────────────────┐
  brand clicks Fund │  POST /payments/checkout/start       │
                    │  → PaymentIntent (pending)           │
                    │  → FedaPay POST /transactions        │
                    │  → FedaPay POST /transactions/{}/token│
                    │  ← checkout_url                      │
                    └──────────────┬───────────────────────┘
                                   │ redirect
                          ┌────────▼────────┐
                          │ FedaPay hosted  │  payer approves on their handset
                          │ checkout page   │
                          └────────┬────────┘
                    ┌──────────────┴──────────────┐
        return url  │                             │  webhook
   GET /payments/checkout/{id}      POST /webhooks/fedapay
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                      checkout.settle_intent()
                      1. re-read GET /transactions/{id}   ← THE ONLY TRUTH
                      2. assert amount + currency match
                      3. assert no escrow exists yet
                      4. service.hold_funds() → Escrow HELD
```

### The three security properties

1. **The webhook is never believed.** A webhook body is the sender's account of
   events, and the sender is whoever got a POST through to our URL. Every path
   that concludes money arrived concludes it from `GET /v1/transactions/{id}`
   over a connection *we* opened to a host *we* chose. The webhook's only job is
   to tell us *when to ask*.
2. **Signature + replay window.** `X-FEDAPAY-SIGNATURE: t=<ts>,s=<hex>`,
   HMAC-SHA256 over `"<ts>.<raw body>"`, constant-time compared, 300s tolerance.
   Computed over **raw request bytes** — re-serialising a parsed body changes
   key order and whitespace and is the classic way this is written wrong. An
   unset secret **refuses**, it does not skip.
3. **Idempotency before the work.** `(provider, event_id)` is unique on
   `gateway_events` and the row is inserted *before* settlement. Two concurrent
   deliveries race on the constraint; exactly one wins and the other returns 200
   having done nothing.

### The amount check

`settle_intent` compares the gateway's reported amount and currency against the
amount copied onto the intent at creation. Paying 500 XOF against a 50,000 XOF
contract is the cheapest fraud against a marketplace checkout and the only
defence is comparing two integers on the way in. On mismatch the intent fails,
**no escrow is created**, and the payer is shown a reference and pointed at
support — never a success screen, and never "nothing was charged", because money
may really have moved.

### Release and payout are separate events

This is the most important design decision in the change.

Previously `_release` called `provider.payout()` inline and marked the escrow
`RELEASED` in the same breath. That is correct against a mock that cannot fail
and wrong against a network that can:

- if the payout raised, the release would 500 **after** the platform had decided
  the creator was owed, leaving an escrow `HELD` on accepted work;
- if it were swallowed, the escrow would read `RELEASED` with nobody paid and
  nothing tracking it.

So the escrow records the **decision** (and never takes it back), and a `Payout`
row records what happened to the **money**. `payouts.disburse` cannot raise. A
failed payout is retried by `payouts.run_pending_payouts`; above
`PAYOUT_MAX_ATTEMPTS` it stops and becomes a support queue item, with the
creator still visibly owed. That state is honest and recoverable.

### Why the payout network is asked for, not inferred

`payout_methods` stores country + `mode` + phone per creator. Operator prefix
ranges in Benin and Côte d'Ivoire have been reassigned more than once, and
number portability moves a subscriber between networks without changing a digit.
A payout sent down the wrong network does not bounce cleanly — it fails late, or
lands in a wallet the recipient does not check. Asking once costs one screen;
inferring costs support tickets about missing money.

---

## 4. Files

| Path | What it is |
|---|---|
| `gateways/base.py` | Result types + the `PaymentGateway` protocol |
| `gateways/signature.py` | Webhook HMAC verification (no official Python SDK exists) |
| `gateways/fedapay.py` | The FedaPay HTTP client |
| `gateways/registry.py` | Country → gateway, and the refusal when none answers |
| `gateway_models.py` | `PaymentIntent`, `Payout`, `PayoutMethod`, `GatewayEvent` |
| `checkout.py` | start / settle / read |
| `payouts.py` | Disbursement, payout methods, the retry sweep |
| `webhooks.py` | `POST /webhooks/fedapay` |
| `gateway_router.py` | Checkout + payout-method endpoints |
| `service.py` | Refactored: `assert_fundable`, `hold_funds`, `_release` via `payouts` |
| `web/src/pages/Checkout.tsx` | The hosted checkout screen (start + return, one page) |
| `mobile/src/screens/CheckoutScreen.tsx` | The same flow via the system browser |

### API surface

| Method | Path | Auth |
|---|---|---|
| `GET` | `/payments/config` | none (publishable key only) |
| `POST` | `/payments/checkout/start` | brand |
| `GET` | `/payments/checkout/{id}` | brand — **settles on read** |
| `GET`/`PUT` | `/payments/payout-method` | any user |
| `GET` | `/payments/payout-modes/{country}` | none |
| `POST` | `/payments/payouts/run` | admin |
| `POST` | `/webhooks/fedapay` | **HMAC signature** |

`POST /payments/escrow/fund` still exists and still works when **no** gateway is
configured (tests, local dev). With a live gateway it refuses with
`escrow_use_checkout` — a synchronous collect cannot be honest when the payer
has not seen a PIN prompt yet.

---

## 5. Going live — the checklist

1. **Register** at fedapay.com, complete KYC for the operating entity.
2. **Whitelist the web domain** in the FedaPay dashboard. Without this, payers
   are redirected to a FedaPay signup page instead of a payment form. This is
   the single most common first-launch failure.
3. **Sandbox keys** → `backend/.env`:
   ```
   FEDAPAY_SECRET_KEY=<sandbox secret>
   FEDAPAY_PUBLIC_KEY=<sandbox public>
   FEDAPAY_SANDBOX=true
   ```
4. **Configure the webhook**: URL `https://<api-host>/webhooks/fedapay`, subscribe
   to `transaction.approved`, `transaction.declined`, `transaction.canceled`,
   `transaction.transferred` and the payout events. Copy the endpoint secret
   (prefix `wh_`) into `FEDAPAY_WEBHOOK_SECRET`. **It is not the API secret key.**
5. **Set `PAYMENT_RETURN_URL`** to the deployed web origin's `/checkout/return`.
6. **Run a sandbox pass** end to end: fund → deliver → approve → confirm the
   payout reaches a sandbox wallet.
7. **Put a scheduler in front of the sweeps.** There are now four admin-triggered
   jobs with no cron behind them: `escrow/auto-release`, `disputes/escalate`,
   `campaigns/orders/expire` and **`payments/payouts/run`**. The last one is the
   one that gets money to creators whose payout hit a network failure — it is
   the one that most needs scheduling before the pilot.
8. **Go live**: live keys, `FEDAPAY_SANDBOX=false`, a fresh webhook secret from
   the live dashboard, and a small real transaction as a smoke test.

### Sandbox test numbers

MTN Benin `97000000` / `61000000` succeed; `…001` processing error;
`…002` insufficient funds. Moov `95000000` / `68000000` follow the same pattern.

---

## 6. Known unknowns

Verify these against FedaPay before go-live rather than trusting this document:

- **Payout webhook event names** are not enumerated in FedaPay's docs. The
  handler matches any `payout.*` prefix, which is defensive but unconfirmed.
- **`sub_accounts_commisssions`** (FedaPay's native split-payment field, and yes
  it is spelled with three `s` in their docs) appears only on the legacy docs
  site. This integration deliberately does **not** use it: escrow is operated by
  us, with collection into the merchant balance and an explicit payout at
  release. That is the more certain mechanism and it keeps the commission rule
  in `core/pricing.py` where it is tested.
- **Response envelope.** FedaPay returns resources keyed by name
  (`{"v1/transaction": {...}}`), but this is not a documented contract. The
  client accepts both the envelope and a bare resource.
- **Per-country pricing** for Togo and Côte d'Ivoire.
- **Card `mode` string** — cards appear to go through the hosted page only.

---

## 7. Legal and compliance — not addressed here

Flagged, not resolved. Qualified local advice is needed on: PSP agreement terms
and settlement timing; who bears transaction fees (currently the platform, on
both legs); refund and chargeback policy; escrow and money-transmission
characterisation in each market; tax treatment of the commission; cross-border
XOF settlement between the three countries; and data protection for the payment
identifiers stored in `payment_intents` and `payout_methods`.
