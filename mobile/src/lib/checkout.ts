/* Types and calls for the hosted checkout flow — the mobile twin of
   web/src/lib/checkout.ts, ported rather than shared because the two clients
   have no common package. The shapes are copied field for field so a backend
   change breaks both clients in the same place instead of one of them
   quietly.

   A FEATURE-SCOPED lib file rather than 40 more lines in one of the shared
   *Types.ts files: these types are used by exactly two screens and one
   navigation decision, they arrived with the payment gateway, and they will
   change when a second gateway lands — the same reasoning that gives each
   feature its own types file here. Anything a third screen needs should
   graduate. */
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
  opts: { firstName?: string; lastName?: string; returnUrl?: string } = {}
): Promise<PaymentIntent> {
  return api<PaymentIntent>("/payments/checkout/start", {
    method: "POST",
    token,
    body: {
      contract_id: contractId,
      payer_first_name: opts.firstName || null,
      payer_last_name: opts.lastName || null,
      return_url: opts.returnUrl || null,
    },
  });
}

/* Not a passive status read: a still-pending intent is re-checked against the
   gateway inside this request, and the escrow is created here if the money
   arrived. Polling this IS the fastest path to a funded contract; the webhook
   is the safety net for the payer who pays and then closes the browser. */
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
   empty option — a chip with no label is unpickable, and a new network should
   degrade to ugly, not to broken. */
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
