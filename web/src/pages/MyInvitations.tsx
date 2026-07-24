import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import type { InvitationWithCampaign } from "../lib/types";

function ProposalForm({ campaignId, onDone }: { campaignId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [days, setDays] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaignId}/proposals`, {
        method: "POST",
        token,
        body: { rate_amount: Number(rate), rate_currency: currency, timeline_days: Number(days) }
      });
      setDone(true);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (done) return <div className="alert alert-success" style={{ marginBottom: 0 }}>{t("invitation.proposalSent")}</div>;

  return (
    <div>
      {error && <div className="alert alert-error">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 1fr auto", gap: 8, alignItems: "end" }}>
        <div>
          <label className="label">{t("invitation.rate")}</label>
          <input className="input" inputMode="numeric" value={rate} onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} placeholder="40000" />
        </div>
        <div>
          <label className="label">{t("campaign.currency")}</label>
          <select className="select" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label">{t("invitation.days")}</label>
          <input className="input" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} placeholder="7" />
        </div>
        <button className="btn btn-primary" disabled={busy || !rate || !days} onClick={submit}>{t("invitation.send")}</button>
      </div>
    </div>
  );
}

export default function MyInvitations() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [invitations, setInvitations] = useState<InvitationWithCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<InvitationWithCampaign[]>("/campaigns/invitations/mine", { token })
      .then(setInvitations)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        <h1>{t("invitation.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("invitation.sub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : invitations.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("invitation.empty")}</p></div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {invitations.map((inv) => (
                <div key={inv.id} className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <strong style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>{inv.campaign.title}</strong>
                    <span className="muted" style={{ fontSize: 13 }}>{inv.status}</span>
                  </div>
                  <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
                    {inv.campaign.budget_amount ? `${inv.campaign.budget_amount} ${inv.campaign.budget_currency}` : t("campaign.noBudget")}
                    {inv.campaign.deadline ? ` - ${inv.campaign.deadline}` : ""}
                  </p>
                  <ProposalForm campaignId={inv.campaign_id} onDone={load} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
