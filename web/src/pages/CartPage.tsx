import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { checkoutItem, useCart, type CartCheckoutOrder, type CartCheckoutResult, type CartLine } from "../lib/cart";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { CreatorIdentity } from "../lib/types";

/* A line with the position the server will know it by. The checkout endpoint
   addresses items by their index in the array that was posted, so the index
   has to survive the grouping — otherwise "Item 3" cannot be pointed at once
   the flat basket has been sorted into piles. */
type IndexedLine = CartLine & { index: number };

type CreatorGroup = { creator_user_id: string; creator: CreatorIdentity; lines: IndexedLine[] };

/* Money, per currency, never across them. The platform sets no exchange rate
   and does not want to: an order carries one escrow and an escrow carries one
   currency, so adding 25 000 XOF to 400 GHS would invent a number nobody
   agreed to and that no order could ever be for. Each currency gets its own
   line instead, in both the per-creator subtotal and the grand total. */
function totalsByCurrency(lines: { amount: number; currency: string }[]): [string, number][] {
  const totals = new Map<string, number>();
  for (const l of lines) totals.set(l.currency, (totals.get(l.currency) ?? 0) + l.amount);
  return [...totals.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

/* One pile per creator, in the order the basket was built. This grouping is
   not decoration: it is exactly what the endpoint does with the items. A
   checkout FANS OUT into one direct order per creator — each one accepted or
   declined on its own, on its own clock, for its own money — so buying three
   packages from one person is one order with three deliverables, while two
   people are two independent orders. Showing the basket any other way would
   promise a shape the receipt then contradicts. */
function groupByCreator(lines: CartLine[]): CreatorGroup[] {
  const groups: CreatorGroup[] = [];
  lines.forEach((line, index) => {
    const found = groups.find((g) => g.creator_user_id === line.creator_user_id);
    if (found) found.lines.push({ ...line, index });
    else groups.push({ creator_user_id: line.creator_user_id, creator: line.creator, lines: [{ ...line, index }] });
  });
  return groups;
}

export default function CartPage() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { lines, remove, clear } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* Which line the server refused, zero-based. Null when the failure was not
     about a particular item (a role check, a network error). */
  const [rejected, setRejected] = useState<number | null>(null);
  const [orders, setOrders] = useState<CartCheckoutOrder[] | null>(null);

  const locale = i18n.language.startsWith("en") ? "en-US" : "fr-FR";
  const money = (n: number, currency: string) => `${n.toLocaleString(locale)} ${currency}`;
  const platformLabel = (id: string | null) => (id ? PLATFORM_LABELS[id] ?? id : "");

  async function checkout() {
    setBusy(true);
    setError(null);
    setRejected(null);
    try {
      const res = await api<CartCheckoutResult>("/campaigns/orders/checkout", {
        method: "POST",
        token,
        body: { items: lines.map(checkoutItem) }
      });
      setOrders(res.orders);
      // The basket became orders. Keeping it would invite the buyer to check
      // out the same six packages twice.
      clear();
    } catch (e) {
      /* Every item is validated before a single row is written and the writes
         are one transaction, so a rejected line means NOTHING was ordered —
         not "the first two went through". That is said out loud next to the
         error, because a buyer who assumes otherwise re-orders the first two.

         The position is parsed off the message and is ZERO-BASED: cart.py
         enumerates the items from zero. It is used only to highlight the row;
         the server's own sentence is what explains the problem, and it is
         shown verbatim because it names the rule and what is allowed in the
         same words the packages module uses. */
      if (e instanceof ApiError && e.status === 400) {
        const match = /^Item (\d+):/.exec(e.message);
        if (match) setRejected(Number(match[1]));
      }
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const groups = groupByCreator(lines);
  const grandTotals = totalsByCurrency(lines);

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        <h1 style={{ margin: 0 }}>{t("cart.title")}</h1>

        {orders ? (
          /* The receipt. One row per creator, not per basket line, because
             that is what was created: the buyer sent a flat list and got back
             a shorter list of orders, and creator_user_id on each row is what
             tells them apart. Each links to its campaign, which is where a
             direct order lives until the creator answers — there is no
             contract to link to yet. */
          <div className="card" style={{ marginTop: 18 }}>
            <div className="alert alert-success">{t("cart.successTitle")}</div>
            <p className="muted" style={{ fontSize: 13.5, marginTop: 0 }}>{t("cart.successRule")}</p>
            <div style={{ display: "grid", gap: 10 }}>
              {orders.map((o) => (
                <div key={o.campaign_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
                  <CreatorChip creator={lines.find((l) => l.creator_user_id === o.creator_user_id)?.creator ?? {
                    display_name: null, avatar_url: null, top_platform: null, top_follower_count: null
                  }} />
                  <Link to={`/campaigns/${o.campaign_id}`} style={{ fontWeight: 600 }}>{t("cart.viewOrder")}</Link>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14 }}>
              <Link className="btn btn-ghost" to="/discover">{t("cart.emptyCta")}</Link>
            </div>
          </div>
        ) : lines.length === 0 ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p className="muted" style={{ margin: "0 0 12px" }}>{t("cart.empty")}</p>
            <Link className="btn btn-primary" to="/discover">{t("cart.emptyCta")}</Link>
          </div>
        ) : (
          <>
            {error && (
              <div className="alert alert-error" style={{ marginTop: 16 }}>
                <div>{error}</div>
                <div style={{ marginTop: 6, fontWeight: 600 }}>{t("cart.allOrNothing")}</div>
              </div>
            )}

            {groups.map((group) => {
              const subtotals = totalsByCurrency(group.lines);
              return (
                <div key={group.creator_user_id} className="card" style={{ marginTop: 16 }}>
                  <CreatorChip creator={group.creator} />

                  <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                    {group.lines.map((line) => {
                      const isRejected = rejected === line.index;
                      return (
                        <div
                          key={line.id}
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12,
                            borderTop: "1px solid var(--line)", paddingTop: 10,
                            borderLeft: isRejected ? "3px solid var(--danger, #c0392b)" : undefined,
                            paddingLeft: isRejected ? 10 : undefined
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>{line.label}</strong>
                            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                              {line.package_id ? "" : `${t("cart.custom")} · `}
                              {platformLabel(line.platform)}
                              {line.deliverable_type ? ` · ${t(`deliverable.${line.deliverable_type}`, line.deliverable_type)}` : ""}
                              {line.quantity && line.quantity > 1 ? ` · ${t("cart.qty", { n: line.quantity })}` : ""}
                              {line.timeline_days ? ` · ${t("cart.days", { n: line.timeline_days })}` : ""}
                            </div>
                            {line.note && (
                              <p className="muted" style={{ fontSize: 13, margin: "6px 0 0", whiteSpace: "pre-wrap" }}>
                                {t("cart.note")} : {line.note}
                              </p>
                            )}
                            {/* The server's sentence sits on the line it is
                                about, not only at the top of the page: a
                                twenty-line basket with one message above it
                                leaves the buyer counting rows. */}
                            {isRejected && error && (
                              <p style={{ fontSize: 13, margin: "6px 0 0", color: "var(--danger, #c0392b)", fontWeight: 600 }}>
                                {t("cart.lineRejected")} — {error}
                              </p>
                            )}
                          </div>
                          <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15 }}>
                              {money(line.amount, line.currency)}
                            </div>
                            <button type="button" className="pp-see-more" style={{ marginTop: 4 }}
                              disabled={busy} onClick={() => remove(line.id)}>
                              {t("cart.remove")}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ borderTop: "1px solid var(--line)", marginTop: 10, paddingTop: 10 }}>
                    {subtotals.map(([currency, amount]) => (
                      <div key={currency} style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                        <span className="muted">{t("cart.subtotal")}</span>
                        <strong>{money(amount, currency)}</strong>
                      </div>
                    ))}
                    {/* One creator, two currencies is refused server-side: an
                        order carries one escrow and an escrow carries one
                        currency. Said here rather than discovered as a 400
                        after the checkout button. */}
                    {subtotals.length > 1 && (
                      <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("cart.mixedCurrency")}</p>
                    )}
                  </div>
                </div>
              );
            })}

            <div className="card" style={{ marginTop: 16 }}>
              {grandTotals.map(([currency, amount]) => (
                <div key={currency} style={{ display: "flex", justifyContent: "space-between", fontSize: 16, marginBottom: 4 }}>
                  <strong>{t("cart.total")}</strong>
                  <strong style={{ fontFamily: "var(--font-display)" }}>{money(amount, currency)}</strong>
                </div>
              ))}
              {grandTotals.length > 1 && (
                <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>{t("cart.totalsNote")}</p>
              )}
              <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>{t("cart.rule")}</p>
              <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} disabled={busy} onClick={checkout}>
                {busy ? t("auth.working") : t("cart.checkout")}
              </button>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
