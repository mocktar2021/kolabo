/* Types and calls for the hosted checkout flow.

   A FEATURE-SCOPED lib file rather than 40 more lines in lib/types.ts, which
   is already 27 KB of shared API shapes. These types are used by exactly two
   screens and one nav decision, they arrived with the payment gateway, and
   they will change when a second gateway lands — the same reasoning that gives
   each feature its own *Strings.ts bundle. Anything a third screen needs
   should graduate to types.ts. */
import { api } from "./api";

/* What the backend can do right now. Read once on the checkout screen so the
   client never assumes payments are live: a dev stack with no FedaPay keys
   answers enabled:false, and the UI says so instead of showing a Pay button
   that 400s. */
export type PaymentConfig = {
  enabled: boolean;
  public_key: string;
  sandbox: boolean;
  countries: string[];
  /* May this client fall back to the mock funding path? True only when the
     backend has no gateway configured AND is not running as production. Lets a
     developer with no FedaPay account still exercise deliver -> approve ->
     release locally; false in production, where funding refuses instead. */
  mock_payments: boolean;
};

export type PaymentIntentStatus = "pending" | "succeeded" | "failed" | "canceled";

export type PaymentIntent = {
  id: string;
  contract_id: string;
  amount: number;
  currency: string;
  status: PaymentIntentStatus;
  provider: string;
  /* Null once the payment is terminal. A used-up checkout url is worse than no
     url: it takes a payer to an expired page instead of telling them the
     payment is already done. */
  checkout_url: string | null;
  /* WHAT THE PAYER HAS TO DO NEXT, and the field that picks the screen.

     "redirect"       open checkout_url. A hosted page takes it from there.
     "device_prompt"  nothing to open. The gateway has already pushed a
                      payment request to the handset we named, and the only
                      thing left is to wait and keep polling.

     READ THIS, NEVER THE NULLNESS OF checkout_url. They are different
     questions and the difference is right above: checkout_url also goes null
     once a redirect payment is terminal, so a screen that inferred the state
     from the url would tell somebody whose card payment had already
     succeeded to go and check their phone. */
  payer_action: "redirect" | "device_prompt";
  /* Which network the request went to, when there was one. Null on a
     redirect, because the payer picks their operator on the hosted page and
     we never learn which one. */
  payer_network: string | null;
  /* THE FIELD THE UI ACTUALLY WAITS ON. status "succeeded" without an escrow
     id is the amount-mismatch case — the gateway took money that does not
     match the contract — and that needs a human, not a success screen. So the
     done state is escrow_id !== null, never status alone. */
  escrow_id: string | null;
  failure_reason: string | null;
};

export type PayoutMethod = {
  country: string;
  mode: string;
  /* Masked by the API. The full number never leaves the server. */
  phone_masked: string;
  account_name: string | null;
};

export function paymentConfig(): Promise<PaymentConfig> {
  return api<PaymentConfig>("/payments/config");
}

export function startCheckout(
  contractId: string,
  token: string | null,
  opts: {
    firstName?: string;
    lastName?: string;
    returnUrl?: string;
    /* Only sent when the routed gateway asked for them, which is what
       collectionNetworks() answers. Both are null on a redirect flow, where
       the payer picks a network and types a number on the hosted page
       instead, and the API accepts their absence on purpose: the last mobile
       build approved by the stores posts this body without them. */
    network?: string;
    phone?: string;
  } = {}
): Promise<PaymentIntent> {
  return api<PaymentIntent>("/payments/checkout/start", {
    method: "POST",
    token,
    body: {
      contract_id: contractId,
      payer_first_name: opts.firstName || null,
      payer_last_name: opts.lastName || null,
      return_url: opts.returnUrl || null,
      payer_network: opts.network || null,
      payer_phone: opts.phone || null,
    },
  });
}

/* Which mobile money networks THIS brand can pay from, for the country on
   their account. An empty list is a real answer and means "do not show a
   picker": the routed gateway runs its own hosted page where the payer
   chooses, so there is nothing for us to ask. */
export function collectionNetworks(token: string | null): Promise<string[]> {
  return api<string[]>("/payments/collection-networks", { token });
}

/* Display names for the collection networks, on the same terms as
   PAYOUT_MODE_LABELS below and deliberately a SEPARATE map.

   The two vocabularies look almost identical and are not the same: a payout
   to Cote d'Ivoire is keyed MTN_CI because that string goes in a URL path,
   while a collection sends MTN CI in a field. One map serving both would
   have to hold both spellings of every operator and would quietly return the
   wrong key the first time one of them changed.

   Unknown codes fall back to the code itself, which is the rule the payout
   map already follows: a network added at the provider should degrade to
   ugly, not to an unpickable blank row. */
export const COLLECTION_NETWORK_LABELS: Record<string, string> = {
  MTN: "MTN Mobile Money",
  MOOV: "Moov Money",
  "CELTIIS BJ": "Celtiis Cash",
  "MOOV TG": "Moov Money",
  "TOGOCOM TG": "T-Money",
  "MTN CI": "MTN Mobile Money",
  "MOOV CI": "Moov Money",
  "WAVE CI": "Wave",
  "ORANGE CI": "Orange Money",
  "WAVE SN": "Wave",
  "ORANGE SN": "Orange Money",
  "FREE SN": "Free Money",
};

export function collectionNetworkLabel(network: string): string {
  return COLLECTION_NETWORK_LABELS[network] || network;
}

/* Not a passive status read: a still-pending intent is re-checked against the
   gateway inside this request, and the escrow is created here if the money
   arrived. Polling this IS the fastest path to a funded contract; the webhook
   is the safety net for the payer who pays and then closes the tab. */
export function readCheckout(intentId: string, token: string | null): Promise<PaymentIntent> {
  return api<PaymentIntent>(`/payments/checkout/${intentId}`, { token });
}

export function payoutModes(country: string): Promise<string[]> {
  return api<string[]>(`/payments/payout-modes/${country}`);
}

export function getPayoutMethod(token: string | null): Promise<PayoutMethod | null> {
  return api<PayoutMethod | null>("/payments/payout-method", { token });
}

export function savePayoutMethod(
  token: string | null,
  body: { country: string; mode: string; phone: string; account_name?: string | null }
): Promise<PayoutMethod> {
  return api<PayoutMethod>("/payments/payout-method", { method: "PUT", token, body });
}

/* Display names for the gateway's network strings. The API returns machine
   values (mtn_open, sbin) because that is what it has to send FedaPay; a
   creator picking their wallet should read "MTN Mobile Money", not an
   identifier. Unknown codes fall back to the code itself rather than to an
   empty option — a dropdown row with no label is unpickable, and a new network
   should degrade to ugly, not to broken. */
export const PAYOUT_MODE_LABELS: Record<string, string> = {
  mtn_open: "MTN Mobile Money",
  moov: "Moov Money",
  sbin: "Celtiis Cash",
  moov_tg: "Moov Money",
  togocel: "T-Money",
  mtn_ci: "MTN Mobile Money",
  moov_ci: "Moov Money",
  wave_ci: "Wave",
  orange_ci: "Orange Money",
};

export function payoutModeLabel(mode: string): string {
  return PAYOUT_MODE_LABELS[mode] || mode;
}
