import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import type { Earnings, EarningPayment } from "../lib/types";

/* What a creator has made, is waiting on, and cannot touch.

   THE RULE THIS WHOLE SCREEN IS BUILT AROUND: NOTHING IS EVER SUMMED ACROSS
   CURRENCIES. The API returns each total as a map keyed by currency rather
   than as a number, and this page renders one group of tiles per currency
   rather than folding them together. XOF and GHS are not addends — a single
   "total earnings" spanning two markets is not a rounding error, it is a
   number that means nothing, and it would appear on the screen a creator
   trusts most. The same rule holds everywhere else in this codebase: an
   amount and its currency travel together, always.

   THREE FIGURES AND NOT TWO. Pending is money a brand has already paid into
   escrow, released on delivery or on the auto-release timer — a promise with
   a date on it, and something a creator can plan around. Disputed money has
   no such date and may go back to the buyer in whole or in part when an admin
   decides. Folding disputed into pending would put a figure on screen meaning
   "expect this" when the truth is "argue for this", and somebody would commit
   rent to it.

   EVERY FIGURE IS NET. The platform's cut comes off at release, so a gross
   number is one that never reaches a wallet; quoting it would overstate every
   line and turn each payout into a small disappointment. The commission is
   explained once under the tiles and shown per line in the table, so it is
   visible rather than merely subtracted. No rate is hardcoded here —
   commission_for in backend/app/modules/payments/service.py is the single
   definition, and a percentage copied into the client is the copy that
   drifts. */

/* Rendered as the API sends them, with grouping for the active locale and the
   currency code beside — the same way the escrow rows on the contract page
   and the package prices on a profile are shown. */
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

/* The escrow status of the payment, as a chip. The labels are the ones the
   contract page already uses for the same statuses, with the raw value as the
   fallback so a status added server-side renders as itself rather than as a
   missing key. */
