/* Where a job has got to: still moving, or over.

   NEITHER A CONTRACT NOR A CAMPAIGN HAS A "COMPLETED" STATUS, and that is not
   a gap in the schema — it is that finishing is not something either of them
   does. A contract's status stops at `signed`; what happens after that is the
   MONEY, and the escrow is the thing that reaches an ending. A campaign's
   status never moves again once it is published; what ends it is the work
   underneath it finishing, or the brand calling it off.

   So "completed" is DERIVED, and derived here so that the campaign list and
   the contract list cannot drift apart on what the word means. The backend
   supplies the raw facts — contracts.service.list_my_contracts returns each
   row's escrow_status — and this file is the only place that turns them into
   a shelf.

   WHY THE CLIENT AND NOT THE SERVER. This decides which tab a row is filed
   under and nothing else: no money moves on it, no request is authorised by
   it, and both lists already hold their whole set in memory (see
   ListFilter's docstring for the same call). A mobile client will need this
   rule too and will have to restate it; that is the cost, and it is smaller
   than a second endpoint whose answer could disagree with this one. */

/* An ending the contract itself reached. `cancelled` is either party calling
   it off before it bound anybody (contracts.cancellation). `void` has never
   been written by any code path, but it means a contract that was never
   valid, which is an ending too — better listed here than silently treated as
   live if it ever starts being used. */
const ENDED_CONTRACT_STATUSES = new Set(["cancelled", "void"]);

/* An ending the MONEY reached. Released means the creator was paid; refunded
   means a dispute sent it back to the brand. Both are terminal.

   `held` and `disputed` are deliberately absent: held money is a job still
   running, and disputed money is a job actively going wrong. Neither belongs
   on the shelf with the finished work — a dispute filed under "Completed" is
   exactly the row somebody stops chasing. */
const SETTLED_ESCROW_STATUSES = new Set(["released", "refunded"]);

const CAMPAIGN_CANCELLED = "cancelled";

/* The shape both rules need. Structural rather than importing the pages' own
   row types, so neither list has to depend on the other's. */
export type CompletableContract = {
  campaign_id: string;
  status: string;
  /* null when nobody has funded it yet — a live state, not an ending. */
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
   produced has finished.

   THE SECOND CONDITION HAS TWO HALVES AND NEEDS BOTH. Every contract on it
   must have reached an ending — one creator still delivering keeps the whole
   brief live — AND at least one of those endings must have been a MONEY
   ending. Without that second half, a brief whose only deal fell through
   before anyone funded it would be filed as completed, when what it actually
   is is an open brief that is still taking proposals. Nothing was finished
   there; something was abandoned, and the brand can still work it.

   A campaign with no contracts at all is never complete by this rule, which
   is right for a draft and right for a published brief nobody has bid on
   yet: in both cases the brand has something left to do. */
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

/* Split a list into the two shelves in one pass, so a caller never has to
   run the predicate twice and risk the counts disagreeing with the rows. */
export function partitionByCompletion<T>(
  rows: T[],
  isCompleted: (row: T) => boolean
): { active: T[]; completed: T[] } {
  const active: T[] = [];
  const completed: T[] = [];
  for (const row of rows) (isCompleted(row) ? completed : active).push(row);
  return { active, completed };
}
