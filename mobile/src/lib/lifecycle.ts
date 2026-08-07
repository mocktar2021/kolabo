/* Where a job has got to: still moving, or over. Mirror of
   web/src/lib/lifecycle.ts, restated here exactly as that file predicted a
   mobile client would have to — the cost it accepted for keeping the rule
   client-side.

   Neither a contract nor a campaign has a "completed" status, and that is not
   a gap in the schema: a contract's status stops at `signed`, and what
   happens after that is the MONEY — the escrow is the thing that reaches an
   ending. So "completed" is DERIVED, and derived in one file so the campaign
   list and the contract list cannot drift apart on what the word means. */

/* An ending the contract itself reached. `void` has never been written by
   any code path, but it means a contract that was never valid, which is an
   ending too. */
const ENDED_CONTRACT_STATUSES = new Set(["cancelled", "void"]);

/* An ending the MONEY reached. `held` and `disputed` are deliberately
   absent: held money is a job still running, and disputed money is a job
   actively going wrong — a dispute filed under "Completed" is exactly the
   row somebody stops chasing. */
const SETTLED_ESCROW_STATUSES = new Set(["released", "refunded"]);

const CAMPAIGN_CANCELLED = "cancelled";

export type CompletableContract = {
  campaign_id: string;
  status: string;
  escrow_status: string | null;
};

export type CompletableCampaign = {
  id: string;
  status: string;
};

export function contractIsCompleted(c: CompletableContract): boolean {
  if (ENDED_CONTRACT_STATUSES.has(c.status)) return true;
  return c.escrow_status !== null && SETTLED_ESCROW_STATUSES.has(c.escrow_status);
}

/* A campaign is over when the brand called it off, or when everything it
   produced has finished. The second condition has two halves and needs both:
   every contract on it must have reached an ending — one creator still
   delivering keeps the whole brief live — AND at least one of those endings
   must have been a MONEY ending, or a brief whose only deal fell through
   unfunded would be filed as completed when it is actually still open. A
   campaign with no contracts at all is never complete by this rule. */
export function campaignIsCompleted(
  campaign: CompletableCampaign,
  contracts: CompletableContract[]
): boolean {
  if (campaign.status === CAMPAIGN_CANCELLED) return true;
  const mine = contracts.filter((c) => c.campaign_id === campaign.id);
  if (mine.length === 0) return false;
  if (!mine.every(contractIsCompleted)) return false;
  return mine.some(
    (c) => c.escrow_status !== null && SETTLED_ESCROW_STATUSES.has(c.escrow_status)
  );
}

/* Split a list into the two shelves in one pass, so a caller never runs the
   predicate twice and risks the counts disagreeing with the rows. */
export function partitionByCompletion<T>(
  rows: T[],
  isCompleted: (row: T) => boolean
): { active: T[]; completed: T[] } {
  const active: T[] = [];
  const completed: T[] = [];
  for (const row of rows) (isCompleted(row) ? completed : active).push(row);
  return { active, completed };
}
