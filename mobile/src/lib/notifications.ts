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
  | {
      name:
        | "Dashboard"
        | "Contracts"
        | "Campaigns"
        | "Invitations"
        | "Earnings"
        | "Spend"
        | "Messages"
        | "Disputes"
        | "Account"
        | "PayoutMethod"
        | "CreatorProfile"
        | "BusinessProfile";
    }
  | { name: "ContractDetail" | "CampaignDetail" | "DisputeDetail"; id: string }
  | { name: "MessageThread"; userId: string };

/* EVERY TYPE backend/app/modules CAN EMIT, read out of the Python by
   tests/notificationRouting.test.ts rather than trusted to this comment. The
   list exists so an unrecognised type can be told apart from a recognised one
   with nowhere to go — see targetFor, where those two answer differently.

   Grouped by the module that raises them:
     campaigns   campaign_invitation, campaign_cancelled, direct_order,
                 brief_application, proposal_submitted, proposal_reply,
                 proposal_closed
     contracts   contract_ready, contract_signed, contract_cancelled
     deliverables deliverable
     payments    payment, dispute
     messaging   message
     auth        security
     admin       verification
     trust_safety report */
export const NOTIFICATION_TYPES = [
  "brief_application",
  "campaign_cancelled",
  "campaign_invitation",
  "contract_cancelled",
  "contract_ready",
  "contract_signed",
  "deliverable",
  "direct_order",
  "dispute",
  "message",
  "payment",
  "proposal_closed",
  "proposal_reply",
  "proposal_submitted",
  "report",
  "security",
  "verification",
] as const;

export const KNOWN_TYPES: ReadonlySet<string> = new Set(NOTIFICATION_TYPES);

/* Where a notification opens.

   THE BACKEND'S `link` WINS. It is built at emit time, the only place the
   recipient's side is known — the same event links a brand to its
   /campaigns/{id} and a creator to /invitations — and it is the only thing on
   the row that names the RECORD rather than the area. It is a web path, so it
   is parsed into this app's screens rather than followed.

   THE TYPE IS THE FALLBACK, AND IT IS READ NEVER FROM THE MESSAGE. The type is
   a fixed vocabulary and real data on the row; the message is a sentence for a
   human, and any rule that read it would break the first time somebody
   reworded a string — silently, and into a wrong destination.

   THREE ANSWERS, NOT TWO, and the third is the point of KNOWN_TYPES:

     * a target — open that screen;
     * null — a type this app KNOWS and has no screen for (a verification
       document decision, a report being closed). The row marks itself read
       and goes nowhere, which is honest: inventing a destination would send
       somebody to a page that says nothing about what they tapped;
     * Dashboard — a type shipped on the backend that this build has never
       heard of. A tap that appears to do nothing reads as a broken app, so an
       unknown type lands on the home tab rather than being swallowed. Home is
       deliberately not a guess at the right screen: it is the one place that
       exists for both roles and can never be wrong about what the
       notification was about. */
export function targetFor(n: AppNotification, isBrand: boolean): NavTarget | null {
  const fromLink = linkTarget(n.link, isBrand);
  if (fromLink) return fromLink;
  const fromType = typeTarget(n.type, isBrand);
  if (fromType) return fromType;
  if (KNOWN_TYPES.has(n.type)) return null;
  return { name: "Dashboard" };
}

