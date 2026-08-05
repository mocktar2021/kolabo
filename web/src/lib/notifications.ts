/* Notifications, as the client has to reason about them.

   The endpoints are in backend/app/modules/notifications/router.py: a capped
   newest-first page (GET /notifications/), the unread count the badge draws
   (GET /notifications/unread-count), mark one (POST /notifications/{id}/read)
   and mark them all (POST /notifications/read-all). Every one of them takes
   its subject from the bearer token; there is no id parameter naming a user,
   so there is nothing here to walk through somebody else's bell with. */
import { parseApiDate } from "./orders";

/* One row of GET /notifications/. Mirror of NotificationOut in
   backend/app/modules/notifications/schemas.py.

   It lives here rather than in types.ts for the reason CartCheckoutOrder
   lives in cart.tsx: the bell and the notifications page are its only
   readers, and both of them are this module's callers.

   `message` is the English prose the backend also emails, and the FALLBACK
   shown when `params` is null — an old row, or a type not yet migrated. `link`
   is where a click goes, built by the backend at emit time (where it knows the
   recipient's side); null falls back to routeForType. `params` carries a
   {key, ...values}: the client renders the localised body from the key's FR/EN
   template (notificationStrings.ts) with the values interpolated. */
export type AppNotification = {
  id: string;
  type: string;
  message: string;
  link: string | null;
  params: Record<string, unknown> | null;
  is_read: boolean;
  /* Naive UTC like every other datetime from this API ("2026-07-31T09:12:00",
     no suffix), so it goes through parseApiDate before it becomes "il y a
     2 h" — left alone the browser reads it as local time and invents or
     destroys hours depending on where the reader is sitting. */
  created_at: string;
};

export type UnreadCount = { unread: number };
export type MarkAllRead = { marked: number };

/* How many rows the bell menu holds. A screenful: past this the panel becomes
   a page, and there is a page. */
export const PANEL_LIMIT = 8;

/* How many rows one page of the full history carries. Well under the server's
   MAX_LIMIT of 200 — this is a list somebody reads, not an export. */
export const PAGE_SIZE = 20;

/* The localised body of one notification.

   When params carries a message key the client renders the FR/EN template for
   it (notif.body.<key> in notificationStrings.ts) with the params as
   interpolation values. Otherwise — an old row, or a type whose call site has
   not been migrated to params yet — it shows the stored English `message`
   verbatim. defaultValue keeps that same fallback even if a key somehow has no
   template, so a notification is never blank. */
type Translate = (key: string, opts?: Record<string, unknown>) => string;

export function notificationBody(n: AppNotification, t: Translate): string {
  const key = n.params && typeof n.params.key === "string" ? (n.params.key as string) : null;
  if (!key) return n.message;
  return t(`notif.body.${key}`, { ...n.params, defaultValue: n.message });
}

/* Where a notification opens.

   The backend's `link` wins: it was built at emit time, which is the only
   place the recipient's side is known — the same event links a brand to its
   /campaigns/{id} and a creator to /invitations. When there is no link (an old
   row, or a type not yet carrying one) it falls back to routeForType, the
   type→screen map below. Null means the row just marks itself read. */
export function targetFor(n: AppNotification, isBrand: boolean): string | null {
  return n.link ?? routeForType(n.type, isBrand);
}

/* Where a notification can honestly be opened by TYPE alone, or null — the
   fallback used for rows the backend did not give a link.

   THIS ROUTES BY TYPE AND NEVER BY MESSAGE. The type is a fixed vocabulary
   the backend writes ("message", "payment", "dispute", "contract_ready",
   "campaign_invitation", "direct_order", "proposal_submitted", "security"...)
   and it is real data on the row. The message is a sentence for a human, and
   any rule that read it would break the first time somebody reworded a
   string — silently, and into a wrong destination.

   Unknown types return null and the row simply marks itself read. A new
   notification type shipped on the backend must never send a reader to a
   screen this file guessed at.

   THE ROLE GUARDS IN App.tsx ARE RESPECTED HERE. /invitations and /earnings
   are CreatorOnly and /payments is BrandOnly, so routing a brand at
   /invitations would bounce them to the dashboard — a click that appears to
   do the wrong thing. Where a role has no screen for a type, this answers
   null. */
export function routeForType(type: string, isBrand: boolean): string | null {
  if (type === "message") return "/messages";
  if (type === "dispute") return "/disputes";
  if (type === "security") return "/account";
  // The two halves of the same question: a buyer reads GROSS spend, a creator
  // reads NET earnings, and they are two screens for that reason.
  if (type === "payment") return isBrand ? "/payments" : "/earnings";
  // contract_ready, contract_signed, contract_cancelled. Both parties have a
  // contracts list and it is unguarded, so no role question arises.
  if (type.startsWith("contract")) return "/contracts";
  // Work submitted, and the brand's answer to it. The deliverables panel lives
  // ON the contract, so the backend always sends a link to the exact one and
  // this is only the fallback — same unguarded list, same absence of a role
  // question.
  if (type === "deliverable") return "/contracts";
  // campaign_invitation and campaign_cancelled are only ever sent to invited
  // creators; a business receiving one would be a backend bug, not a route to
  // build for.
  if (type === "campaign_invitation" || type === "campaign_cancelled") {
    return isBrand ? null : "/invitations";
  }
  // A direct order is read from opposite ends: the buyer owns the hidden
  // campaign, the creator answers it from their invitations.
  if (type === "direct_order") return isBrand ? "/campaigns" : "/invitations";
  // proposal_submitted, and any future proposal_* the negotiation adds.
  if (type.startsWith("proposal")) return isBrand ? "/campaigns" : "/invitations";
  return null;
}

/* "il y a 2 h", as a key and a number rather than as a finished string.

   The translation is left to the caller on purpose: this module has no `t`
   and importing one would give it a dependency on i18n for the sake of four
   lines. Computed on render rather than on a timer — nothing in a bell is
   worth a ticking clock. */
export function relativeParts(iso: string): { key: string; n: number } {
  const minutes = Math.floor((Date.now() - parseApiDate(iso)) / 60000);
  if (minutes < 1) return { key: "notif.justNow", n: 0 };
  if (minutes < 60) return { key: "notif.minutesAgo", n: minutes };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { key: "notif.hoursAgo", n: hours };
  return { key: "notif.daysAgo", n: Math.floor(hours / 24) };
}
