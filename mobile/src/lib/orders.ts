/* Direct orders, as the client has to reason about them. Mirror of
   web/src/lib/orders.ts against the same payloads.

   A proposal carrying expires_at is a direct order, and one without is a
   brief's. Only orders run on a clock — a brief's proposals stay open because
   leaving one open promised nobody anything, while an order has a buyer
   waiting on a price they already named.

   parseApiDate (lib/dates.ts) is what stops a device in UTC+1 reading the
   API's naive-UTC timestamps as local time and inventing or destroying hours
   of a 48 h window. */
import { parseApiDate } from "./dates";
import type { InvitationWithCampaign, Proposal } from "./campaignTypes";

/* The order behind an invitation row, or null when the row is a brief. */
export function directOrderOf(inv: InvitationWithCampaign): Proposal | null {
  return inv.proposal && inv.proposal.expires_at ? inv.proposal : null;
}

/* How much of the window is left, or null once it has closed. Computed on
   demand rather than on a ticking timer: the server is the authority on
   expiry and answers "This order has expired." to a late click, which the
   screen shows inline — so a stale minute on screen costs a second attempt
   and nothing else. Never reports "0 min" while the offer is live. */
export function orderTimeLeft(expiresAt: string): { unit: "hours" | "minutes"; n: number } | null {
  const d = parseApiDate(expiresAt);
  if (!d) return null;
  const ms = d.getTime() - Date.now();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return { unit: "minutes", n: Math.max(minutes, 1) };
  return { unit: "hours", n: Math.floor(minutes / 60) };
}

/* "Sent 2 h ago" for one version of a chain, as a key and a number rather
   than a finished string, so the caller keeps its own `t`. */
export function sentParts(iso: string): { key: string; n: number } | null {
  const d = parseApiDate(iso);
  if (!d) return null;
  const minutes = Math.floor((Date.now() - d.getTime()) / 60000);
  if (minutes < 1) return { key: "invitation.sentJustNow", n: 0 };
  if (minutes < 60) return { key: "invitation.sentMinutesAgo", n: minutes };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { key: "invitation.sentHoursAgo", n: hours };
  return { key: "invitation.sentDaysAgo", n: Math.floor(hours / 24) };
}
