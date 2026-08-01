import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { Layout } from "../components/Layout";
import { EvidencePicker } from "../components/EvidencePicker";
import { useAuth } from "../lib/auth";
import {
  DISPUTE_REASONS,
  MAX_STATEMENT_CHARS,
  MIN_STATEMENT_CHARS,
  openDisputeFor
} from "../lib/disputes";
import type {
  ContractDetail,
  Dispute,
  DisputeReason,
  Escrow,
  UploadedMedia
} from "../lib/types";

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
      <span className="muted">{label}</span>
      <span style={{ color: ok ? "var(--teal-600)" : "var(--ink)", fontWeight: ok ? 600 : 400 }}>{value}</span>
    </div>
  );
}

/* Raising a dispute, inline and on the contract itself.

   Not a modal. This is the most consequential button on the page and the
   terms it is about — the amount, the timeline, the document — are three
   centimetres above it; a dialog would cover exactly the thing somebody needs
   to reread while they write down what was supposed to happen.

   The reason is a select over the closed set because the admin queue triages
   by it and free text cannot be triaged. The statement carries the words, and
   its bounds are the server's, shown as a counter rather than discovered as a
   400 after four hundred words. */
function RaiseDisputeForm({
  escrowId,
  busy,
  onSubmit,
  onCancel
}: {
  escrowId: string;
  busy: boolean;
  onSubmit: (body: { reason: DisputeReason; statement: string; media_ids: string[] }) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState<DisputeReason>("not_delivered");
  const [statement, setStatement] = useState("");
  const [evidence, setEvidence] = useState<UploadedMedia[]>([]);

  const length = statement.trim().length;
  const tooShort = length < MIN_STATEMENT_CHARS;
  const tooLong = length > MAX_STATEMENT_CHARS;

  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
      <h4 style={{ margin: "0 0 10px" }}>{t("dispute.formTitle")}</h4>

      <label className="label" htmlFor={`dispute-reason-${escrowId}`}>{t("dispute.reason")}</label>
      <select
        id={`dispute-reason-${escrowId}`}
        className="input"
        value={reason}
        disabled={busy}
        onChange={(e) => setReason(e.target.value as DisputeReason)}
      >
        {DISPUTE_REASONS.map((r) => (
          <option key={r} value={r}>{t(`dispute.reason_${r}`)}</option>
        ))}
      </select>

      <label className="label" style={{ marginTop: 10 }} htmlFor={`dispute-statement-${escrowId}`}>
        {t("dispute.statement")}
      </label>
      <textarea
        id={`dispute-statement-${escrowId}`}
        className="input"
        rows={5}
        value={statement}
        disabled={busy}
        maxLength={MAX_STATEMENT_CHARS}
        placeholder={t("dispute.statementPlaceholder")}
        onChange={(e) => setStatement(e.target.value)}
      />
      <p className="muted" style={{ fontSize: 13, margin: "4px 0 10px" }}>
        {t("dispute.counter", { n: length, max: MAX_STATEMENT_CHARS })}
        {tooShort && length > 0 && ` · ${t("dispute.statementTooShort", { n: MIN_STATEMENT_CHARS })}`}
      </p>

      <EvidencePicker items={evidence} onChange={setEvidence} disabled={busy} />

      {/* Said before the act, not after it: the funds freeze for BOTH sides
          and the other party gets an exclusive window. A creator who learns
          that afterwards has frozen a payout they were about to receive. */}
      <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>{t("dispute.consequence")}</p>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          className="btn btn-primary"
          disabled={busy || tooShort || tooLong}
          onClick={() =>
            onSubmit({
              reason,
              statement: statement.trim(),
              media_ids: evidence.map((e) => e.id)
            })
          }
        >
          {t("dispute.submit")}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          {t("dispute.cancel")}
        </button>
      </div>
    </div>
  );
}

