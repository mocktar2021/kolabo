/* Narrowing a money statement, shared by the creator's earnings screen and
   the buyer's spend screen.

   ONE MODULE FOR BOTH, for the reason payments/filters.py is one object on
   the server: the two screens ask the same four questions — when, on which
   campaign, with whom — and the answers have to mean the same thing on both.
   Two copies of "is this row in the range" is two chances for one of them to
   make a bound exclusive, and the first anybody would know about it is a
   creator and a brand quoting each other different totals for the same
   contract.

   THE FILTER NARROWS THE TOTALS AND THE LIST TOGETHER. That is the whole
   rule. A filtered list sitting beside all-time totals is not a smaller view
   of the truth, it is two different questions answered on one screen:
   somebody who asked for March sees a March statement under an all-time
   figure, adds up the rows, gets a different number, and concludes our
   arithmetic is broken.

   WHY THE WORK IS SPLIT BETWEEN THE SERVER AND HERE, which is the one
   surprising thing in this file.

     THE PERIOD GOES TO THE SERVER. /payments/earnings and /payments/spend
     both take year, from_date and to_date, and payments/filters.py narrows
     the totals and the list together from them — authoritatively, over every
     escrow, not just the hundred rows the list carries. So the period
     controls re-fetch, and the totals that come back are the server's.

     THE CAMPAIGN AND THE COUNTERPARTY ARE FILTERED HERE. The endpoints take
     campaign_id and counterparty_id, and THE ROWS DO NOT CARRY EITHER ID:
     EarningPaymentOut and SpendPaymentOut ship campaign_title and
     counterparty_name and nothing else to identify them by. A selector built
     out of the rows the page already has — which is the whole point of not
     adding an endpoint for it — therefore has no id to send, so it matches on
     the displayed name instead and the totals are rebuilt from the rows that
     survive.

     THE BOUND THAT CREATES, said out loud: rebuilt totals are computed from
     the payments LIST, which the server caps at 100 rows. Below that cap they
     equal the server's to the unit. Above it a campaign filter would
     understate. At pilot volume nobody is near it, and the fix is a
     campaign_id on the statement row rather than anything in this file — at
     which point the whole client-side half of this module goes away. */
import { parseApiDate } from "./orders";
import type { EarningPayment, SpendPayment } from "./types";

/* What the filter row holds. Strings rather than Dates for the two bounds
   because they come straight off <input type="date">, which speaks
   "YYYY-MM-DD" — the same spelling the API's from_date and to_date take, so
   the value is never parsed and re-formatted on its way to the query. */
export type StatementFilter = {
  year: number | null;
  from: string;
  to: string;
  /* Matched against campaign_title and counterparty_name, not against ids.
     See the module docstring. "" means "all". */
  campaign: string;
  counterparty: string;
};

export const NO_FILTER: StatementFilter = {
  year: null,
  from: "",
  to: "",
  campaign: "",
  counterparty: ""
};

/* Is anything narrowed at all? What the "Totaux filtrés" line is driven by:
   the moment ONE of the four is set, the figures on screen stop being the
   all-time ones and the screen has to say so. */
export function isFiltered(f: StatementFilter): boolean {
  return f.year !== null || f.from !== "" || f.to !== "" || f.campaign !== "" || f.counterparty !== "";
}

/* The half the server answers, as a query string ("" when there is none).

   year and a date range compose as an INTERSECTION server-side, so sending
   both is not a conflict to resolve here: year=2025 with a March window means
   March 2025, and a contradictory pair honestly answers zero rows. */
