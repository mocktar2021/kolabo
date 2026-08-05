import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, mediaSrc } from "../lib/api";
import { EvidencePicker } from "./EvidencePicker";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import {
  REVIEW_WINDOW_DAYS,
  draftFrom,
  openSubmission,
  type DeliverableSubmission
} from "../lib/deliverables";
import type { UploadedMedia } from "../lib/types";

/* The work, on the contract it was agreed in.

   WHY IT LIVES HERE AND NOT ON A SCREEN OF ITS OWN. Approving a submission
   releases the escrow, and the two facts a brand needs in order to decide —
   the terms they agreed and the money they are about to move — are already on
   this page. A separate deliverables screen would put the decision one
   navigation away from its own context, and the decision is irreversible.

   THE TWO ANSWERS ARE DELIBERATELY NOT SYMMETRICAL. Approve is one click
   because it is the happy path and the brand has already read the work.
   Request changes opens a form, because it REQUIRES a reason: "rejected" with
   no note is a round trip that teaches the creator nothing and comes back the
   same. That asymmetry is the product rule, not a layout accident. */
function StatusChip({ status }: { status: DeliverableSubmission["status"] }) {
  const { t } = useTranslation();
  const tone =
    status === "approved"
      ? "var(--teal-600)"
      : status === "changes_requested"
        ? "var(--danger)"
        : "var(--muted)";
  return (
    <span
      style={{
        fontSize: 12, fontWeight: 600, color: tone, background: "var(--surface-2)",
        padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap"
      }}
    >
      {t(`deliv.status_${status}`)}
    </span>
  );
}

function SubmissionRow({ row }: { row: DeliverableSubmission }) {
  const { t } = useTranslation();
  return (
    <div style={{ borderTop: "1px solid var(--line)", padding: "12px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <StatusChip status={row.status} />
        {/* parseApiDate, not new Date: these are naive UTC strings like
            "2026-08-05T09:12:00" with no suffix, and left alone the browser
            reads them as local time and invents or destroys hours. */}
        <span className="muted" style={{ fontSize: 12 }}>
          {new Date(parseApiDate(row.created_at)).toLocaleDateString()}
        </span>
      </div>
      {row.link_url && (
        <p style={{ margin: "8px 0 0", fontSize: 14 }}>
          {/* rel="noreferrer" because this is a link somebody else supplied. */}
          <a href={row.link_url} target="_blank" rel="noreferrer">{t("deliv.viewPost")}</a>
        </p>
      )}
      {row.note && <p style={{ margin: "6px 0 0", fontSize: 14, whiteSpace: "pre-wrap" }}>{row.note}</p>}
      {/* Through mediaSrc: the API returns a bare "/profiles/media/{id}" path,
          and the API origin is not the web origin — used raw these would
          resolve against the web app and 404. */}
      {row.attachments.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {row.attachments.map((url) => (
            <a key={url} href={mediaSrc(url)} target="_blank" rel="noreferrer">
              <img
                src={mediaSrc(url)}
                alt={t("deliv.attachments")}
                style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 8, border: "1px solid var(--line)" }}
              />
            </a>
          ))}
        </div>
      )}
      {/* The brand's reason, kept ON the attempt it closed rather than only in
          a notification the creator may have cleared. */}
      {row.review_note && (
        <p className="muted" style={{ margin: "8px 0 0", fontSize: 13.5 }}>
          <strong>{t("deliv.reviewNoteShown")}</strong> {row.review_note}
        </p>
      )}
    </div>
  );
}

