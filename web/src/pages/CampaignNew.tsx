import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { PLATFORM_LABELS, SELLABLE_PLATFORMS, deliverablesFor } from "../lib/platforms";

type Deliverable = { platform: string; type: string; quantity: number };

/* Quantity choices for a deliverable row. A dropdown rather than a free text
   field: a fat finger on a number input turns "10 reels" into "100 reels" and
   the brand only finds out when the proposals come back absurd. Twenty is far
   past any real brief, and this is the same control the package form uses. */
const QUANTITIES = Array.from({ length: 20 }, (_, i) => i + 1);

/* A fresh row starts on the first platform's first deliverable so the pair is
   valid by construction; the backend validates every pair against the same
   catalog and answers 400 for anything else. */
function emptyDeliverable(): Deliverable {
  const platform = SELLABLE_PLATFORMS[0].id;
  return { platform, type: deliverablesFor(platform)[0], quantity: 1 };
}

type Campaign = {
  id: string;
  title: string;
  budget_amount: number | null;
  budget_currency: string | null;
  deliverables: Deliverable[];
  deadline: string | null;
  status: string;
};

export default function CampaignNew() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();

  const [title, setTitle] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [deadline, setDeadline] = useState("");
  const [deliverables, setDeliverables] = useState<Deliverable[]>([emptyDeliverable()]);
  const [publishNow, setPublishNow] = useState(false);

  const [created, setCreated] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function updateDeliverable(i: number, patch: Partial<Deliverable>) {
    setDeliverables((prev) => prev.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));
  }
  /* Switching platform resets the type to that platform's first deliverable:
     keeping the old type would silently build an invalid pair (e.g. a TikTok
     "reel") that only surfaces as a 400 on submit. */
  function changePlatform(i: number, platform: string) {
    updateDeliverable(i, { platform, type: deliverablesFor(platform)[0] });
  }
  function addDeliverable() {
    setDeliverables((prev) => [...prev, emptyDeliverable()]);
  }
  function removeDeliverable(i: number) {
    setDeliverables((prev) => prev.filter((_, idx) => idx !== i));
  }

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
              {deliverables.map((d, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 88px auto", gap: 8, marginBottom: 8 }}>
                  <select className="select" value={d.platform} onChange={(e) => changePlatform(i, e.target.value)}>
                    {SELLABLE_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                  </select>
                  <select className="select" value={d.type} onChange={(e) => updateDeliverable(i, { type: e.target.value })}>
                    {deliverablesFor(d.platform).map((ty) => <option key={ty} value={ty}>{t(`deliverable.${ty}`, ty)}</option>)}
                  </select>
                  <select className="select" aria-label={t("profile.packageQuantity")} value={d.quantity}
                    onChange={(e) => updateDeliverable(i, { quantity: Number(e.target.value) })}>
                    {QUANTITIES.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                  <button type="button" className="btn btn-ghost" onClick={() => removeDeliverable(i)} disabled={deliverables.length === 1} aria-label="remove">x</button>
                </div>
              ))}
              <button type="button" className="btn btn-ghost" style={{ padding: "7px 13px", fontSize: 13 }} onClick={addDeliverable}>+ {t("campaign.addDeliverable")}</button>
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
