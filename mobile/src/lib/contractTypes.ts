/* Contracts, escrow and deliverable shapes, mirrored from web/src/lib/types.ts
   and web/src/lib/deliverables.ts (and the backend schemas behind them). Only
   what the mobile screens read is typed. */

export type Contract = {
  id: string;
  campaign_id: string;
  proposal_id: string;
  business_user_id: string;
  influencer_user_id: string;
  language: string;
  status: string;
  rate_amount: number;
  rate_currency: string;
  timeline_days: number;
  business_signed: boolean;
  influencer_signed: boolean;
  fully_signed: boolean;
};

/* A row of GET /contracts/mine: the base contract plus what the card needs to
   read at a glance. */
export type ContractListItem = Contract & {
  campaign_title: string | null;
  counterparty_name: string | null;
  counterparty_avatar_url: string | null;
  created_at: string;
  escrow_status: string | null;
};

export type ContractDetail = Contract & { body: string };

export type Escrow = {
  id: string;
  contract_id: string;
  campaign_id: string;
  business_user_id: string;
  influencer_user_id: string;
  amount: number;
  currency: string;
  commission_amount: number | null;
  status: string;
};

export type DeliverableStatus = "submitted" | "approved" | "changes_requested" | "withdrawn";

export type DeliverableSubmission = {
  id: string;
  contract_id: string;
  submitted_by_user_id: string;
  link_url: string | null;
  note: string | null;
  status: DeliverableStatus;
  review_note: string | null;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  attachments: string[];
};

/* The attempt the brand still owes an answer on, if any — found by status, not
   by taking the newest row (a contract sent back carries a closed newest row).
   Mirror of openSubmission in web/src/lib/deliverables.ts. */
export function openSubmission(rows: DeliverableSubmission[]): DeliverableSubmission | null {
  return rows.find((r) => r.status === "submitted") ?? null;
}

/* Mirrors settings.review_window_days; shown to the creator as a promise about
   when they get paid. Kept in sync with the backend by hand, like web. */
export const REVIEW_WINDOW_DAYS = 4;
