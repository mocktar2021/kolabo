import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { StatementFilters } from "../components/StatementFilters";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import {
  NO_FILTER,
  NO_OPTIONS,
  applyLocalFilter,
  filtersLocally,
  hasOptions,
  isFiltered,
  optionsFrom,
  serverQuery,
  spendTotals,
  type StatementFilter,
  type StatementOptions
} from "../lib/statement";
import type { Spend, SpendPayment } from "../lib/types";

/* What a buyer has spent, has committed, and has had come back.

   THE MIRROR OF /earnings AND DELIBERATELY NOT THE SAME SCREEN. The routing
   sends a creator here back to the dashboard and a business away from
   /earnings, and the reason is not tidiness — the same words mean opposite
   things on the two sides of an escrow:

     A BUYER PAYS GROSS, A CREATOR RECEIVES NET. The platform's cut comes off
     the creator's release, not the brand's payment: a brand that funded
     100000 XOF paid 100000 XOF whatever the creator ended up with, so there
     is no commission column here and no "net" figure to quote. Putting one
     on this screen would invite a brand to think it had been charged
     something it was not.

     REFUNDS ARE A LINE HERE AND NO LINE AT ALL THERE. Money that came back is
     something the buyer paid and got back, and both halves have to be visible
     or the arithmetic does not close. For the creator it never arrived.

     "EN ATTENTE" MEANS THE OPPOSITE THING. To a creator it is money on its
     way to them; to a buyer it is money already gone from their wallet,
     committed against work nobody has signed off yet.

   NOTHING IS EVER SUMMED ACROSS CURRENCIES, exactly as on the creator's
   screen and for the same reason: XOF and GHS are not addends, and a brand
   running in two markets has two budgets rather than one meaningless total.
   The API returns each figure as a map keyed by currency and this page
   renders one group of tiles per currency.

   AND THE FILTER NARROWS THE TOTALS WITH THE LIST, from the same shared
   definition the creator's screen uses — a brand and a creator narrowing the
   same contract to the same month are answered by one rule. See
   lib/statement.ts. */

/* Rendered as the API sends it, grouped for the active locale with the
   currency code beside — the same way the escrow rows on the contract page
   and the lines of the earnings statement are shown. */
function amount(value: number, currency: string, locale: string): string {
  return `${value.toLocaleString(locale)} ${currency}`;
}

function Tile({ label, hint, value }: { label: string; hint: string; value: string }) {
  return (
    <div className="card" style={{ margin: 0 }}>
      <div className="muted" style={{ fontSize: 12.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 24, marginTop: 4 }}>{value}</div>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>{hint}</div>
    </div>
  );
}

/* The escrow status of the payment, as a chip. Its own copy of the tones
   rather than a shared one with the earnings screen, because the two screens
   do not see the same set: REFUNDED reaches a buyer's statement and never
   reaches a creator's. The labels are the ones the contract page already uses
   for the same statuses, with the raw value as the fallback so a status added
   server-side renders as itself rather than as a missing key. */
