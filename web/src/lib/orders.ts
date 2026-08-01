/* Direct orders, as the client has to reason about them.

   Two facts about an order are not obvious from the payload, and both live
   here so that no page has to rediscover either one.

   First: a proposal carrying expires_at is a direct order, and one without is
   a brief's. Only orders run on a clock — a brief's proposals stay open
   because leaving one open promised nobody anything, while an order has a
   buyer waiting on a price they already named.

   Second: the API serialises naive UTC datetimes ("2026-07-31T09:12:00", no
   suffix), which JavaScript reads as LOCAL time. Left alone that invents or
   destroys hours of a 48 h window depending on where the creator is sitting,
   which is the difference between answering and lapsing. */
import type { InvitationWithCampaign, Proposal } from "./types";

export function parseApiDate(iso: string): number {
  const time = iso.slice(10);
  const hasZone = time.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(time);
  return Date.parse(hasZone ? iso : `${iso}Z`);
}

/* The order behind an invitation row, or null when the row is a brief. */
export function directOrderOf(inv: InvitationWithCampaign): Proposal | null {
  return inv.proposal && inv.proposal.expires_at ? inv.proposal : null;
}

/* How much of the window is left, or null once it has closed. Computed on
   demand rather than on a ticking timer: the server is the authority on
   expiry and answers "This order has expired." to a late click, which the
   invitations page shows inline — so a stale minute on screen costs a second
   attempt and nothing else. Never reports "0 min" while the offer is live. */
export function orderTimeLeft(expiresAt: string): { unit: "hours" | "minutes"; n: number } | null {
  const ms = parseApiDate(expiresAt) - Date.now();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return { unit: "minutes", n: Math.max(minutes, 1) };
  return { unit: "hours", n: Math.floor(minutes / 60) };
}

/* An order still waiting on the creator: the live version of the chain, with
   the clock still running. Anything superseded, accepted or declined has been
   answered already. */
export function isOrderAwaitingAnswer(inv: InvitationWithCampaign): boolean {
  const order = directOrderOf(inv);
  if (!order || !order.expires_at || order.status !== "submitted") return false;
  return orderTimeLeft(order.expires_at) !== null;
}
