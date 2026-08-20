/* Tapping a notification has to open the RECORD it is about.

   The bug this pins was reported from an Android handset in one sentence:
   "when clicking on order notification, it is not opening the order itself".
   It was not one broken branch. The resolver understood three link shapes out
   of nine and five types out of seventeen, so a whole column of the bell —
   messages, the password-changed warning, a dispute with no link, and the
   "add your Mobile Money details" row that decided where a creator's money
   goes — did nothing at all when tapped. The order case was simply the one
   somebody hit first.

   THE MATRIX BELOW IS THE FIX. Every (type, link) pair backend/app/modules can
   emit, and where it must land for a brand and for a creator. It is written
   out rather than derived, because a table derived from the same code it
   checks agrees with itself by construction.

   AND THE PYTHON IS READ, so the table cannot go quietly stale. A type shipped
   on the backend that this app has never heard of fails the first test here —
   which is the failure that matters, because the client's answer to an unknown
   type is a fallback, and a fallback that is silently doing real work is the
   bug coming back. */
import { describe, expect, it } from "vitest";

import { NOTIFICATION_TYPE, assertBackendIsThere, literals } from "./backendKeys";
import {
  KNOWN_TYPES,
  NOTIFICATION_TYPES,
  targetFor,
  type AppNotification,
  type NavTarget,
} from "../src/lib/notifications";

const CONTRACT = "c-1";
const CAMPAIGN = "k-1";
const DISPUTE = "d-1";
const SENDER = "u-9";

function row(type: string, link: string | null): AppNotification {
  return {
    id: "n-1",
    type,
    message: "whatever the backend also emailed",
    link,
    params: null,
    is_read: false,
    created_at: "2026-08-19T09:12:00",
  };
}

type Case = {
  type: string;
  link: string | null;
  /* What raises it, so a failure names the call site rather than a row index. */
  from: string;
  brand: NavTarget | null;
  creator: NavTarget | null;
};

/* Every notify() in backend/app/modules, by the (type, link) pair it writes.
   Where an event only ever reaches one side of the marketplace the other side
   is still asserted: a brand must never be sent to a creator-only tab, and the
   answer for the side that cannot receive it is part of the contract. */