function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const tone =
    status === "released"
      ? { color: "var(--teal-600)", background: "#e7f6f0" }
      : status === "disputed" || status === "refunded"
        ? { color: "var(--danger)", background: "var(--surface-2)" }
        : { color: "var(--muted)", background: "var(--surface-2)" };
  return (
    <span style={{ fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap", ...tone }}>
      {t(`escrow.status_${status}`, status)}
    </span>
  );
}

/* Four totals, each a map of currency to amount. Written out rather than
   inferred because the memo below has an early return for "no data yet", and
   an empty object literal infers as {} — which cannot be indexed by a
   currency code. */
type SpendTotals = {
  spent: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  refunded: Record<string, number>;
};

export default function PaymentsPage() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<Spend | null>(null);
  const [filter, setFilter] = useState<StatementFilter>(NO_FILTER);
  /* Derived from the ALL-TIME response and then kept, exactly as on the
     creator's screen: recomputing the choices from a FILTERED response would
     leave each droplist holding only the value already chosen. */
  const [options, setOptions] = useState<StatementOptions>(NO_OPTIONS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Only the period reaches the server. The campaign and the creator are
     matched here, because the statement row carries their NAMES and not their
     ids — lib/statement.ts says why at length. */
  const query = serverQuery(filter);

  useEffect(() => {
    if (!token) return;
    let live = true;
    setLoading(true);
    api<Spend>(`/payments/spend${query}`, { token })
      .then((res) => {
        if (!live) return;
        setData(res);
        setError(null);
        if (query === "") setOptions(optionsFrom(res.payments));
      })
      .catch(() => { if (live) setError(t("spend.loadFailed")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token, query, t]);

  const payments: SpendPayment[] = useMemo(
    () => applyLocalFilter(data?.payments ?? [], filter),
    [data, filter]
  );

  /* The server's own totals whenever it did all the narrowing — they are
     computed over every escrow rather than over the hundred rows the list
     carries. Rebuilt here the moment this page narrows further, so the
     figures never describe a wider question than the table under them. */
  const totals = useMemo<SpendTotals>(() => {
    if (!data) return { spent: {}, pending: {}, disputed: {}, refunded: {} };
    if (filtersLocally(filter)) return spendTotals(payments);
    return { spent: data.spent, pending: data.pending, disputed: data.disputed, refunded: data.refunded };
  }, [data, payments, filter]);

  /* One group per currency, never a sum over them. The union of the four
     maps, because a brand can have money frozen in a market it has never had
     a release in — and a currency that appears in only one of the four still
     deserves its group. */
  const currencies = useMemo(
    () => Array.from(
      new Set([
        ...Object.keys(totals.spent),
        ...Object.keys(totals.pending),
        ...Object.keys(totals.disputed),
        ...Object.keys(totals.refunded)
      ])
    ).sort(),
    [totals]
  );

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const filtering = isFiltered(filter);
  const nothing = !loading && !filtering && currencies.length === 0 && payments.length === 0;

  return (
    <Layout>
      <div className="container page">
        <h1 style={{ margin: 0 }}>{t("spend.title")}</h1>
        <p className="muted" style={{ marginTop: 6 }}>{t("spend.sub")}</p>

        {hasOptions(options) && (
          <StatementFilters
            idPrefix="spend"
            value={filter}
            onChange={setFilter}
            options={options}
            counterpartyLabel={t("spend.creatorLabel")}
            counterpartyAll={t("spend.creatorAll")}
          />
        )}

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {loading ? (
          <p className="muted" style={{ marginTop: 18 }}>{t("discover.loading")}</p>
        ) : nothing ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p style={{ margin: 0 }}>{t("spend.empty")}</p>
            <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0" }}>{t("spend.emptyHint")}</p>
          </div>
        ) : (
          <>
            {/* Said as soon as anything is narrowed, above the numbers it is
                about — the same line, in the same place, as on the creator's
                screen. */}
            {filtering && (
              <p className="muted" style={{ fontSize: 13.5, margin: "16px 0 -2px", fontWeight: 600 }}>
                {t("filt.totals")} <span style={{ fontWeight: 400 }}>— {t("filt.totalsHint")}</span>
              </p>
            )}

            {currencies.map((currency) => (
              <section key={currency} style={{ marginTop: 18 }}>
                {/* The currency names the group rather than sitting inside the
                    numbers, so two markets read as two budgets and never as
                    one running total. */}
                {currencies.length > 1 && (
                  <h2 style={{ fontSize: 16, margin: "0 0 10px" }}>{t("spend.currencyGroup", { currency })}</h2>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
                  <Tile label={t("spend.spent")} hint={t("spend.spentHint")}
                    value={amount(totals.spent[currency] ?? 0, currency, i18n.language)} />
                  <Tile label={t("spend.pending")} hint={t("spend.pendingHint")}
                    value={amount(totals.pending[currency] ?? 0, currency, i18n.language)} />
                  <Tile label={t("spend.disputed")} hint={t("spend.disputedHint")}
                    value={amount(totals.disputed[currency] ?? 0, currency, i18n.language)} />
                  <Tile label={t("spend.refunded")} hint={t("spend.refundedHint")}
                    value={amount(totals.refunded[currency] ?? 0, currency, i18n.language)} />
                </div>
              </section>
            ))}

            {/* Said once and plainly, under the tiles, because that is where
                the question gets asked. The creator's screen carries the
                opposite sentence in the same place. */}
            <p className="muted" style={{ fontSize: 13.5, marginTop: 14 }}>{t("spend.gross")}</p>
            {currencies.length > 1 && (
              <p className="muted" style={{ fontSize: 13.5, marginTop: -6 }}>{t("spend.currencyRule")}</p>
            )}

            <div className="card" style={{ marginTop: 18, overflowX: "auto" }}>
              <h3 style={{ marginTop: 0 }}>{t("spend.statement")}</h3>
              {payments.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{filtering ? t("filt.none") : t("spend.empty")}</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                  <thead>
                    <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("spend.colDate")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("spend.colCampaign")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("spend.colCreator")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>{t("spend.colAmount")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("spend.colStatus")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((row) => (
                      <tr key={row.escrow_id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td style={{ padding: "8px", whiteSpace: "nowrap" }}>
                          {/* The active language, not the browser's: somebody
                              reading the app in French should not get an en-US
                              date beside it. Naive UTC from the API, so it goes
                              through parseApiDate first. */}
                          {row.date
                            ? new Date(parseApiDate(row.date)).toLocaleDateString(i18n.language)
                            : t("spend.noDate")}
                        </td>
                        <td style={{ padding: "8px" }}>
                          <Link to={`/contracts/${row.contract_id}`} style={{ fontWeight: 600 }}>
                            {row.campaign_title || t("spend.untitled")}
                          </Link>
                        </td>
                        {/* The counterparty on a buyer's row is always the
                            creator. Null while they have written no profile:
                            the users table holds nothing but a phone number
                            besides, and a phone number is never handed to the
                            other side of a deal. */}
                        <td style={{ padding: "8px" }}>{row.counterparty_name || t("spend.unknownCreator")}</td>
                        <td style={{ padding: "8px", textAlign: "right", whiteSpace: "nowrap" }}>
                          <span style={{ fontWeight: 700 }}>{amount(row.amount, row.currency, i18n.language)}</span>
                          {/* The refunded half of a dispute split, on the row
                              it belongs to. Without it this line shows 60000
                              spent against a contract the buyer funded with
                              100000, and the 40000 that came back sits in the
                              refunded tile with nothing to trace it to — the
                              statement and the totals would disagree and
                              neither would be findable. Rendered only when it
                              is non-zero, which is almost every row. */}
                          {row.refunded_amount > 0 && (
                            <div className="muted" style={{ fontSize: 12.5, fontWeight: 500 }}>
                              {t("spend.rowRefunded", { amount: amount(row.refunded_amount, row.currency, i18n.language) })}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "8px" }}><StatusChip status={row.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
