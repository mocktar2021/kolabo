import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";

type Kind = "influencer" | "business";

export default function ProfileSetup() {
  const { t } = useTranslation();
  const { userId, isAuthenticated } = useAuth();
  const stored = (localStorage.getItem("kolabo_role") as Kind) || "influencer";
  const [kind, setKind] = useState<Kind>(stored === "business" ? "business" : "influencer");

  // Influencer fields
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [followers, setFollowers] = useState("");
  const [rate, setRate] = useState("");
  // Business fields
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function toggleCategory(c: string) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    setBusy(true);
    try {
      if (kind === "influencer") {
        await api(`/profiles/influencer/${userId}`, {
          method: "PUT",
          body: {
            bio: bio || null,
            categories,
            rate_card: rate ? { post: Number(rate) } : {},
            follower_count: followers ? Number(followers) : null
          }
        });
      } else {
        await api(`/profiles/business/${userId}`, {
          method: "PUT",
          body: { company_name: company, industry: industry || null, description: description || null }
        });
      }
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <h1>{t("profile.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("profile.sub")}</p>

        <div className="segment" style={{ margin: "18px 0 22px" }}>
          {(["influencer", "business"] as Kind[]).map((k) => (
            <div
              key={k}
              className={`segment-option ${kind === k ? "selected" : ""}`}
              onClick={() => setKind(k)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setKind(k); }}
            >
              <div className="t">{k === "influencer" ? t("profile.asCreator") : t("profile.asBusiness")}</div>
            </div>
          ))}
        </div>

        <div className="card">
          {error && <div className="alert alert-error">{error}</div>}
          {done && <div className="alert alert-success">{t("profile.saved")}</div>}
          <form onSubmit={onSubmit}>
            {kind === "influencer" ? (
              <>
                <div className="field">
                  <label className="label" htmlFor="bio">{t("profile.bio")}</label>
                  <textarea id="bio" className="input" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
                </div>
                <div className="field">
                  <span className="label">{t("profile.categories")}</span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {CATEGORIES.map((c) => (
                      <button
                        type="button"
                        key={c}
                        onClick={() => toggleCategory(c)}
                        className={`btn ${categories.includes(c) ? "btn-primary" : "btn-ghost"}`}
                        style={{ padding: "7px 13px", fontSize: 13 }}
                      >
                        {t(`cat.${c}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="field">
                  <label className="label" htmlFor="followers">{t("profile.followers")}</label>
                  <input id="followers" className="input" inputMode="numeric" value={followers}
                    onChange={(e) => setFollowers(e.target.value.replace(/\D/g, ""))} placeholder="10000" />
                </div>
                <div className="field">
                  <label className="label" htmlFor="rate">{t("profile.rate")}</label>
                  <input id="rate" className="input" inputMode="numeric" value={rate}
                    onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} placeholder="50000" />
                  <div className="hint">{t("profile.rateHint")}</div>
                </div>
              </>
            ) : (
              <>
                <div className="field">
                  <label className="label" htmlFor="company">{t("profile.company")}</label>
                  <input id="company" className="input" value={company} onChange={(e) => setCompany(e.target.value)} required />
                </div>
                <div className="field">
                  <label className="label" htmlFor="industry">{t("profile.industry")}</label>
                  <input id="industry" className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} />
                </div>
                <div className="field">
                  <label className="label" htmlFor="description">{t("profile.description")}</label>
                  <textarea id="description" className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
              </>
            )}
            <button className="btn btn-primary btn-lg" disabled={busy} type="submit">
              {busy ? t("auth.working") : t("profile.save")}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  );
}
