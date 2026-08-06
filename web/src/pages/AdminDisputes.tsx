/* The dispute queue an admin works from, and the form that ends a case.

   ADMIN IDENTITY IS AN ORDINARY LOGIN. An admin signs in the same way every
   other user does, and this page sends the same bearer token every other
   screen sends. The API refuses a token whose account is not an admin — 403,
   surfaced by the error path below — and who is an admin is settled by
   deployment configuration, not by anything typed into this page. See
   backend/app/modules/auth/admins.py.

   The placeholder header this screen used to send in place of a token is
   gone, along with the field that collected it, the browser-storage key it
   was kept in, and the matching option on the api helper. */
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, mediaSrc } from "../lib/api";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { StatusChip } from "./Disputes";
import { COMMISSION_BPS, commissionFor } from "../lib/pricing";
import { parseApiDate } from "../lib/orders";
import type { DisputeCase, DisputeReason, DisputeStatus } from "../lib/types";

/* One row of GET /admin/disputes. Kept local to this page rather than in
   lib/types.ts: the dispute shapes there are read by four screens, this one
   by exactly this file, and it is a triage projection rather than a resource
   — it exists to be sorted and scanned, and it dies with the screen. */
type DisputeQueueRow = {
  id: string;
  escrow_id: string;
  status: DisputeStatus;
  reason: DisputeReason;
  amount: number;
  currency: string;
  opened_by_user_id: string;
  business_user_id: string;
  business_name: string | null;
  creator_user_id: string;
  creator_name: string | null;
  message_count: number;
  respond_by: string;
  created_at: string;
};

function Evidence({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
      {urls.map((url) => (
        <a key={url} href={mediaSrc(url)} target="_blank" rel="noreferrer">
          <img src={mediaSrc(url)} alt="" style={{ width: 88, height: 88, objectFit: "cover", borderRadius: 8, display: "block" }} />
        </a>
      ))}
    </div>
  );
}