function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const tone =
    status === "released"
      ? { color: "var(--teal-600)", background: "#e7f6f0" }
      : status === "disputed"
        ? { color: "var(--danger)", background: "var(--surface-2)" }
        : { color: "var(--muted)", background: "var(--surface-2)" };
  return (
    <span style={{ fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap", ...tone }}>
      {t(`escrow.status_${status}`, status)}
    </span>
  );
}

export default function EarningsPage() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<Earnings | null>(null);
  const [year, setYear] = useState<number | null>(null);
  /* Derived from the ALL-TIME response and then kept. The API takes a `year`
     parameter but publishes no list of years, so the options have to come out
     of the payments themselves — and recomputing them from a FILTERED
     response would leave the dropdown holding only the year already chosen,
     with no way back to the others. */
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let live = true;
    setLoading(true);
    api<Earnings>(year === null ? "/payments/earnings" : `/payments/earnings?year=${year}`, { token })
      .then((res) => {
        if (!live) return;
        setData(res);
        setError(null);
        if (year === null) {
          const found = new Set<number>();
          for (const row of res.payments) {
            // Naive UTC from the API, so it goes through parseApiDate before
            // a year is read off it — a payment settled at 23:40 UTC on 31
            // December is not last year's for a reader in Accra and this
            // year's for one in Douala.
            if (row.date) found.add(new Date(parseApiDate(row.date)).getUTCFullYear());
          }
          setYears(Array.from(found).sort((a, b) => b - a));
        }
      })
      .catch(() => { if (live) setError(t("earn.loadFailed")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token, year, t]);

  /* One group per currency, never a sum over them. The union of the three
     maps, because a creator can have money pending in a market they have not
     been released in yet — and a currency that appears in only one of the
     three still deserves its group. */
  const currencies = useMemo(() => {
    if (!data) return [];
    return Array.from(
      new Set([...Object.keys(data.earned), ...Object.keys(data.pending), ...Object.keys(data.disputed)])
    ).sort();
  }, [data]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const payments: EarningPayment[] = data?.payments ?? [];
  const nothing = !loading && currencies.length === 0 && payments.length === 0;

  return (
    <Layout>
      <div className="container page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: 0 }}>{t("earn.title")}</h1>
            <p className="muted" style={{ marginTop: 6 }}>{t("earn.sub")}</p>
          </div>
          {/* Offered only once there is more than one year to choose between:
             a filter over a single year is a control that can only ever
             reproduce the page it is already on. */}
          {years.length > 1 && (
            <div>
              <label className="label" htmlFor="earn-year">{t("earn.yearLabel")}</label>
              <select id="earn-year" className="select" value={year === null ? "" : String(year)}
                onChange={(e) => setYear(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">{t("earn.yearAll")}</option>
                {years.map((y) => <option key={y} value={String(y)}>{y}</option>)}
              </select>
            </div>
          )}
        </div>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {loading ? (
          <p className="muted" style={{ marginTop: 18 }}>{t("discover.loading")}</p>
        ) : nothing ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p style={{ margin: 0 }}>{t("earn.empty")}</p>
            <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0" }}>{t("earn.emptyHint")}</p>
          </div>
        ) : (
          <>
            {currencies.map((currency) => (
              <section key={currency} style={{ marginTop: 18 }}>
                {/* The currency names the group rather than sitting inside the
                    numbers, so two markets read as two balances and never as
                    one running total. */}
                {currencies.length > 1 && (
                  <h2 style={{ fontSize: 16, margin: "0 0 10px" }}>{t("earn.currencyGroup", { currency })}</h2>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
                  <Tile label={t("earn.earned")} hint={t("earn.earnedHint")}
                    value={amount(data?.earned[currency] ?? 0, currency, i18n.language)} />
                  <Tile label={t("earn.pending")} hint={t("earn.pendingHint")}
                    value={amount(data?.pending[currency] ?? 0, currency, i18n.language)} />
                  <Tile label={t("earn.disputed")} hint={t("earn.disputedHint")}
                    value={amount(data?.disputed[currency] ?? 0, currency, i18n.language)} />
                </div>
              </section>
            ))}

            {/* The commission, said once and plainly. Under the tiles because
                that is where the question is asked: the figures above are net,
                and a fee somebody cannot see is a fee they assume was a
                mistake. */}
            <p className="muted" style={{ fontSize: 13.5, marginTop: 14 }}>{t("earn.commission")}</p>
            {currencies.length > 1 && (
              <p className="muted" style={{ fontSize: 13.5, marginTop: -6 }}>{t("earn.currencyRule")}</p>
            )}

            <div className="card" style={{ marginTop: 18, overflowX: "auto" }}>
              <h3 style={{ marginTop: 0 }}>{t("earn.statement")}</h3>
              {payments.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("earn.empty")}</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                  <thead>
                    <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("earn.colDate")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("earn.colWhat")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600 }}>{t("earn.colStatus")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>{t("earn.colGross")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>{t("earn.colCommission")}</th>
                      <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>{t("earn.colNet")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((row) => (
                      <tr key={row.escrow_id} style={{ borderTop: "1px solid var(--line)" }}>
                        <td style={{ padding: "8px", whiteSpace: "nowrap" }}>
                          {/* The active language, not the browser's: somebody
                              reading the app in French should not get an en-US
                              date beside it. */}
                          {row.date
                            ? new Date(parseApiDate(row.date)).toLocaleDateString(i18n.language)
                            : t("earn.noDate")}
                        </td>
                        <td style={{ padding: "8px" }}>
                          <Link to={`/contracts/${row.contract_id}`} style={{ fontWeight: 600 }}>
                            {row.campaign_title || t("earn.untitled")}
                          </Link>
                          {/* The counterparty is always the buyer, and a
                              buyer's only public identity is its company name.
                              Null while it has written no profile: the users
                              table holds nothing but a phone number besides,
                              and a phone number is never handed to the other
                              side of a deal. */}
                          <div className="muted" style={{ fontSize: 12.5 }}>
                            {row.counterparty_name || t("earn.unknownBrand")}
                          </div>
                        </td>
                        <td style={{ padding: "8px" }}><StatusChip status={row.status} /></td>
                        <td style={{ padding: "8px", textAlign: "right", whiteSpace: "nowrap" }}>{amount(row.gross, row.currency, i18n.language)}</td>
                        <td style={{ padding: "8px", textAlign: "right", whiteSpace: "nowrap" }} className="muted">-{amount(row.commission, row.currency, i18n.language)}</td>
                        <td style={{ padding: "8px", textAlign: "right", whiteSpace: "nowrap", fontWeight: 700 }}>{amount(row.net, row.currency, i18n.language)}</td>
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
