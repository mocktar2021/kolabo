/* One case, end to end: the claim, the thread, and what was decided.

   Readable by the two parties (the server refuses anybody else with a 403).
   The thread is the point of the screen — most disputes are misunderstandings
   and the reply that ends them is written here, which is why the composer
   stays open after the case has queued for an admin as well as during the
   window. */
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, mediaSrc } from "../lib/api";
import { Layout } from "../components/Layout";
import { EvidencePicker } from "../components/EvidencePicker";
import { RespondBy, StatusChip } from "./Disputes";
import { useAuth } from "../lib/auth";
import {
  MAX_STATEMENT_CHARS,
  counterpartyNamesByContract,
  isDisputeOpen
} from "../lib/disputes";
import { parseApiDate } from "../lib/orders";
import type { DisputeCase, UploadedMedia } from "../lib/types";

function Evidence({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
      {urls.map((url) => (
        <a key={url} href={mediaSrc(url)} target="_blank" rel="noreferrer">
          <img src={mediaSrc(url)} alt="" style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 8, display: "block" }} />
        </a>
      ))}
    </div>
  );
}

function When({ iso }: { iso: string }) {
  return (
    <span className="muted" style={{ fontSize: 12 }}>
      {new Date(parseApiDate(iso)).toLocaleString()}
    </span>
  );
}

export default function DisputeDetailPage() {
  const { t } = useTranslation();
  const { token, userId, isAuthenticated } = useAuth();
  const { id } = useParams();
  const [dispute, setDispute] = useState<DisputeCase | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [body, setBody] = useState("");
  const [evidence, setEvidence] = useState<UploadedMedia[]>([]);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setDispute(await api<DisputeCase>(`/payments/disputes/${id}`, { token }));
      try {
        setNames(await counterpartyNamesByContract(token));
      } catch {
        setNames({});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [id, token]);

  useEffect(() => { load(); }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const escrow = dispute?.escrow ?? null;
  const otherName = (escrow && names[escrow.contract_id]) || t("dispute.unknownParty");
  const open = dispute ? isDisputeOpen(dispute) : false;
  /* Only the claimant may drop the claim. The other party answering "you are
     wrong" is a different act, and the server answers them 403 — offering the
     button would be offering a refusal. */
  const isOpener = !!dispute && dispute.opened_by_user_id === userId;
  const author = (authorId: string) => (authorId === userId ? t("dispute.you") : otherName);

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        <Link className="btn btn-ghost" to="/disputes">{t("dispute.back")}</Link>
        {error && <div className="alert alert-error" style={{ marginTop: 12 }}>{error}</div>}
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : !dispute ? (
          <p className="muted">{t("dispute.notFound")}</p>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginTop: 12 }}>
              <h1 style={{ margin: 0, fontSize: 24 }}>{t(`dispute.reason_${dispute.reason}`)}</h1>
              <StatusChip status={dispute.status} />
            </div>
            <p className="muted" style={{ fontSize: 14, marginTop: 6 }}>
              {otherName}
              {escrow && ` · ${escrow.amount} ${escrow.currency}`}
            </p>
            {dispute.status === "awaiting_response" && <RespondBy respondBy={dispute.respond_by} />}

            <div className="card" style={{ marginTop: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <h3 style={{ margin: 0 }}>{t("dispute.opening")}</h3>
                <When iso={dispute.created_at} />
              </div>
              <p className="muted" style={{ fontSize: 13, margin: "4px 0 0" }}>
                {author(dispute.opened_by_user_id)}
              </p>
              <p style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{dispute.statement}</p>
              <Evidence urls={dispute.attachments} />
            </div>

            {/* The decision, in figures. "Your dispute was resolved" with no
                numbers in it is the support ticket it was meant to prevent,
                so both sides of the split are shown even when one is zero. */}
            {dispute.status === "resolved" && escrow && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3 style={{ marginTop: 0 }}>{t("dispute.outcome")}</h3>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
                  <span className="muted">{t("dispute.outcomeReleased")}</span>
                  <span>{`${dispute.released_amount ?? 0} ${escrow.currency}`}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
                  <span className="muted">{t("dispute.outcomeRefunded")}</span>
                  <span>{`${dispute.refunded_amount ?? 0} ${escrow.currency}`}</span>
                </div>
                {dispute.resolution && (
                  <div style={{ marginTop: 10 }}>
                    <p className="muted" style={{ fontSize: 13, margin: 0 }}>{t("dispute.outcomeNote")}</p>
                    <p style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>{dispute.resolution}</p>
                  </div>
                )}
              </div>
            )}

            <div className="card" style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0 }}>{t("dispute.thread")}</h3>
              {dispute.messages.length === 0 ? (
                <p className="muted" style={{ fontSize: 14 }}>{t("dispute.noMessages")}</p>
              ) : (
                dispute.messages.map((m) => (
                  <div key={m.id} style={{ padding: "10px 0", borderTop: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
                      <strong style={{ fontSize: 14 }}>{author(m.author_user_id)}</strong>
                      <When iso={m.created_at} />
                    </div>
                    <p style={{ whiteSpace: "pre-wrap", margin: "4px 0 0" }}>{m.body}</p>
                    <Evidence urls={m.attachments} />
                  </div>
                ))
              )}

              {open && (
                <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                  <textarea
                    className="input"
                    rows={3}
                    value={body}
                    disabled={busy}
                    maxLength={MAX_STATEMENT_CHARS}
                    placeholder={t("dispute.composerPlaceholder")}
                    onChange={(e) => setBody(e.target.value)}
                  />
                  <div style={{ marginTop: 8 }}>
                    <EvidencePicker items={evidence} onChange={setEvidence} disabled={busy} />
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ marginTop: 10 }}
                    disabled={busy || body.trim().length === 0}
                    onClick={() =>
                      act(async () => {
                        await api(`/payments/disputes/${dispute.id}/messages`, {
                          method: "POST",
                          token,
                          body: { body: body.trim(), media_ids: evidence.map((e) => e.id) }
                        });
                        setBody("");
                        setEvidence([]);
                      })
                    }
                  >
                    {t("dispute.send")}
                  </button>
                </div>
              )}
            </div>

            {open && isOpener && (
              <div className="card" style={{ marginTop: 16 }}>
                {/* Inline confirmation rather than a browser confirm(): the
                    thing worth saying is where the money goes, and a native
                    dialog cannot say it. */}
                {!confirmWithdraw ? (
                  <button className="btn btn-ghost" disabled={busy} onClick={() => setConfirmWithdraw(true)}>
                    {t("dispute.withdraw")}
                  </button>
                ) : (
                  <>
                    <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>{t("dispute.withdrawExplain")}</p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            await api(`/payments/disputes/${dispute.id}/withdraw`, { method: "POST", token });
                            setConfirmWithdraw(false);
                          })
                        }
                      >
                        {t("dispute.withdrawYes")}
                      </button>
                      <button className="btn btn-ghost" disabled={busy} onClick={() => setConfirmWithdraw(false)}>
                        {t("dispute.withdrawNo")}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
