/* Dispute shapes and the client-side rules, mirrored from web/src/lib/
   disputes.ts and the backend DisputeOut schema. Every bound here is re-checked
   by backend/app/modules/payments/disputes.py; these just let a refusal reach
   the person before they have typed a statement and pressed a button. */
import { parseApiDate } from "./dates";
import type { Escrow } from "./contractTypes";

export type DisputeReason =
  | "not_delivered"
  | "late"
  | "wrong_content"
  | "quality"
  | "payment_issue"
  | "other";

export type DisputeStatus = "awaiting_response" | "awaiting_admin" | "resolved" | "withdrawn";

export type Dispute = {
  id: string;
  escrow_id: string;
  opened_by_user_id: string;
  reason: DisputeReason;
  statement: string;
  status: DisputeStatus;
  respond_by: string;
  resolved_at: string | null;
  resolution: string | null;
  released_amount: number | null;
  refunded_amount: number | null;
  resolved_by: string | null;
  created_at: string;
  attachments: string[];
  escrow: Escrow | null;
};

export type DisputeMessage = {
  id: string;
  author_user_id: string;
  body: string;
  created_at: string;
  attachments: string[];
};

export type DisputeCase = Dispute & { messages: DisputeMessage[] };

/* In the order the reason picker offers them: what a buyer most often means
   first. Mirror of DISPUTE_REASONS in payments/models.py. */
export const DISPUTE_REASONS: DisputeReason[] = [
  "not_delivered",
  "late",
  "wrong_content",
  "quality",
  "payment_issue",
  "other",
];

export const OPEN_DISPUTE_STATUSES: DisputeStatus[] = ["awaiting_response", "awaiting_admin"];

export const MIN_STATEMENT_CHARS = 10;
export const MAX_STATEMENT_CHARS = 4000;

export function isDisputeOpen(d: Dispute): boolean {
  return OPEN_DISPUTE_STATUSES.includes(d.status);
}

/* The live case on an escrow — the OPEN one, not the most recent: a resolved
   or withdrawn row is history, and showing it where the open one goes would
   tell somebody their money is frozen over an argument that ended. */
export function openDisputeFor(disputes: Dispute[], escrowId: string): Dispute | null {
  return disputes.find((d) => d.escrow_id === escrowId && isDisputeOpen(d)) ?? null;
}

/* How much of the 72 h response window is left, or null once it has closed.
   Computed on demand rather than on a ticking timer — the server decides when
   a window has expired, so a stale minute on screen costs nothing. */
export function respondTimeLeft(respondBy: string): { unit: "hours" | "minutes"; n: number } | null {
  const d = parseApiDate(respondBy);
  if (!d) return null;
  const ms = d.getTime() - Date.now();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return { unit: "minutes", n: Math.max(minutes, 1) };
  return { unit: "hours", n: Math.floor(minutes / 60) };
}
