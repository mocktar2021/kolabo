/* The buyer's money, mirrored from backend SpendOut / SpendPaymentOut. Four
   states, never summed across currencies. Unlike the creator's earnings there
   is NO commission column — the platform's cut comes off the creator's
   release, not the buyer's payment — and `refunded` is its own state because
   money that came back is a real line in a buyer's ledger. */

export type SpendPayment = {
  escrow_id: string;
  contract_id: string;
  campaign_title: string | null;
  counterparty_name: string | null;
  amount: number;
  /* The part of this contract that came back after a dispute split. Zero on
     almost every row; shown on the line so a split doesn't leave money in a
     total with no row to trace it to. */
  refunded_amount: number;
  currency: string;
  status: string;
  date: string | null;
};

export type Spend = {
  spent: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  refunded: Record<string, number>;
  payments: SpendPayment[];
};
