import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { DeliverableRows, emptyDeliverable } from "../components/DeliverableRows";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES, MAX_DESCRIPTION_LENGTH } from "../lib/campaignOptions";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { Campaign, Deliverable } from "../lib/types";

export default function CampaignNew() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();

  const [title, setTitle] = useState("");
  /* The brief in prose, set at creation rather than only afterwards. A brand
     that has to publish first and explain second publishes a title and a
     budget, which is exactly the brief creators cannot price. */
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [deadline, setDeadline] = useState("");
  const [deliverables, setDeliverables] = useState<Deliverable[]>([emptyDeliverable()]);
  const [publishNow, setPublishNow] = useState(false);

  const [created, setCreated] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const campaign = await api<Campaign>("/campaigns/", {
        method: "POST",
        token,
        body: {
          title,
          // Null rather than an empty string: the column is nullable and "no
          // description" is an absence, not a description made of nothing.
          description: description.trim() || null,
          budget_amount: budget ? Number(budget) : null,
          budget_currency: budget ? currency : null,
          deliverables,
          deadline: deadline || null,
          publish: publishNow
        }
      });
      setCreated(campaign);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!created) return;
    setError(null);
    setBusy(true);
    try {
      const updated = await api<Campaign>(`/campaigns/${created.id}/publish`, { method: "POST", token });
      setCreated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        <h1>{t("campaign.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("campaign.sub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {created ? (
          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ fontFamily: "var(--font-display)", fontSize: 18 }}>{created.title}</strong>
              <span style={{ fontSize: 12, fontWeight: 600, color: created.status === "published" ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                {t(`campaign.status_${created.status}`, created.status)}
              </span>
            </div>
            <p className="muted" style={{ fontSize: 14, margin: "10px 0" }}>
              {created.budget_amount ? `${created.budget_amount} ${created.budget_currency}` : t("campaign.noBudget")}
              {created.deadline ? ` - ${created.deadline}` : ""}
            </p>
            {created.description && (
              <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: "0 0 10px" }}>{created.description}</p>
            )}
            <ul style={{ margin: "0 0 14px", paddingLeft: 18, fontSize: 14 }}>
              {created.deliverables.map((d, i) => (
                <li key={i}>{d.quantity} x {t(`deliverable.${d.type}`, d.type)} - {PLATFORM_LABELS[d.platform] ?? d.platform}</li>
              ))}
            </ul>
            {created.status !== "published" ? (
              <button className="btn btn-teal" disabled={busy} onClick={publish}>{t("campaign.publish")}</button>
            ) : (
              <div className="alert alert-success" style={{ marginBottom: 0 }}>{t("campaign.published")}</div>
            )}
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-ghost" onClick={() => setCreated(null)}>{t("campaign.another")}</button>
            </div>
          </div>
        ) : (
          <form className="card" style={{ marginTop: 16 }} onSubmit={onSubmit}>
            <div className="field">
              <label className="label" htmlFor="c-title">{t("campaign.name")}</label>
              <input id="c-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="field">
              <label className="label" htmlFor="c-description">{t("campaign.description")}</label>
              <textarea id="c-description" className="input" rows={4} maxLength={MAX_DESCRIPTION_LENGTH}
                style={{ resize: "vertical" }} value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("campaign.descriptionPlaceholder")} />
            </div>
            <div className="field" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
              <div>
                <label className="label" htmlFor="c-budget">{t("campaign.budget")}</label>
                <input id="c-budget" className="input" inputMode="numeric" value={budget}
                  onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))} placeholder="500000" />
              </div>
              <div>
                <label className="label" htmlFor="c-currency">{t("campaign.currency")}</label>
                <select id="c-currency" className="select" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="c-deadline">{t("campaign.deadline")}</label>
              <input id="c-deadline" className="input" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </div>

            <div className="field">
              <span className="label">{t("campaign.deliverables")}</span>
              <DeliverableRows value={deliverables} onChange={setDeliverables} />
            </div>

            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={publishNow} onChange={(e) => setPublishNow(e.target.checked)} />
                {t("campaign.publishNow")}
              </label>
            </div>

            <button className="btn btn-primary btn-lg" disabled={busy} type="submit">
              {busy ? t("auth.working") : t("campaign.create")}
            </button>
          </form>
        )}
      </div>
    </Layout>
  );
}