export default function ContractPage() {
  const { t } = useTranslation();
  const { token, userId, isAuthenticated } = useAuth();
  const { id } = useParams();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [raising, setRaising] = useState(false);
  /* Inline confirmation for calling the contract off, kept apart from the
     page-level error so a refused cancellation does not replace whatever the
     rest of the screen was saying. */
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const loadEscrow = useCallback(async (contractId: string) => {
    try {
      const e = await api<Escrow>(`/payments/escrow/by-contract/${contractId}`, { token });
      setEscrow(e);
      /* The caller's cases, in one request for every escrow they are in.
         There is no per-escrow dispute endpoint and there does not need to
         be: /disputes/mine is what a party is allowed to read, and a person
         has few enough of these that filtering client-side is free. A failure
         here is not worth an error state — it costs the link to an existing
         case, and the server still refuses a duplicate with a 409. */
      try {
        setDisputes(await api<Dispute[]>("/payments/disputes/mine", { token }));
      } catch {
        setDisputes([]);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setEscrow(null);
    }
  }, [token]);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const c = await api<ContractDetail>(`/contracts/${id}`, { token });
      setContract(c);
      if (c.fully_signed) await loadEscrow(c.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [id, token, loadEscrow]);

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

  /* Calling off a contract that has not yet bound anybody.

     EITHER PARTY, not just the buyer. Nothing is owed in either direction
     yet, and a creator who has realised they cannot deliver should be able to
     say so on the platform rather than by not answering — silence is what
     sends the next conversation to WhatsApp and the one after that
     off-platform for good.

     The refusals are mapped BY STATUS CODE, and the two codes mean different
     things:

       409  an escrow exists against this contract. Money at the provider
            turns "should this end" into "who is owed what", which is exactly
            the question the dispute and resolution path has rules for — a
            split, commission charged only on what was released, an audit log,
            an admin. A cancel button running alongside all of that would be a
            second, unaudited way for money to stop moving, and it would be
            the one somebody reached for first.

       400  already fully signed, or already cancelled. Both parties put their
            name to these terms, and a button that walks out of an agreement
            is the thing a contract exists to prevent. */
  async function cancelContract() {
    if (!contract) return;
    setBusy(true);
    setCancelError(null);
    try {
      await api(`/contracts/${contract.id}/cancel`, { method: "POST", token });
      setConfirmingCancel(false);
      await load();
    } catch (e) {
      setCancelError(
        e instanceof ApiError && e.status === 409
          ? t("undo.contractFunded")
          : e instanceof ApiError && e.status === 400
            ? t("undo.contractRefused")
            : e instanceof Error ? e.message : "Error"
      );
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const isBusiness = !!contract && userId === contract.business_user_id;
  const alreadySigned = !!contract && (isBusiness ? contract.business_signed : contract.influencer_signed);
  /* The other party on this contract, which is also the only person this
     reader is allowed to message about this campaign. A contract names
     exactly two people, so the counterparty is whichever of them is not the
     reader — no lookup required. */
  const counterpartyId = contract
    ? (isBusiness ? contract.influencer_user_id : contract.business_user_id)
    : null;
  /* The OPEN case on this escrow, if there is one — not the most recent.
     Since one open dispute at a time replaced one dispute ever, an escrow can
     carry withdrawn and resolved rows as well, and those are history: showing
     one where the live case goes would tell somebody their money is frozen
     over an argument that ended. */
  const openDispute = escrow ? openDisputeFor(disputes, escrow.id) : null;
  /* Offered while the contract binds nobody. Two conditions and not one,
     mirroring cancellation.py: a full signature closes it, and so does an
     escrow, separately. In practice they line up today because funding
     requires a full signature — but they are different facts, and the one
     that matters is the money. A cancelled contract is already closed, so it
     drops the offer too rather than leaving a button that answers 400. */
  const cancellable = !!contract && !contract.fully_signed && contract.status !== "cancelled" && !escrow;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : !contract ? (
          <p className="muted">{t("contract.notFound")}</p>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h1 style={{ margin: 0 }}>{t("contract.title")}</h1>
              <span style={{ fontSize: 12, fontWeight: 600, color: contract.fully_signed ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                {t(`contract.status_${contract.status}`, contract.status)}
              </span>
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <Row label={t("contract.rate")} value={`${contract.rate_amount} ${contract.rate_currency}`} />
              <Row label={t("contract.timeline")} value={`${contract.timeline_days}d`} />
              <Row label={t("contract.businessSigned")} value={contract.business_signed ? t("contract.yes") : t("contract.no")} ok={contract.business_signed} />
              <Row label={t("contract.creatorSigned")} value={contract.influencer_signed ? t("contract.yes") : t("contract.no")} ok={contract.influencer_signed} />
              {/* This contract IS the permission to talk, so the way into the
                  conversation belongs on it. A pending signature is enough:
                  both parties are looking at terms they are about to sign,
                  and making them wait for the second signature to ask a
                  question about it would push that question to WhatsApp. */}
              {counterpartyId && (
                <div style={{ marginTop: 10 }}>
                  <Link className="btn btn-ghost" to={`/messages?campaign=${contract.campaign_id}&with=${counterpartyId}`}>
                    {t("msg.openConversation")}
                  </Link>
                </div>
              )}
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0 }}>{t("contract.document")}</h3>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-body)", fontSize: 13, background: "var(--surface)", padding: 14, borderRadius: 8, margin: 0 }}>{contract.body}</pre>
            </div>

            {!contract.fully_signed && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3 style={{ marginTop: 0 }}>{t("contract.signHeading")}</h3>
                {alreadySigned ? (
                  <div className="alert alert-info" style={{ marginBottom: 0 }}>{t("contract.waitingOther")}</div>
                ) : (
                  <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
                    <div style={{ flex: 1 }}>
                      <label className="label">{t("contract.typeName")}</label>
                      <input className="input" value={signature} onChange={(e) => setSignature(e.target.value)} placeholder={t("contract.namePlaceholder")} />
                    </div>
                    <button className="btn btn-primary" disabled={busy || !signature}
                      onClick={() => act(() => api(`/contracts/${contract.id}/sign`, { method: "POST", token, body: { signature } }))}>
                      {t("contract.sign")}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Below the signature block on purpose: signing is what this page
                is for, and the way out should not sit above the way through. */}
            {cancellable && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3 style={{ marginTop: 0, fontSize: 16 }}>{t("undo.contractTitle")}</h3>
                {cancelError && <div className="alert alert-error">{cancelError}</div>}
                {!confirmingCancel ? (
                  <>
                    <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("undo.contractExplain")}</p>
                    <button type="button" className="btn btn-ghost" disabled={busy}
                      style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                      onClick={() => { setConfirmingCancel(true); setCancelError(null); }}>
                      {t("undo.contractCancel")}
                    </button>
                  </>
                ) : (
                  <>
                    {/* The consequence stated before the click, not after it:
                        the other party is told, the agreement is over, and
                        working together again means starting from a new
                        proposal. */}
                    <p style={{ fontSize: 14, margin: "0 0 10px" }}>{t("undo.contractConfirm")}</p>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button type="button" className="btn btn-ghost" disabled={busy}
                        style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                        onClick={cancelContract}>
                        {t("undo.contractYes")}
                      </button>
                      <button type="button" className="btn btn-ghost" disabled={busy}
                        onClick={() => { setConfirmingCancel(false); setCancelError(null); }}>
                        {t("undo.contractNo")}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {contract.fully_signed && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3 style={{ marginTop: 0 }}>{t("contract.payment")}</h3>
                {!escrow ? (
                  isBusiness ? (
                    <>
                      <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>{t("contract.fundHint")}</p>
                      <button className="btn btn-teal" disabled={busy}
                        onClick={() => act(() => api("/payments/escrow/fund", { method: "POST", token, body: { contract_id: contract.id } }))}>
                        {t("contract.fund")}
                      </button>
                    </>
                  ) : (
                    <div className="alert alert-info" style={{ marginBottom: 0 }}>{t("contract.awaitingFunding")}</div>
                  )
                ) : (
                  <>
                    <Row label={t("contract.escrowStatus")} value={t(`escrow.status_${escrow.status}`, escrow.status)} ok={escrow.status === "released"} />
                    <Row label={t("contract.amount")} value={`${escrow.amount} ${escrow.currency}`} />
                    {escrow.commission_amount !== null && (
                      <Row label={t("contract.commission")} value={`${escrow.commission_amount} ${escrow.currency}`} />
                    )}
                    {escrow.status === "held" && (
                      <>
                        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                          {isBusiness && (
                            <button className="btn btn-teal" disabled={busy}
                              onClick={() => act(() => api(`/payments/escrow/${escrow.id}/release`, { method: "POST", token }))}>
                              {t("contract.release")}
                            </button>
                          )}
                          {/* Either party. A dispute is a claim on money held
                              between the two of them, and either can be the
                              one who was let down. */}
                          {!raising && (
                            <button className="btn btn-ghost" disabled={busy} onClick={() => setRaising(true)}>
                              {t("dispute.open")}
                            </button>
                          )}
                        </div>
                        {raising && (
                          <RaiseDisputeForm
                            escrowId={escrow.id}
                            busy={busy}
                            onCancel={() => setRaising(false)}
                            onSubmit={(body) =>
                              act(async () => {
                                await api(`/payments/escrow/${escrow.id}/dispute`, { method: "POST", token, body });
                                setRaising(false);
                              })
                            }
                          />
                        )}
                      </>
                    )}
                    {escrow.status === "released" && <div className="alert alert-success" style={{ marginTop: 12, marginBottom: 0 }}>{t("contract.released")}</div>}
                    {escrow.status === "disputed" && (
                      <div style={{ marginTop: 12 }}>
                        <div className="alert alert-info">{t("dispute.existing")}</div>
                        {/* The case itself, rather than the form: there is
                            already a thread to answer in, and a second claim
                            over the same money would give an admin two half
                            cases. */}
                        {openDispute && (
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                              {t(`dispute.status_${openDispute.status}`)}
                            </span>
                            <Link className="btn btn-ghost" to={`/disputes/${openDispute.id}`}>
                              {t("dispute.view")}
                            </Link>
                          </div>
                        )}
                      </div>
                    )}
                    {escrow.status === "refunded" && <div className="alert alert-info" style={{ marginTop: 12, marginBottom: 0 }}>{t("contract.refunded")}</div>}
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
