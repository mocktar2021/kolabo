import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import type { ContractDetail, Escrow } from "../lib/types";

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
      <span className="muted">{label}</span>
      <span style={{ color: ok ? "var(--teal-600)" : "var(--ink)", fontWeight: ok ? 600 : 400 }}>{value}</span>
    </div>
  );
}

export default function ContractPage() {
  const { t } = useTranslation();
  const { token, userId, isAuthenticated } = useAuth();
  const { id } = useParams();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadEscrow = useCallback(async (contractId: string) => {
    try {
      const e = await api<Escrow>(`/payments/escrow/by-contract/${contractId}`, { token });
      setEscrow(e);
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

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const isBusiness = !!contract && userId === contract.business_user_id;
  const alreadySigned = !!contract && (isBusiness ? contract.business_signed : contract.influencer_signed);

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
                      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                        {isBusiness && (
                          <button className="btn btn-teal" disabled={busy}
                            onClick={() => act(() => api(`/payments/escrow/${escrow.id}/release`, { method: "POST", token }))}>
                            {t("contract.release")}
                          </button>
                        )}
                        <button className="btn btn-ghost" disabled={busy}
                          onClick={() => act(() => api(`/payments/escrow/${escrow.id}/dispute`, { method: "POST", token }))}>
                          {t("contract.dispute")}
                        </button>
                      </div>
                    )}
                    {escrow.status === "released" && <div className="alert alert-success" style={{ marginTop: 12, marginBottom: 0 }}>{t("contract.released")}</div>}
                    {escrow.status === "disputed" && <div className="alert alert-info" style={{ marginTop: 12, marginBottom: 0 }}>{t("contract.disputed")}</div>}
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
