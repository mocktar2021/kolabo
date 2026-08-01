import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { InvitationWithCampaign } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. Enforced
   here too so the limit is hit as a full textarea rather than as a 422 after
   the creator has finished typing. */
const NOTE_MAX_LENGTH = 2000;

function ProposalForm({ campaignId, onDone }: { campaignId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      /* The note travels with the offer rather than in a message beside it, so
         the terms and the reasoning for them stay in one record — the same
         record the business answers and the contract is eventually written
         from. Omitted entirely when empty: a creator who wants to send bare
         numbers still can. */
      const trimmed = note.trim();
      await api(`/campaigns/${campaignId}/proposals`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          rate_currency: currency,
          timeline_days: Number(days),
          ...(trimmed ? { note: trimmed } : {})
        }
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
      <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 1fr", gap: 8, alignItems: "end" }}>
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
      </div>
      <div style={{ marginTop: 12 }}>
        <label className="label">{t("invitation.note")}</label>
        <textarea
          className="input"
          rows={3}
          maxLength={NOTE_MAX_LENGTH}
          style={{ resize: "vertical" }}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("invitation.notePlaceholder")}
        />
      </div>
      <button className="btn btn-primary" style={{ marginTop: 12 }} disabled={busy || !rate || !days} onClick={submit}>{t("invitation.send")}</button>
    </div>
  );
}

/* One invitation, read top to bottom the way the decision is actually made:
   who is asking, what they want made, what they budgeted, by when — and only
   at the bottom, what the creator wants to be paid. Quoting a number before
   seeing the deliverables was guesswork. */
function InvitationCard({ inv, onDone }: { inv: InvitationWithCampaign; onDone: () => void }) {
  const { t } = useTranslation();
  const c = inv.campaign;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          {/* business_company_name is null until the brand fills its profile;
              a generic label beats an empty line above the title. */}
          <div className="muted" style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
            {inv.business_company_name || t("invitation.brandFallback")}
          </div>
          <strong style={{ fontFamily: "var(--font-display)", fontSize: 18 }}>{c.title}</strong>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>{inv.status}</span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 24px", marginTop: 10, fontSize: 14 }}>
        <span>
          <span className="muted">{t("campaign.budget")} : </span>
          {c.budget_amount ? `${c.budget_amount} ${c.budget_currency ?? ""}`.trim() : t("campaign.noBudget")}
        </span>
        <span>
          <span className="muted">{t("campaign.deadline")} : </span>
          {c.deadline || t("invitation.noDeadline")}
        </span>
      </div>

      {/* Same one-line-per-deliverable shape as the campaign recap, so the
          creator is pricing exactly the list the brand wrote. */}
      <div style={{ marginTop: 16 }}>
        <span className="label">{t("campaign.deliverables")}</span>
        {c.deliverables.length === 0 ? (
          <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("campaign.noDeliverables")}</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
            {c.deliverables.map((d, i) => (
              <li key={i}>{d.quantity} × {t(`deliverable.${d.type}`, d.type)} — {PLATFORM_LABELS[d.platform] ?? d.platform}</li>
            ))}
          </ul>
        )}
      </div>

      {/* The rule above the line is the brand's; everything below it is the
          creator's answer, so the two are separated visually. */}
      <div style={{ borderTop: "1px solid var(--line)", marginTop: 20, paddingTop: 16 }}>
        <span className="label" style={{ marginBottom: 10 }}>{t("invitation.yourProposal")}</span>
        <ProposalForm campaignId={inv.campaign_id} onDone={onDone} />
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
                <InvitationCard key={inv.id} inv={inv} onDone={load} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