export default function AdminDisputesPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rows, setRows] = useState<DisputeQueueRow[]>([]);
  const [openCase, setOpenCase] = useState<DisputeCase | null>(null);
  const [released, setReleased] = useState("");
  const [refunded, setRefunded] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await api<DisputeQueueRow[]>("/admin/disputes", { token }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function openRow(row: DisputeQueueRow) {
    setError(null);
    setBusy(true);
    try {
      // The same endpoint the two parties read, which already accepts an
      // admin credential: one case view, so an admin decides on exactly what
      // the parties can see they said.
      setOpenCase(await api<DisputeCase>(`/payments/disputes/${row.id}`, { token }));
      setReleased("");
      setRefunded("");
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  function age(createdAt: string): string {
    const hours = Math.floor((Date.now() - parseApiDate(createdAt)) / 3600000);
    return hours >= 24
      ? t("admin.ageDays", { n: Math.floor(hours / 24) })
      : t("admin.ageHours", { n: Math.max(hours, 0) });
  }

  const escrow = openCase?.escrow ?? null;
  const releasedNum = Number(released || 0);
  const refundedNum = Number(refunded || 0);
  const valid =
    Number.isFinite(releasedNum) && Number.isFinite(refundedNum) &&
    releasedNum >= 0 && refundedNum >= 0;
  /* What is still unallocated. The server refuses a split that does not add
     up to the escrow exactly — anything less invents a remainder nobody owns,
     anything more pays out money that was never collected — so the form shows
     the gap rather than letting an admin find it as a 400. */
  const remainder = escrow && valid ? escrow.amount - releasedNum - refundedNum : null;
  const balanced = remainder === 0;
  const commission = valid ? commissionFor(releasedNum) : 0;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 860 }}>
        <h1 style={{ marginBottom: 4 }}>{t("admin.disputesTitle")}</h1>
        <p className="muted" style={{ marginTop: 0 }}>{t("admin.disputesSub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 12 }}>{error}</div>}

        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : rows.length === 0 ? (
          <p className="muted">{t("admin.empty")}</p>
        ) : (
          /* Rendered in the order the server sent it. awaiting_admin first,
             oldest first within each group — frozen money is somebody not
             being paid, and the fair order for that is arrival order. Sorting
             here would silently undo the one thing the queue endpoint does. */
          rows.map((row) => (
            <div key={row.id} className="card" style={{ marginTop: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                <strong>{t(`dispute.reason_${row.reason}`)}</strong>
                <StatusChip status={row.status} />
              </div>
              <div className="muted" style={{ fontSize: 14, marginTop: 6 }}>
                {`${t("admin.brand")}: ${row.business_name || t("admin.unnamed")}`}
                {` · ${t("admin.creator")}: ${row.creator_name || t("admin.unnamed")}`}
              </div>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                {`${row.amount} ${row.currency}`}
                {` · ${t("admin.messages", { n: row.message_count })}`}
                {` · ${t("admin.openedAgo", { age: age(row.created_at) })}`}
              </div>
              <button
                className="btn btn-ghost"
                style={{ marginTop: 10 }}
                disabled={busy}
                onClick={() => (openCase?.id === row.id ? setOpenCase(null) : openRow(row))}
              >
                {openCase?.id === row.id ? t("admin.closeCase") : t("admin.openCase")}
              </button>

              {openCase?.id === row.id && (
                <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                  <h4 style={{ margin: "0 0 4px" }}>{t("dispute.opening")}</h4>
                  <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{openCase.statement}</p>
                  <Evidence urls={openCase.attachments} />

                  <h4 style={{ margin: "14px 0 0" }}>{t("dispute.thread")}</h4>
                  {openCase.messages.length === 0 ? (
                    <p className="muted" style={{ fontSize: 14 }}>{t("dispute.noMessages")}</p>
                  ) : (
                    openCase.messages.map((m) => (
                      <div key={m.id} style={{ padding: "10px 0", borderTop: "1px solid var(--line)" }}>
                        <div className="muted" style={{ fontSize: 13 }}>
                          {(m.author_user_id === row.business_user_id
                            ? row.business_name || t("admin.brand")
                            : row.creator_name || t("admin.creator")) +
                            " · " +
                            new Date(parseApiDate(m.created_at)).toLocaleString()}
                        </div>
                        <p style={{ whiteSpace: "pre-wrap", margin: "4px 0 0" }}>{m.body}</p>
                        <Evidence urls={m.attachments} />
                      </div>
                    ))
                  )}

                  {escrow && (
                    <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                      <h4 style={{ margin: "0 0 10px" }}>{t("admin.resolveTitle")}</h4>

                      {/* Shortcuts, not separate outcomes: full release and
                          full refund are the two ends of the same line, and
                          filling the split keeps every decision one shape. */}
                      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                        <button
                          className="btn btn-ghost"
                          disabled={busy}
                          onClick={() => { setReleased(String(escrow.amount)); setRefunded("0"); }}
                        >
                          {t("admin.fullRelease")}
                        </button>
                        <button
                          className="btn btn-ghost"
                          disabled={busy}
                          onClick={() => { setReleased("0"); setRefunded(String(escrow.amount)); }}
                        >
                          {t("admin.fullRefund")}
                        </button>
                      </div>

                      <div style={{ display: "flex", gap: 8 }}>
                        <div style={{ flex: 1 }}>
                          <label className="label" htmlFor={`released-${row.id}`}>{t("admin.released")}</label>
                          <input
                            id={`released-${row.id}`}
                            className="input"
                            type="number"
                            min={0}
                            value={released}
                            disabled={busy}
                            onChange={(e) => setReleased(e.target.value)}
                          />
                        </div>
                        <div style={{ flex: 1 }}>
                          <label className="label" htmlFor={`refunded-${row.id}`}>{t("admin.refunded")}</label>
                          <input
                            id={`refunded-${row.id}`}
                            className="input"
                            type="number"
                            min={0}
                            value={refunded}
                            disabled={busy}
                            onChange={(e) => setRefunded(e.target.value)}
                          />
                        </div>
                      </div>

                      <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>
                        {balanced
                          ? t("admin.balanced")
                          : t("admin.remainder", { n: remainder ?? escrow.amount, currency: escrow.currency })}
                      </p>

                      {/* What the creator actually nets. The fee is charged on
                          the released part only, so moving the split moves it
                          too — an admin should not have to derive that. */}
                      <p className="muted" style={{ fontSize: 13, margin: "4px 0 0" }}>
                        {t("admin.commission", { pct: COMMISSION_BPS / 100, n: commission, currency: escrow.currency })}
                        {` · ${t("admin.netToCreator", { n: Math.max(releasedNum - commission, 0), currency: escrow.currency })}`}
                      </p>
                      <p className="muted" style={{ fontSize: 13, margin: "4px 0 10px" }}>{t("admin.commissionHint")}</p>

                      <label className="label" htmlFor={`note-${row.id}`}>{t("admin.note")}</label>
                      <textarea
                        id={`note-${row.id}`}
                        className="input"
                        rows={3}
                        value={note}
                        disabled={busy}
                        placeholder={t("admin.notePlaceholder")}
                        onChange={(e) => setNote(e.target.value)}
                      />

                      <button
                        className="btn btn-primary"
                        style={{ marginTop: 10 }}
                        disabled={busy || !balanced || note.trim().length === 0}
                        onClick={async () => {
                          setBusy(true);
                          setError(null);
                          try {
                            await api(`/payments/escrow/${openCase.escrow_id}/resolve`, {
                              method: "POST",
                              token,
                              body: {
                                released_amount: releasedNum,
                                refunded_amount: refundedNum,
                                note: note.trim()
                              }
                            });
                            setOpenCase(null);
                            await load();
                          } catch (e) {
                            setError(e instanceof Error ? e.message : "Error");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        {t("admin.submit")}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Layout>
  );
}
