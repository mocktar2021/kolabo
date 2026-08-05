import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { checkoutItem, useCart, UNKNOWN_CREATOR, type CartCheckoutOrder, type CartCheckoutResult, type CartLine } from "../lib/cart";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { CreatorIdentity } from "../lib/types";

type CreatorGroup = { creator_user_id: string; creator: CreatorIdentity; lines: CartLine[] };

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
   promise a shape the receipt then contradicts.

   IT IS ALSO WHY THE CHECKBOX IS PER GROUP AND NOT PER LINE. The unit the
   server creates is the creator's order; ticking two of somebody's three
   packages would look like a choice the buyer had made and would arrive as
   one order for two — the same order, quietly different. A creator who wants
   only two removes the third. */
function groupByCreator(lines: CartLine[]): CreatorGroup[] {
  const groups: CreatorGroup[] = [];
  for (const line of lines) {
    const found = groups.find((g) => g.creator_user_id === line.creator_user_id);
    if (found) found.lines.push(line);
    else groups.push({ creator_user_id: line.creator_user_id, creator: line.creator, lines: [line] });
  }
  return groups;
}

export default function CartPage() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { lines, remove } = useCart();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* Which line the server refused, by ID rather than by position.

     It used to be the index, and the index used to be right: the basket was
     posted whole, so the server's zero-based cart_index 3 was the fourth row
     on screen. With a selection it is the fourth row OF WHAT WAS POSTED,
     which is a different row as soon as anything is unticked — and
     highlighting the wrong line is worse than highlighting none, because the
     buyer then edits an item the server never complained about. The posted
     list is kept below and the index is resolved through it once, here. */
  const [rejectedId, setRejectedId] = useState<string | null>(null);
  const [orders, setOrders] = useState<CartCheckoutOrder[] | null>(null);
  /* The lines that became those orders. Kept because they are removed from
     the basket on success and the receipt still has to name who each order is
     for. */
  const [orderedLines, setOrderedLines] = useState<CartLine[]>([]);

  /* WHAT IS **NOT** SELECTED, rather than what is.

     Default-all-selected is the requirement, and storing the negative is what
     makes it true without any syncing: a group added after this state was
     created is selected because it is not in the set, so adding a package on
     another profile and coming back does not silently leave it out of the
     order. A positive set would have to be topped up every time the basket
     changed, and the day somebody forgot, the bug would be a paid order
     missing a line. */
  const [deselected, setDeselected] = useState<Set<string>>(new Set());

  const locale = i18n.language.startsWith("en") ? "en-US" : "fr-FR";
  const money = (n: number, currency: string) => `${n.toLocaleString(locale)} ${currency}`;
  const platformLabel = (id: string | null) => (id ? PLATFORM_LABELS[id] ?? id : "");

  /* The creator as CreatorChip should render them here.

     THE FALLBACK IS NOT THE CHIP'S OWN. CreatorChip answers a null name with
     "Créateur sans nom", which is right everywhere it is used — a favourite,
     an invitation, a proposal all come from the server, so a missing name
     really does mean the creator has not written one, and the brand should
     notice. A basket line is the one place that is not true: a line added
     before the identity snapshot existed carries no name because NOBODY EVER
     ASKED, and telling a buyer this person is nameless would be asserting
     something we never checked. So an un-snapshotted line gets a neutral
     label, and a creator who genuinely has no display name gets the same one,
     which is the honest floor for both. */
  const chipFor = (creator: CreatorIdentity): CreatorIdentity => ({
    ...creator,
    display_name: creator.display_name || t("cart.unknownCreator")
  });

  function toggleGroup(creatorUserId: string) {
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(creatorUserId)) next.delete(creatorUserId);
      else next.add(creatorUserId);
      return next;
    });
  }

  const groups = groupByCreator(lines);
  const selectedGroups = groups.filter((g) => !deselected.has(g.creator_user_id));
  const selectedLines = selectedGroups.flatMap((g) => g.lines);
  const selectedTotals = totalsByCurrency(selectedLines);

  async function checkout() {
    /* Frozen before the request. selectedLines is derived from state that a
       click could change while the round trip is in flight, and the index the
       server sends back has to be resolved against exactly what was sent —
       not against whatever the page is showing when the answer arrives. */
    const posted = selectedLines;
    if (posted.length === 0) return;
    setBusy(true);
    setError(null);
    setRejectedId(null);
    try {
      const res = await api<CartCheckoutResult>("/campaigns/orders/checkout", {
        method: "POST",
        token,
        body: { items: posted.map(checkoutItem) }
      });
      setOrders(res.orders);
      setOrderedLines(posted);
      /* Only what was ordered leaves the basket. clear() was right while the
         whole cart was always posted; with a selection it would throw away
         the groups the buyer deliberately held back, which is the one thing
         holding them back was for. */
      posted.forEach((line) => remove(line.id));
    } catch (e) {
      /* Every item is validated before a single row is written and the writes
         are one transaction, so a rejected line means NOTHING was ordered —
         not "the first two went through". That is said out loud next to the
         error, because a buyer who assumes otherwise re-orders the first two.

         THE ALL-OR-NOTHING IS PER REQUEST, which is exactly why the selection
         is a selection and not a partial order: the server has no way to
         create some of a basket, so choosing less means SENDING less. What
         goes up is still ordered whole.

         THE POSITION ARRIVES AS DATA, in `values.cart_index`, and is
         ZERO-BASED: cart.py enumerates the items from zero. It used to be
         read back out of the English sentence with a regular expression,
         which meant rewording that sentence would have silently stopped the
         highlight working with nothing failing anywhere.

         The status is not tested, because it has nothing to add: an index is
         either on the refusal or it is not, and cart.py puts one on every
         refusal it re-raises. What IS tested is that the value is a real
         integer — `Number(null)` is 0, which would confidently highlight the
         first row of a basket the server never said anything about.

         The refusal keeps the resolver's own code, so the sentence beside the
         row is the specific one ("you cannot order your own package"), in the
         reader's language, via errorText. */
      if (e instanceof ApiError) {
        const raw = e.values?.cart_index;
        const index = raw == null ? NaN : Number(raw);
        if (Number.isInteger(index)) setRejectedId(posted[index]?.id ?? null);
      }
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

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
            {/* Anything held back is still in the basket and is still
                orderable. Said here because the success banner otherwise
                reads as "the cart is done". */}
            {lines.length > 0 && (
              <p className="muted" style={{ fontSize: 13.5, marginTop: 0 }}>{t("cart.remaining", { n: lines.length })}</p>
            )}
            <div style={{ display: "grid", gap: 10 }}>
              {orders.map((o) => (
                <div key={o.campaign_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
                  {/* Looked up in the lines that were ordered, which is why
                      they were kept — and falling back to the empty identity
                      rather than assuming one is there, the same defence
                      readStored applies to a line written by an older
                      build. */}
                  <CreatorChip creator={chipFor(orderedLines.find((l) => l.creator_user_id === o.creator_user_id)?.creator ?? UNKNOWN_CREATOR)} />
                  <Link to={`/campaigns/${o.campaign_id}`} style={{ fontWeight: 600 }}>{t("cart.viewOrder")}</Link>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14 }}>
              {lines.length > 0 ? (
                <button type="button" className="btn btn-primary" onClick={() => { setOrders(null); setOrderedLines([]); }}>
                  {t("cart.backToCart")}
                </button>
              ) : (
                <Link className="btn btn-ghost" to="/discover">{t("cart.emptyCta")}</Link>
              )}
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

            {/* Only offered once there is more than one pile to choose
                between. "Tout sélectionner" over a single group is a control
                that can only ever undo itself. */}
            {groups.length > 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
                <span className="muted" style={{ fontSize: 13.5 }}>
                  {t("cart.selectedCount", { n: selectedGroups.length, total: groups.length })}
                </span>
                <button type="button" className="pp-see-more" onClick={() => setDeselected(new Set())}>
                  {t("cart.selectAll")}
                </button>
                <button type="button" className="pp-see-more"
                  onClick={() => setDeselected(new Set(groups.map((g) => g.creator_user_id)))}>
                  {t("cart.selectNone")}
                </button>
              </div>
            )}

            {groups.map((group) => {
              const subtotals = totalsByCurrency(group.lines);
              const selected = !deselected.has(group.creator_user_id);
              return (
                <div key={group.creator_user_id} className="card"
                  style={{ marginTop: 16, opacity: selected ? 1 : 0.55 }}>
                  {/* The checkbox and the chip in one label, so the whole
                      header is the hit target rather than a 13 px box. */}
                  <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={busy}
                      onChange={() => toggleGroup(group.creator_user_id)}
                      aria-label={t("cart.selectGroup", { name: group.creator.display_name || t("cart.unknownCreator") })}
                    />
                    <CreatorChip creator={chipFor(group.creator)} />
                  </label>

                  <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
                    {group.lines.map((line) => {
                      const isRejected = rejectedId === line.id;
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
                            {/* The refusal sits on the line it is about, not
                                only at the top of the page: a twenty-line
                                basket with one message above it leaves the
                                buyer counting rows. Same sentence in both
                                places — errorText resolved it once, from the
                                code the resolver refused with. */}
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
                    {/* Only on the piles that are being left behind, so the
                        basket does not repeat itself on every card. */}
                    {!selected && (
                      <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("cart.groupExcluded")}</p>
                    )}
                  </div>
                </div>
              );
            })}

            <div className="card" style={{ marginTop: 16 }}>
              {selectedTotals.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("cart.noneSelected")}</p>
              ) : (
                selectedTotals.map(([currency, amount]) => (
                  <div key={currency} style={{ display: "flex", justifyContent: "space-between", fontSize: 16, marginBottom: 4 }}>
                    {/* The label says the total is of the SELECTION as soon as
                        anything is unticked. A figure called "Total" that
                        silently ignores a group is the way somebody adds the
                        cards up, gets a different number, and concludes our
                        arithmetic is wrong. */}
                    <strong>{selectedGroups.length === groups.length ? t("cart.total") : t("cart.totalSelected")}</strong>
                    <strong style={{ fontFamily: "var(--font-display)" }}>{money(amount, currency)}</strong>
                  </div>
                ))
              )}
              {selectedTotals.length > 1 && (
                <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>{t("cart.totalsNote")}</p>
              )}
              <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>{t("cart.rule")}</p>
              {/* THE DISTINCTION THIS WHOLE FEATURE RESTS ON, said once, where
                  the decision is made: the server cannot create part of a
                  basket — it validates every item and writes them in one
                  transaction — so a partial cart is a partial SELECTION and
                  never a partial order. What goes up goes up whole. */}
              {groups.length > 1 && (
                <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>{t("cart.selectionNote")}</p>
              )}
              <button className="btn btn-primary btn-block" style={{ marginTop: 12 }}
                disabled={busy || selectedGroups.length === 0} onClick={checkout}>
                {busy
                  ? t("auth.working")
                  : selectedGroups.length === groups.length
                    ? t("cart.checkout")
                    : t("cart.checkoutSelected", { n: selectedGroups.length })}
              </button>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
