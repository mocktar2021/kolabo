import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { DeliverableRows, emptyDeliverable } from "../components/DeliverableRows";
import { LicenceFields } from "../components/LicenceFields";
import { EMPTY_TARGETING, TargetingFields, targetingBody, type Targeting } from "../components/TargetingFields";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CURRENCIES, MAX_DESCRIPTION_LENGTH } from "../lib/campaignOptions";
import { EMPTY_LICENCE, licenceBody, licenceIsComplete, type LicenceDraft } from "../lib/licence";
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
  /* WHAT THE BRAND MAY DO WITH THE CONTENT, set at creation for the same reason
     the description is and a stronger one besides.

     Article 10 of the collaboration contract makes the parties choose between
     three options, and leaves the choice blank to be filled in per contract.
     The founder settled that the brand states it BEFORE the contract exists,
     and this is one of the two screens where it does so.

     IT CANNOT WAIT FOR SIGNATURE, which is the whole argument. A creator prices
     option 2, where the brand may run the content as a paid advertisement,
     quite differently from option 1, where the post stays on the creator's own
     accounts. Asking at signature would mean the creator priced one job and
     signed another, and the only honest remedy at that point is to reopen the
     negotiation. So it belongs with the budget and the deliverables, which are
     the other things a creator prices against. */
  const [licence, setLicence] = useState<LicenceDraft>(EMPTY_LICENCE);
  /* Who the brief is for, and whether strangers may answer it. Set at
     creation rather than only on a later PATCH because deciding who a brief
     is for is part of writing it — the API takes these fields on POST for
     exactly that reason, so a brand does not save a brief and then open it in
     a second request. Still defaults to closed: nobody opens a brief to the
     whole platform by accident. */
  const [targeting, setTargeting] = useState<Targeting>(EMPTY_TARGETING);

  const [created, setCreated] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    /* Null only for an unanswered option, and the button below is disabled
       until one is chosen, so this is a guard rather than a branch anybody
       reaches. It exists because licenceBody is the one function that knows
       which of the four further fields belong to the chosen option, and a
       caller that spread an unchecked result would be free to post a licence
       with no option on it. The server would refuse that with
       licence_terms_invalid; refusing it here costs nobody a round trip. */
    const terms = licenceBody(licence);
    if (!terms) return;
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
          publish: publishNow,
          /* All five licence fields, with explicit nulls for the ones this
             option does not use. See licenceBody in lib/licence.ts for why
             they are nulls rather than absent keys. */
          ...terms,
          ...targetingBody(targeting)
        }
      });
      setCreated(campaign);
    } catch (err) {
      setError(errorText(err, t));
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
      setError(errorText(err, t));
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
            {/* Confirmed back rather than assumed: opening a brief to the whole
                platform is the one setting on this form whose consequence
                arrives from strangers, and a brand should see that it took. */}
            {created.is_open && (
              <p className="muted" style={{ fontSize: 13, margin: "0 0 14px" }}>{t("target.openHint")}</p>
            )}
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

            {/* IMMEDIATELY AFTER THE DELIVERABLES AND BEFORE THE TARGETING, and
                that order is the argument for the whole feature. Above this
                line the brand has said what it wants made; here it says what it
                may then do with it; below it, who it hopes will answer. The
                first two are what a creator prices, so they belong together,
                and the audience is a separate question. */}
            <LicenceFields idPrefix="c" value={licence} onChange={setLicence} disabled={busy} />

            {/* Targeting ranks who sees this brief first and blocks nobody from
                applying. The rule lives in components/TargetingFields.tsx and
                is stated on screen there, because a brand that believes it set
                a hard filter declines off-target applications unread. */}
            <TargetingFields idPrefix="c" value={targeting} onChange={setTargeting} />

            <div className="field">
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input type="checkbox" checked={publishNow} onChange={(e) => setPublishNow(e.target.checked)} />
                {t("campaign.publishNow")}
              </label>
            </div>

            {/* THE LICENCE IS REQUIRED TO CREATE A BRIEF AT ALL, not only to
                publish one. A brief with no licence on it is a brief no creator
                can price, and the missing clause would surface as
                contract_licence_terms_missing at the far end, when a contract
                is being generated and somebody has already done the work. The
                sentence saying what is still missing is inside LicenceFields,
                under the control it is about, so both screens that use that
                control get it without holding their own copy. */}
            <button className="btn btn-primary btn-lg" disabled={busy || !licenceIsComplete(licence)} type="submit">
              {busy ? t("auth.working") : t("campaign.create")}
            </button>
          </form>
        )}
      </div>
    </Layout>
  );
}