const MATRIX: Case[] = [
  // ---- campaigns -------------------------------------------------------
  {
    type: "campaign_invitation",
    link: null,
    from: "campaigns/service.py invite_creator",
    brand: null,
    creator: { name: "Invitations" },
  },
  {
    type: "campaign_invitation",
    link: "/invitations",
    from: "campaigns/withdrawals.py withdraw_invitation",
    brand: null,
    creator: { name: "Invitations" },
  },
  {
    type: "campaign_cancelled",
    link: "/invitations",
    from: "campaigns/editing.py cancel_campaign",
    brand: null,
    creator: { name: "Invitations" },
  },
  {
    type: "direct_order",
    link: null,
    from: "campaigns/service.py _place_order",
    brand: { name: "Campaigns" },
    creator: { name: "Invitations" },
  },
  {
    /* THE FOUNDER'S CASE. The buyer's order was accepted and the contract it
       produced is what they now have to sign — so the tap opens that contract,
       not the campaigns list. */
    type: "direct_order",
    link: `/contracts/${CONTRACT}`,
    from: "campaigns/orders.py accept_direct_order",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  {
    type: "direct_order",
    link: `/campaigns/${CAMPAIGN}`,
    from: "campaigns/orders.py decline_direct_order, expire_stale_orders (brand)",
    brand: { name: "CampaignDetail", id: CAMPAIGN },
    creator: { name: "Invitations" },
  },
  {
    type: "direct_order",
    link: "/invitations",
    from: "campaigns/orders.py expire_stale_orders (creator)",
    brand: { name: "Campaigns" },
    creator: { name: "Invitations" },
  },
  {
    type: "brief_application",
    link: `/campaigns/${CAMPAIGN}`,
    from: "campaigns/service.py submit_proposal (is_application)",
    brand: { name: "CampaignDetail", id: CAMPAIGN },
    creator: { name: "Invitations" },
  },
  {
    type: "proposal_submitted",
    link: `/campaigns/${CAMPAIGN}`,
    from: "campaigns/service.py submit_proposal, campaigns/withdrawals.py withdraw_proposal",
    brand: { name: "CampaignDetail", id: CAMPAIGN },
    creator: { name: "Invitations" },
  },
  {
    type: "proposal_reply",
    link: null,
    from: "campaigns/service.py reply_to_proposal",
    brand: { name: "Campaigns" },
    creator: { name: "Invitations" },
  },
  {
    type: "proposal_closed",
    link: "/invitations",
    from: "campaigns/completion.py close_open_offers",
    brand: { name: "Campaigns" },
    creator: { name: "Invitations" },
  },
  // ---- contracts and deliverables --------------------------------------
  {
    type: "contract_ready",
    link: `/contracts/${CONTRACT}`,
    from: "contracts/service.py generate_from_proposal",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  {
    type: "contract_signed",
    link: `/contracts/${CONTRACT}`,
    from: "contracts/service.py sign_contract",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  {
    type: "contract_cancelled",
    link: `/contracts/${CONTRACT}`,
    from: "contracts/cancellation.py cancel_contract",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  {
    type: "deliverable",
    link: `/contracts/${CONTRACT}`,
    from: "deliverables/service.py submit, request_changes",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  // ---- money -----------------------------------------------------------
  {
    type: "payment",
    link: `/contracts/${CONTRACT}`,
    from: "payments/service.py hold_funds, _release, _refund, run_non_delivery_refunds",
    brand: { name: "ContractDetail", id: CONTRACT },
    creator: { name: "ContractDetail", id: CONTRACT },
  },
  {
    type: "payment",
    link: `/disputes/${DISPUTE}`,
    from: "payments/resolution.py resolve_dispute",
    brand: { name: "DisputeDetail", id: DISPUTE },
    creator: { name: "DisputeDetail", id: DISPUTE },
  },
  {
    /* The row that used to land on Earnings, a screen with no payout section
       and no way onward. payouts.disburse raises it against whichever side is
       owed, so it is not creator-only. */
    type: "payment",
    link: "/settings/payouts",
    from: "payments/payouts.py disburse (no payout method)",
    brand: { name: "PayoutMethod" },
    creator: { name: "PayoutMethod" },
  },
  {
    type: "payment",
    link: "/earnings",
    from: "payments/payouts.py _notify_paid",
    brand: { name: "Spend" },
    creator: { name: "Earnings" },
  },
  {
    type: "dispute",
    link: `/disputes/${DISPUTE}`,
    from: "payments/disputes.py raise_dispute, post_message, withdraw_dispute, _escalate",
    brand: { name: "DisputeDetail", id: DISPUTE },
    creator: { name: "DisputeDetail", id: DISPUTE },
  },
  // ---- messaging, account, moderation ----------------------------------
  {
    type: "message",
    link: `/messages?campaign=${CAMPAIGN}&with=${SENDER}`,
    from: "messaging/service.py send_message, messaging/conversations.py send_to",
    brand: { name: "MessageThread", userId: SENDER },
    creator: { name: "MessageThread", userId: SENDER },
  },
  {
    type: "security",
    link: "/account",
    from: "auth/account.py _notify_password_changed",
    brand: { name: "Account" },
    creator: { name: "Account" },
  },
  {
    type: "verification",
    link: "/profile",
    from: "admin/service.py decide_social",
    brand: { name: "BusinessProfile" },
    creator: { name: "CreatorProfile" },
  },
  {
    /* No screen anywhere in this product reads a verification DOCUMENT's
       status — web has none either. Null, and the row says so by not
       responding to a press, rather than a guess at /account. */
    type: "verification",
    link: null,
    from: "admin/service.py decide_document",
    brand: null,
    creator: null,
  },
  {
    /* Same: nobody can read their own reports on any surface. */
    type: "report",
    link: null,
    from: "trust_safety/service.py resolve_report",
    brand: null,
    creator: null,
  },
];

/* The type map on its own, which is what a row with no link falls back to.
   Most of these pairs are unreachable today because the call site always
   sends a link — they are the safety net under a call site that stops. */
const TYPE_FALLBACKS: Case[] = [
  { type: "payment", link: null, from: "type map", brand: { name: "Spend" }, creator: { name: "Earnings" } },
  { type: "dispute", link: null, from: "type map", brand: { name: "Disputes" }, creator: { name: "Disputes" } },
  { type: "message", link: null, from: "type map", brand: { name: "Messages" }, creator: { name: "Messages" } },
  { type: "security", link: null, from: "type map", brand: { name: "Account" }, creator: { name: "Account" } },
  { type: "contract_ready", link: null, from: "type map", brand: { name: "Contracts" }, creator: { name: "Contracts" } },
  { type: "contract_signed", link: null, from: "type map", brand: { name: "Contracts" }, creator: { name: "Contracts" } },
  { type: "contract_cancelled", link: null, from: "type map", brand: { name: "Contracts" }, creator: { name: "Contracts" } },
  { type: "deliverable", link: null, from: "type map", brand: { name: "Contracts" }, creator: { name: "Contracts" } },
  { type: "brief_application", link: null, from: "type map", brand: { name: "Campaigns" }, creator: { name: "Invitations" } },
  { type: "proposal_submitted", link: null, from: "type map", brand: { name: "Campaigns" }, creator: { name: "Invitations" } },
  { type: "proposal_closed", link: null, from: "type map", brand: { name: "Campaigns" }, creator: { name: "Invitations" } },
];

function check(cases: Case[]): string[] {
  const wrong: string[] = [];
  for (const c of cases) {
    for (const [role, isBrand, want] of [
      ["brand", true, c.brand],
      ["creator", false, c.creator],
    ] as const) {
      const got = targetFor(row(c.type, c.link), isBrand);
      if (JSON.stringify(got) !== JSON.stringify(want)) {
        wrong.push(
          `${c.type} link=${c.link ?? "null"} as ${role} (${c.from}): ` +
            `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`
        );
      }
    }
  }
  return wrong;
}

describe("every notification opens the record it is about", () => {
  it("routes every (type, link) pair the backend emits", () => {
    expect(check(MATRIX)).toEqual([]);
  });

  it("routes by type when the row carries no link", () => {
    expect(check(TYPE_FALLBACKS)).toEqual([]);
  });

  it("never sends a brand to a creator-only tab, or the reverse", () => {
    /* Invitations and Board are mounted only for a creator; Campaigns and
       Discover only for a brand. Navigating to a route that is not mounted for
       this role is a tap that does nothing, which is the bug this file is
       about wearing a different hat. */
    const brandOnly = new Set(["Campaigns", "Discover"]);
    const creatorOnly = new Set(["Invitations", "Board"]);
    const wrong: string[] = [];
    for (const c of [...MATRIX, ...TYPE_FALLBACKS]) {
      const asBrand = targetFor(row(c.type, c.link), true);
      const asCreator = targetFor(row(c.type, c.link), false);
      if (asBrand && creatorOnly.has(asBrand.name)) wrong.push(`${c.type} sends a brand to ${asBrand.name}`);
      if (asCreator && brandOnly.has(asCreator.name)) wrong.push(`${c.type} sends a creator to ${asCreator.name}`);
    }
    expect(wrong).toEqual([]);
  });
});

describe("the ends of the map", () => {
  it("sends an unrecognised type to the home tab rather than nowhere", () => {
    /* Visible beats correct-but-silent here. A type this build has never heard
       of cannot be routed honestly, and a tap that appears to do nothing reads
       as a broken app — so it lands on the one screen both roles have. */
    expect(targetFor(row("something_shipped_later", null), true)).toEqual({ name: "Dashboard" });
    expect(targetFor(row("something_shipped_later", null), false)).toEqual({ name: "Dashboard" });
  });

  it("still follows the link of an unrecognised type", () => {
    /* The link is data the backend built at emit time; not knowing the type is
       no reason to ignore it. */
    expect(targetFor(row("something_shipped_later", `/contracts/${CONTRACT}`), false)).toEqual({
      name: "ContractDetail",
      id: CONTRACT,
    });
  });

  it("opens the inbox for a message link with no counterparty on it", () => {
    expect(targetFor(row("message", "/messages"), false)).toEqual({ name: "Messages" });
  });

  it("reads a percent-encoded counterparty out of a message link", () => {
    expect(targetFor(row("message", "/messages?with=a%2Fb"), false)).toEqual({
      name: "MessageThread",
      userId: "a/b",
    });
  });

  it("opens the record named by a deeper path", () => {
    expect(targetFor(row("deliverable", `/contracts/${CONTRACT}/deliverables`), true)).toEqual({
      name: "ContractDetail",
      id: CONTRACT,
    });
  });

  it("ignores a query string when matching a record path", () => {
    expect(targetFor(row("dispute", `/disputes/${DISPUTE}?tab=evidence`), true)).toEqual({
      name: "DisputeDetail",
      id: DISPUTE,
    });
  });
});

describe("the map is checked against the Python, not against itself", () => {
  it("can see the backend modules", () => {
    expect(() => assertBackendIsThere()).not.toThrow();
  });

  it("finds the notify() call sites at all", () => {
    /* A scanner that matched nothing would make every test below pass over an
       empty set. These types have been emitted since before this file existed;
       if the scan cannot see them, it is the scan that is broken. */
    const emitted = literals(NOTIFICATION_TYPE);
    const canaries = ["payment", "dispute", "message", "deliverable", "security", "verification", "report"];
    expect(canaries.filter((t) => !emitted.has(t))).toEqual([]);
  });

  it("knows every type the backend can emit", () => {
    const unrouted: string[] = [];
    for (const [type, files] of literals(NOTIFICATION_TYPE)) {
      if (!KNOWN_TYPES.has(type)) unrouted.push(`${type} emitted by ${files.join(", ")}`);
    }
    expect(unrouted).toEqual([]);
  });

  it("gives every type it knows a decision for both roles", () => {
    /* Not necessarily a screen — verification and report have none — but a
       DECISION: null, and never the unknown-type fallback, which would mean
       the type list and the route map had drifted apart. */
    const guessed: string[] = [];
    for (const type of NOTIFICATION_TYPES) {
      for (const isBrand of [true, false]) {
        const got = targetFor(row(type, null), isBrand);
        if (got && got.name === "Dashboard") guessed.push(`${type} (isBrand=${isBrand})`);
      }
    }
    expect(guessed).toEqual([]);
  });

  it("reports types this app lists that no call site emits", () => {
    /* The other direction is NOT an error: a type can outlive the call site
       that raised it. Recorded as a count so the drift is visible in the run.
       The bodies test keeps the same asymmetry for the same reason. */
    const emitted = new Set(literals(NOTIFICATION_TYPE).keys());
    const unused = NOTIFICATION_TYPES.filter((t) => !emitted.has(t));
    expect(unused.length).toBeLessThan(NOTIFICATION_TYPES.length);
  });
});