/* The path of a web link, without its query string or fragment. */
function pathOf(link: string): string {
  const cut = link.search(/[?#]/);
  return cut === -1 ? link : link.slice(0, cut);
}

/* One query parameter of a web link, decoded, or null.

   Hand-parsed rather than handed to URLSearchParams: this module is pure and
   is exercised under vitest's node environment as well as on a device, and a
   four-line split has no runtime to disagree about. */
function queryParam(link: string, name: string): string | null {
  const start = link.indexOf("?");
  if (start === -1) return null;
  const query = link.slice(start + 1).split("#")[0];
  for (const pair of query.split("&")) {
    const eq = pair.indexOf("=");
    if (eq === -1) continue;
    if (pair.slice(0, eq) !== name) continue;
    const value = decodeURIComponent(pair.slice(eq + 1));
    return value || null;
  }
  return null;
}

/* The record id in "/contracts/{id}" and friends. Deliberately NOT anchored
   at the end: a deeper path ("/campaigns/{id}/proposals") still names the same
   record, and the screen this app has for it is the same one. */
function idAfter(path: string, segment: string): string | null {
  const m = path.match(new RegExp(`^/${segment}/([^/]+)`));
  return m ? m[1] : null;
}

function linkTarget(link: string | null, isBrand: boolean): NavTarget | null {
  if (!link) return null;
  const path = pathOf(link);

  const contract = idAfter(path, "contracts");
  if (contract) return { name: "ContractDetail", id: contract };
  const dispute = idAfter(path, "disputes");
  if (dispute) return { name: "DisputeDetail", id: dispute };
  const campaign = idAfter(path, "campaigns");
  if (campaign) {
    /* Campaign detail is owner-only server-side; a creator holding this link
       answers the same event from their invitations. */
    return isBrand ? { name: "CampaignDetail", id: campaign } : { name: "Invitations" };
  }

  /* "/messages?campaign=<id>&with=<user id>" — the shape messaging.send_message
     and conversations.send_to both write. The mobile inbox is keyed by PERSON
     (GET /messaging/with/{userId}), so `with` is the whole address and the
     campaign is provenance this screen has no use for. Without a `with` there
     is no thread to open and the inbox is the honest answer. */
  if (path === "/messages") {
    const withUser = queryParam(link, "with");
    return withUser ? { name: "MessageThread", userId: withUser } : { name: "Messages" };
  }

  /* Where a creator (or a brand owed a refund) says which wallet to pay.
     payouts.disburse raises this one against BOTH sides, so it is not
     role-split: the screen is a form about the caller's own account. */
  if (path === "/settings/payouts") return { name: "PayoutMethod" };

  /* The two halves of the same question: a buyer reads GROSS spend, a creator
     reads NET earnings. Web spells the buyer's screen /payments. */
  if (path === "/earnings" || path === "/payments") {
    return isBrand ? { name: "Spend" } : { name: "Earnings" };
  }

  if (path === "/account") return { name: "Account" };
  /* Social accounts are managed on the profile form, which is a different
     screen for each side of the marketplace here. */
  if (path === "/profile") {
    return isBrand ? { name: "BusinessProfile" } : { name: "CreatorProfile" };
  }
  if (path === "/contracts") return { name: "Contracts" };
  if (path === "/disputes") return { name: "Disputes" };
  /* Invitations is a creator tab and Campaigns a brand one, so a link naming
     the wrong side of the marketplace is dropped rather than followed into a
     screen that is not mounted for this role — the type map answers instead. */
  if (path === "/invitations") return isBrand ? null : { name: "Invitations" };
  if (path === "/campaigns") return isBrand ? { name: "Campaigns" } : { name: "Invitations" };
  return null;
}

function typeTarget(type: string, isBrand: boolean): NavTarget | null {
  // The two halves of the same question: a buyer reads GROSS spend, a
  // creator reads NET earnings.
  if (type === "payment") return isBrand ? { name: "Spend" } : { name: "Earnings" };
  // contract_ready, contract_signed, contract_cancelled, and the work handed
  // in against one. Both parties have a contracts list and it is unguarded.
  if (type.startsWith("contract") || type === "deliverable") return { name: "Contracts" };
  // A dispute always carries a link to its own case; this is what a linkless
  // row (an old one) falls back to.
  if (type === "dispute") return { name: "Disputes" };
  // Likewise a message always names the sender, and the inbox is where a row
  // that does not goes.
  if (type === "message") return { name: "Messages" };
  // "Your password was changed" — the screen that can change it back.
  if (type === "security") return { name: "Account" };
  if (type === "campaign_invitation" || type === "campaign_cancelled") {
    return isBrand ? null : { name: "Invitations" };
  }
  /* A direct order is read from opposite ends: the buyer owns the hidden
     campaign, the creator answers it from their invitations. An application
     and every proposal_* — submitted, reply, closed — split the same way. */
  if (
    type === "direct_order" ||
    type === "brief_application" ||
    type.startsWith("proposal")
  ) {
    return isBrand ? { name: "Campaigns" } : { name: "Invitations" };
  }
  /* verification and report fall through on purpose. A social decision
     carries /profile and is answered by linkTarget above; a verification
     DOCUMENT decision and a closed report carry no link because this product
     has no screen for either, on mobile or on web. Guessing one would send
     somebody to a page that says nothing about what they tapped. */
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
