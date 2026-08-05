import { describe, expect, it } from "vitest";
import {
  campaignIsCompleted,
  contractIsCompleted,
  partitionByCompletion,
  type CompletableCampaign,
  type CompletableContract
} from "./lifecycle";

/* The Active/Completed split, which decides which shelf every campaign and
   contract is filed on.

   IT IS WORTH TESTING DESPITE BEING "JUST DISPLAY", because the failure is
   silent and the wrong direction is the dangerous one. A row wrongly filed as
   Completed does not error — it disappears from the list somebody checks to
   see what still needs doing, and the first sign of trouble is a creator
   asking why nobody looked at their work. Every case below that expects
   `false` is guarding that direction. */

function contract(over: Partial<CompletableContract> = {}): CompletableContract {
  return { campaign_id: "camp-1", status: "signed", escrow_status: null, ...over };
}

function campaign(over: Partial<CompletableCampaign> = {}): CompletableCampaign {
  return { id: "camp-1", status: "published", ...over };
}

describe("contractIsCompleted", () => {
  it("is false while the contract is still waiting for signatures", () => {
    expect(contractIsCompleted(contract({ status: "pending_signatures" }))).toBe(false);
  });

  it("is false for a signed contract nobody has funded", () => {
    // The commonest live state there is: terms agreed, money not yet in.
    expect(contractIsCompleted(contract({ escrow_status: null }))).toBe(false);
  });

  it("is false while the money is held", () => {
    expect(contractIsCompleted(contract({ escrow_status: "held" }))).toBe(false);
  });

  it("is false while the money is disputed", () => {
    /* The case most worth pinning. A dispute is a job actively going wrong,
       and filing it under Completed is exactly the row somebody stops
       chasing — the money would sit frozen with nobody watching it. */
    expect(contractIsCompleted(contract({ escrow_status: "disputed" }))).toBe(false);
  });

  it("is true once the escrow is released", () => {
    expect(contractIsCompleted(contract({ escrow_status: "released" }))).toBe(true);
  });

  it("is true once the escrow is refunded", () => {
    // A dispute that sent the money back is still an ending.
    expect(contractIsCompleted(contract({ escrow_status: "refunded" }))).toBe(true);
  });

  it("is true when the contract itself was cancelled or voided", () => {
    // Endings the document reached rather than the money — no escrow needed.
    expect(contractIsCompleted(contract({ status: "cancelled" }))).toBe(true);
    expect(contractIsCompleted(contract({ status: "void" }))).toBe(true);
  });
});

describe("campaignIsCompleted", () => {
  it("is true when the brand called it off, whatever is underneath", () => {
    expect(campaignIsCompleted(campaign({ status: "cancelled" }), [])).toBe(true);
  });

  it("is false for a draft and for a published brief with no contracts", () => {
    // In both cases the brand still has something left to do.
    expect(campaignIsCompleted(campaign({ status: "draft" }), [])).toBe(false);
    expect(campaignIsCompleted(campaign(), [])).toBe(false);
  });

  it("is true once its only contract has been paid out", () => {
    expect(campaignIsCompleted(campaign(), [contract({ escrow_status: "released" })])).toBe(true);
  });

  it("is false while any one of its contracts is still running", () => {
    /* One creator still delivering keeps the whole brief live. A brief that
       went Completed here would hide work the brand still owes a review. */
    const rows = [contract({ escrow_status: "released" }), contract({ escrow_status: "held" })];
    expect(campaignIsCompleted(campaign(), rows)).toBe(false);
  });

  it("is true when one contract paid out and another was cancelled", () => {
    const rows = [
      contract({ escrow_status: "released" }),
      contract({ status: "cancelled" })
    ];
    expect(campaignIsCompleted(campaign(), rows)).toBe(true);
  });

  it("is FALSE when its only deal fell through before anyone funded it", () => {
    /* THE TWO-HALVES RULE, and the reason it has a second half at all.
       Every contract has ended, so the first half is satisfied — but no money
       ever moved. Nothing was finished here; something was abandoned, and
       what the brand is left holding is an open brief that is still taking
       proposals. Filing it as Completed would bury a brief they can still
       work. */
    expect(campaignIsCompleted(campaign(), [contract({ status: "cancelled" })])).toBe(false);
    expect(
      campaignIsCompleted(campaign(), [
        contract({ status: "cancelled" }),
        contract({ status: "cancelled" })
      ])
    ).toBe(false);
  });

  it("is true when the money came back after a dispute", () => {
    // Refunded is a money ending, so the second half is satisfied.
    expect(campaignIsCompleted(campaign(), [contract({ escrow_status: "refunded" })])).toBe(true);
  });

  it("ignores contracts belonging to other campaigns", () => {
    /* The caller hands in EVERY contract they are a party to, so the rule has
       to select its own. Without the filter, one finished job would mark
       every other brief on the account as complete. */
    const other = contract({ campaign_id: "camp-2", escrow_status: "released" });
    expect(campaignIsCompleted(campaign({ id: "camp-1" }), [other])).toBe(false);

    const mine = contract({ campaign_id: "camp-1", escrow_status: "held" });
    expect(campaignIsCompleted(campaign({ id: "camp-1" }), [other, mine])).toBe(false);
  });
});

describe("partitionByCompletion", () => {
  it("splits the rows and keeps each side in its original order", () => {
    const rows = [
      contract({ campaign_id: "a", escrow_status: "released" }),
      contract({ campaign_id: "b", escrow_status: "held" }),
      contract({ campaign_id: "c", status: "cancelled" }),
      contract({ campaign_id: "d", escrow_status: null })
    ];
    const { active, completed } = partitionByCompletion(rows, contractIsCompleted);

    expect(active.map((r) => r.campaign_id)).toEqual(["b", "d"]);
    expect(completed.map((r) => r.campaign_id)).toEqual(["a", "c"]);
  });

  it("accounts for every row exactly once, which is what the tab counts show", () => {
    const rows = [
      contract({ escrow_status: "released" }),
      contract({ escrow_status: "held" }),
      contract({ escrow_status: "disputed" })
    ];
    const { active, completed } = partitionByCompletion(rows, contractIsCompleted);
    expect(active.length + completed.length).toBe(rows.length);
  });

  it("handles an empty list", () => {
    expect(partitionByCompletion([], contractIsCompleted)).toEqual({ active: [], completed: [] });
  });
});
