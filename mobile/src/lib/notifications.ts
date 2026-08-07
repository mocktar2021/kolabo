/* Notifications, as the mobile client has to reason about them. Mirror of
   web/src/lib/notifications.ts against the same endpoints: a capped
   newest-first page (GET /notifications/), the unread count the badge draws
   (GET /notifications/unread-count), mark one (POST /notifications/{id}/read)
   and mark them all (POST /notifications/read-all). */
import { parseApiDate } from "./dates";

export type AppNotification = {
  id: string;
  type: string;
  /* The English prose the backend also emails — the fallback shown when
     params is null (an old row, or a type not yet migrated to keys). */
  message: string;
  /* Where a click goes, built at emit time as a WEB path ("/contracts/{id}").
     The mobile client translates it to a screen in targetFor below; null
     falls back to the type→screen map. */
  link: string | null;
  params: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
};

export type UnreadCount = { unread: number };
export type MarkAllRead = { marked: number };

/* One page of the history. Well under the server's MAX_LIMIT of 200 — this is
   a list somebody reads, not an export. */
export const PAGE_SIZE = 20;

type Translate = (key: string, opts?: Record<string, unknown>) => string;

/* The localised body: when params carries a message key, render the FR/EN
   template (notif.body.<key>) with the params interpolated; otherwise show
   the stored English `message` verbatim. defaultValue keeps that fallback
   even if a key has no template, so a notification is never blank. */
export function notificationBody(n: AppNotification, t: Translate): string {
  const key = n.params && typeof n.params.key === "string" ? (n.params.key as string) : null;
  if (!key) return n.message;
  return t(`notif.body.${key}`, { ...n.params, defaultValue: n.message });
}

/* A navigation target this app can actually reach. A discriminated union of
   literal screen names rather than a raw string, so the caller can switch on
   `name` and hand React Navigation correctly-typed params. */
export type NavTarget =
  | { name: "Contracts" | "Campaigns" | "Invitations" | "Earnings" | "Spend" }
  | { name: "ContractDetail" | "CampaignDetail" | "DisputeDetail"; id: string };

/* Where a notification opens. The backend's `link` wins — it was built at
   emit time, the only place the recipient's side is known — but it is a web
   path, so it is parsed into this app's screens. When no screen exists for it
   here (messages, account), the row just marks itself read.

   THE FALLBACK ROUTES BY TYPE AND NEVER BY MESSAGE: the type is a fixed
   vocabulary and real data on the row; the message is a sentence for a human,
   and any rule that read it would break the first time somebody reworded a
   string. Unknown types return null — a new backend type must never send a
   reader to a screen this file guessed at. */
export function targetFor(n: AppNotification, isBrand: boolean): NavTarget | null {
  const fromLink = linkTarget(n.link, isBrand);
  if (fromLink) return fromLink;
  return typeTarget(n.type, isBrand);
}

function linkTarget(link: string | null, isBrand: boolean): NavTarget | null {
  if (!link) return null;
  const contract = link.match(/^\/contracts\/([^/?#]+)/);
  if (contract) return { name: "ContractDetail", id: contract[1] };
  const dispute = link.match(/^\/disputes\/([^/?#]+)/);
  if (dispute) return { name: "DisputeDetail", id: dispute[1] };
  const campaign = link.match(/^\/campaigns\/([^/?#]+)/);
  if (campaign) {
    /* Campaign detail is owner-only server-side; a creator holding this link
       answers the same event from their invitations. */
    return isBrand ? { name: "CampaignDetail", id: campaign[1] } : { name: "Invitations" };
  }
  // Messages and anything else without a mobile screen yet.
  return null;
}

function typeTarget(type: string, isBrand: boolean): NavTarget | null {
  // The two halves of the same question: a buyer reads GROSS spend, a
  // creator reads NET earnings.
  if (type === "payment") return isBrand ? { name: "Spend" } : { name: "Earnings" };
  if (type.startsWith("contract") || type === "deliverable") return { name: "Contracts" };
  if (type === "campaign_invitation" || type === "campaign_cancelled") {
    return isBrand ? null : { name: "Invitations" };
  }
  if (type === "direct_order" || type.startsWith("proposal")) {
    return isBrand ? { name: "Campaigns" } : { name: "Invitations" };
  }
  // message, dispute (linkless rows), security: no mobile screen to promise.
  return null;
}

/* "il y a 2 h", as a key and a number rather than a finished string — the
   caller keeps its own `t`. Computed on render; nothing in a bell is worth a
   ticking clock. */
export function relativeParts(iso: string): { key: string; n: number } {
  const d = parseApiDate(iso);
  const minutes = d ? Math.floor((Date.now() - d.getTime()) / 60000) : 0;
  if (minutes < 1) return { key: "notif.justNow", n: 0 };
  if (minutes < 60) return { key: "notif.minutesAgo", n: minutes };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { key: "notif.hoursAgo", n: hours };
  return { key: "notif.daysAgo", n: Math.floor(hours / 24) };
}