export function DeliverablesPanel({
  contractId,
  isBusiness,
  hasEscrow,
  escrowHeld,
  onChanged
}: {
  contractId: string;
  isBusiness: boolean;
  hasEscrow: boolean;
  escrowHeld: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rows, setRows] = useState<DeliverableSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [link, setLink] = useState("");
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<UploadedMedia[]>([]);
  const [asking, setAsking] = useState(false);
  const [reviewNote, setReviewNote] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(
        await api<DeliverableSubmission[]>(`/deliverables?contract_id=${contractId}`, { token })
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [contractId, token]);

  useEffect(() => { load(); }, [load]);

  /* Every write goes through here so a refusal lands in THIS panel's own error
     line rather than the page-level banner at the top of a long contract page,
     which is the bug the dispute form had to be rewritten to avoid. */
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  const open = openSubmission(rows);
  const canSubmit = !isBusiness && escrowHeld && !open;
  const canReview = isBusiness && escrowHeld && !!open;
  // The button is disabled until the submission would be accepted, so the
  // server's "a submission needs a link or a file" is a rule the form states
  // rather than a 400 the creator discovers.
  const nothingToSend = !link.trim() && files.length === 0;

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("deliv.title")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("deliv.sub")}</p>

      {error && <div className="alert alert-error">{error}</div>}

      {!hasEscrow ? (
        <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("deliv.notFunded")}</p>
      ) : loading ? (
        <p className="muted" style={{ margin: 0 }}>{t("discover.loading")}</p>
      ) : (
        <>
          {rows.length === 0 && (
            <div style={{ marginBottom: 4 }}>
              <p style={{ fontSize: 14, margin: 0 }}>
                {isBusiness ? t("deliv.emptyBrand") : t("deliv.emptyCreator")}
              </p>
              {isBusiness && (
                <p className="muted" style={{ fontSize: 13.5, margin: "6px 0 0" }}>{t("deliv.emptyBrandHint")}</p>
              )}
            </div>
          )}

          {/* The brand's answer, offered only on an attempt that is actually
              waiting for one. */}
          {canReview && open && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
              <h4 style={{ margin: "0 0 6px" }}>{t("deliv.reviewTitle")}</h4>
              <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>{t("deliv.awaitingReview")}</p>
              {!asking ? (
                <>
                  {/* Said before the click, not after it: this releases the
                      money and there is no way back. */}
                  <p className="muted" style={{ fontSize: 13.5 }}>{t("deliv.approveWarning")}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn btn-teal" disabled={busy}
                      onClick={() => act(() => api(`/deliverables/${open.id}/approve`, { method: "POST", token }))}>
                      {t("deliv.approve")}
                    </button>
                    <button className="btn btn-ghost" disabled={busy}
                      onClick={() => { setAsking(true); setReviewNote(""); }}>
                      {t("deliv.requestChanges")}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <label className="label" htmlFor="deliv-review-note">{t("deliv.reviewNoteLabel")}</label>
                  <textarea
                    id="deliv-review-note"
                    className="input"
                    rows={3}
                    value={reviewNote}
                    disabled={busy}
                    placeholder={t("deliv.reviewNotePlaceholder")}
                    onChange={(e) => setReviewNote(e.target.value)}
                  />
                  {/* Distinguishes this from a dispute, which is the thing a
                      brand reaches for when it does not know these are
                      different acts. */}
                  <p className="muted" style={{ fontSize: 13, margin: "6px 0 10px" }}>{t("deliv.changesKeepEscrow")}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn btn-primary" disabled={busy || !reviewNote.trim()}
                      onClick={() => act(async () => {
                        await api(`/deliverables/${open.id}/request-changes`, {
                          method: "POST", token, body: { note: reviewNote.trim() }
                        });
                        setAsking(false);
                        setReviewNote("");
                      })}>
                      {t("deliv.sendRequest")}
                    </button>
                    <button className="btn btn-ghost" disabled={busy} onClick={() => setAsking(false)}>
                      {t("deliv.cancel")}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* The creator's side of the same moment: either it is with the
              brand, or there is a form. */}
          {!isBusiness && open && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
              <div className="alert alert-info" style={{ marginBottom: 8 }}>{t("deliv.awaitingReviewCreator")}</div>
              <p className="muted" style={{ fontSize: 13, margin: "0 0 8px" }}>{t("deliv.withdrawHint")}</p>
              <button className="btn btn-ghost" disabled={busy}
                onClick={() => act(() => api(`/deliverables/${open.id}/withdraw`, { method: "POST", token }))}>
                {t("deliv.withdraw")}
              </button>
            </div>
          )}

          {canSubmit && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
              <h4 style={{ margin: "0 0 8px" }}>{t("deliv.submitTitle")}</h4>

              <label className="label" htmlFor="deliv-link">{t("deliv.linkLabel")}</label>
              <input id="deliv-link" className="input" value={link} disabled={busy}
                placeholder={t("deliv.linkPlaceholder")} onChange={(e) => setLink(e.target.value)} />

              <label className="label" style={{ marginTop: 10 }} htmlFor="deliv-note">{t("deliv.noteLabel")}</label>
              <textarea id="deliv-note" className="input" rows={3} value={note} disabled={busy}
                placeholder={t("deliv.notePlaceholder")} onChange={(e) => setNote(e.target.value)} />

              {/* The dispute uploader, relabelled. It already does exactly
                  what is needed — uploads through the caller's own
                  /profiles/{userId}/media, so the server's ownership check
                  passes by construction — and only its LABEL was
                  dispute-specific, which is why the label became a prop
                  rather than this becoming a second uploader. */}
              <div style={{ marginTop: 10 }}>
                <EvidencePicker items={files} onChange={setFiles} disabled={busy}
                  label={t("deliv.attachments")} />
              </div>

              {nothingToSend && (
                <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>{t("deliv.needSomething")}</p>
              )}
              {/* What happens next, including the part the creator most wants
                  to know: silence still pays them. */}
              <p className="muted" style={{ fontSize: 13.5, marginTop: 8 }}>
                {t("deliv.submitHint", { n: REVIEW_WINDOW_DAYS })}
              </p>

              <button className="btn btn-primary" style={{ marginTop: 4 }} disabled={busy || nothingToSend}
                onClick={() => act(async () => {
                  await api("/deliverables", {
                    method: "POST", token, body: draftFrom(contractId, link, note, files)
                  });
                  setLink("");
                  setNote("");
                  setFiles([]);
                })}>
                {t("deliv.submit")}
              </button>
            </div>
          )}

          {rows.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <h4 style={{ margin: "0 0 2px", fontSize: 14 }}>{t("deliv.history")}</h4>
              {rows.map((row) => <SubmissionRow key={row.id} row={row} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