export function serverQuery(f: StatementFilter): string {
  const qs = new URLSearchParams();
  if (f.year !== null) qs.set("year", String(f.year));
  if (f.from) qs.set("from_date", f.from);
  if (f.to) qs.set("to_date", f.to);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

/* Is the client doing any narrowing of its own? When it is, the totals on
   screen have to be rebuilt from the surviving rows, because the ones the
   server sent answer a wider question than the list underneath them. */
export function filtersLocally(f: StatementFilter): boolean {
  return f.campaign !== "" || f.counterparty !== "";
}

/* The two fields the local half matches on. Both statement rows have them,
   which is what lets one function serve both screens. */
type NamedRow = { campaign_title: string | null; counterparty_name: string | null };

export function applyLocalFilter<T extends NamedRow>(rows: T[], f: StatementFilter): T[] {
  if (!filtersLocally(f)) return rows;
  return rows.filter(
    (r) =>
      (f.campaign === "" || r.campaign_title === f.campaign) &&
      (f.counterparty === "" || r.counterparty_name === f.counterparty)
  );
}

export type StatementOptions = {
  years: number[];
  campaigns: string[];
  counterparties: string[];
};

export const NO_OPTIONS: StatementOptions = { years: [], campaigns: [], counterparties: [] };

/* Is there anything worth offering? A filter row over a statement with one
   campaign and one counterparty on it is a set of controls that can only ever
   reproduce the page somebody is already looking at. */
export function hasOptions(o: StatementOptions): boolean {
  return o.years.length > 1 || o.campaigns.length > 1 || o.counterparties.length > 1;
}

/* The choices, read off the rows themselves rather than from an endpoint.

   DERIVED FROM THE UNFILTERED RESPONSE AND THEN KEPT, which is the rule the
   year selector has always run on: recomputing them from a FILTERED response
   would leave each droplist holding only the value already chosen, with no
   way back to the others.

   A row with no title or no name contributes no option. It is not an
   "unknown" bucket to select — nothing on the server would match it — and an
   empty entry in a droplist is worse than an absent one. Such a row still
   shows on the unfiltered screen, where no claim about it is being made. */
export function optionsFrom(rows: (NamedRow & { date: string | null })[]): StatementOptions {
  const years = new Set<number>();
  const campaigns = new Set<string>();
  const counterparties = new Set<string>();
  for (const row of rows) {
    // Naive UTC from the API, so it goes through parseApiDate before a year
    // is read off it — a payment settled at 23:40 UTC on 31 December is not
    // last year's for a reader in Accra and this year's for one in Douala.
    if (row.date) years.add(new Date(parseApiDate(row.date)).getUTCFullYear());
    if (row.campaign_title) campaigns.add(row.campaign_title);
    if (row.counterparty_name) counterparties.add(row.counterparty_name);
  }
  return {
    years: Array.from(years).sort((a, b) => b - a),
    campaigns: Array.from(campaigns).sort((a, b) => a.localeCompare(b)),
    counterparties: Array.from(counterparties).sort((a, b) => a.localeCompare(b))
  };
}

function add(bucket: Record<string, number>, currency: string, amount: number): void {
  bucket[currency] = (bucket[currency] ?? 0) + amount;
}

/* The creator's three totals, rebuilt from a filtered list.

   A MIRROR OF app/modules/payments/earnings.py AND NOTHING MORE: released
   money is earned, disputed money is disputed, everything else is pending,
   and the figure taken is NET because every figure on that screen is net.
   REFUNDED never appears — the endpoint does not count it, because money
   returned to the buyer never reached the creator at all.

   Keyed by currency and never summed across them, exactly as the server
   does it: XOF and GHS are not addends. */
export function earningsTotals(rows: EarningPayment[]): {
  earned: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
} {
  const earned: Record<string, number> = {};
  const pending: Record<string, number> = {};
  const disputed: Record<string, number> = {};
  for (const row of rows) {
    const bucket = row.status === "released" ? earned : row.status === "disputed" ? disputed : pending;
    add(bucket, row.currency, row.net);
  }
  return { earned, pending, disputed };
}

/* The buyer's four totals, rebuilt from a filtered list.

   A MIRROR OF app/modules/payments/spend.py: released money is spent, a fully
   refunded escrow is refunded, disputed money is disputed, everything else is
   pending — and the figure is GROSS, because the commission came out of the
   creator's release and not out of the buyer's payment.

   refunded_amount is added on top wherever it is non-zero, which is what
   makes a dispute split land in two buckets from one row: the released half
   in spent, the returned half in refunded. That is what actually happened to
   the money, and dropping it would understate the refunded total by exactly
   the amount the buyer got back. */
export function spendTotals(rows: SpendPayment[]): {
  spent: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  refunded: Record<string, number>;
} {
  const spent: Record<string, number> = {};
  const pending: Record<string, number> = {};
  const disputed: Record<string, number> = {};
  const refunded: Record<string, number> = {};
  for (const row of rows) {
    const bucket =
      row.status === "released"
        ? spent
        : row.status === "refunded"
          ? refunded
          : row.status === "disputed"
            ? disputed
            : pending;
    add(bucket, row.currency, row.amount);
    if (row.refunded_amount > 0) add(refunded, row.currency, row.refunded_amount);
  }
  return { spent, pending, disputed, refunded };
}

/* Which tile a statement row belongs to, mirroring the bucket logic in
   spendTotals / earningsTotals exactly so the drill-down and the totals can
   never disagree about what a row is. Used to narrow the statement TABLE when
   a buyer or creator clicks one of the tiles above it: the tile stays a
   category total, and clicking it shows the rows behind that total.

   A split row (released, with refunded_amount > 0) matches BOTH "spent" and
   "refunded", exactly as it lands in both buckets above — the released half is
   spend, the returned half is a refund, and it is honest for the one row to
   show under either tile. */
export type SpendKind = "spent" | "pending" | "disputed" | "refunded";
export type EarningKind = "earned" | "pending" | "disputed";

export function spendRowMatches(row: SpendPayment, kind: SpendKind): boolean {
  if (kind === "spent") return row.status === "released";
  if (kind === "refunded") return row.status === "refunded" || row.refunded_amount > 0;
  if (kind === "disputed") return row.status === "disputed";
  // pending: what the other three do not claim, i.e. held.
  return row.status !== "released" && row.status !== "refunded" && row.status !== "disputed";
}

export function earningRowMatches(row: EarningPayment, kind: EarningKind): boolean {
  if (kind === "earned") return row.status === "released";
  if (kind === "disputed") return row.status === "disputed";
  // pending: not released and not disputed.
  return row.status !== "released" && row.status !== "disputed";
}
