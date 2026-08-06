/* The creator's earnings, mirrored from backend EarningsOut / EarningPaymentOut
   and web/src/lib/types.ts. Totals are maps of currency -> minor units and are
   NEVER summed across currencies; each figure is NET (the commission comes off
   at release). See the payments/earnings module and the web screen for the
   reasoning this UI is built around. */

export type EarningPayment = {
  escrow_id: string;
  contract_id: string;
  campaign_title: string | null;
  counterparty_name: string | null;
  gross: number;
  commission: number;
  net: number;
  currency: string;
  status: string;
  date: string | null;
};

export type Earnings = {
  earned: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  payments: EarningPayment[];
};

export type EarningKind = "earned" | "pending" | "disputed";

/* Which tile a row belongs to — a mirror of earningsTotals in
   web/src/lib/statement.ts (and payments/earnings.py) so the drill-down and
   the totals can never disagree: released is earned, disputed is disputed,
   everything else is pending. Refunded money never reaches the creator and so
   never appears. */
export function earningRowMatches(row: EarningPayment, kind: EarningKind): boolean {
  if (kind === "earned") return row.status === "released";
  if (kind === "disputed") return row.status === "disputed";
  return row.status !== "released" && row.status !== "disputed";
}
