/* The dispute rules the client has to know, in one place.

   Every one of these mirrors something the server enforces, and none of them
   replaces it: the bounds are checked again in
   backend/app/modules/payments/disputes.py, which is what answers a request
   that skipped the form. What they buy is a refusal the person can act on
   before they have typed four hundred words and pressed a button.

   ONE OPEN DISPUTE, NOT ONE EVER. An escrow can carry several dispute rows
   over its life — one withdrawn when two parties settled a misunderstanding
   themselves, another raised weeks later when the work actually failed. Only
   an OPEN one blocks a new claim or has anything left to say, so every screen
   that asks "is this escrow disputed" has to ask about status and not just
   count rows. */
import type { Dispute, DisputeReason, DisputeStatus } from "./types";
import { parseApiDate } from "./orders";

/* Mirror of DISPUTE_REASONS in backend/app/modules/payments/models.py, in the
   order the select offers them: what a buyer most often means first. */
export const DISPUTE_REASONS: readonly DisputeReason[] = [
  "not_delivered",
  "late",
  "wrong_content",
  "quality",
  "payment_issue",
  "other"
];

/* Mirror of disputes.OPEN_STATUSES. */
export const OPEN_DISPUTE_STATUSES: readonly DisputeStatus[] = [
  "awaiting_response",
  "awaiting_admin"
];

export const MIN_STATEMENT_CHARS = 10;
export const MAX_STATEMENT_CHARS = 4000;
export const MAX_EVIDENCE_IMAGES = 10;

export function isDisputeOpen(dispute: Dispute): boolean {
  return OPEN_DISPUTE_STATUSES.includes(dispute.status);
}

/* The live case on an escrow, out of everything the caller is party to.

   Deliberately not "the most recent dispute on this escrow": a resolved or
   withdrawn one is history, and showing it where the open one goes would tell
   somebody their money is frozen over an argument that ended. */
export function openDisputeFor(disputes: Dispute[], escrowId: string): Dispute | null {
  return disputes.find((d) => d.escrow_id === escrowId && isDisputeOpen(d)) ?? null;
}

/* How much of the response window is left, or null once it has closed.

   Computed on demand rather than on a ticking timer, exactly like the order
   countdown: the server decides when a window has expired (the escalation
   sweep does), so a stale minute on screen costs nothing. Never reports
   "0 min" while the window is still open. */
export function respondTimeLeft(
  respondBy: string
): { unit: "hours" | "minutes"; n: number } | null {
  const ms = parseApiDate(respondBy) - Date.now();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return { unit: "minutes", n: Math.max(minutes, 1) };
  return { unit: "hours", n: Math.floor(minutes / 60) };
}
