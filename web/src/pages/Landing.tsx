import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorCard } from "../components/CreatorCard";
import { api } from "../lib/api";
import { CATEGORIES } from "../lib/categories";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import type { SearchResult } from "../lib/types";

/* Placeholder social proof. Replace with real pilot names and numbers as they
   land; kept obviously generic so nothing here reads as a claim we cannot back. */
const PLACEHOLDER_BRANDS = ["Votre marque", "Brand", "Enterprise", "Startup", "Agence", "NGO"];

export default function Landing() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [platform, setPlatform] = useState("");
  const [q, setQ] = useState("");
  const [featured, setFeatured] = useState<SearchResult[]>([]);

  useEffect(() => {
    api<SearchResult[]>("/discovery/search?limit=8").then(setFeatured).catch(() => undefined);
  }, []);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (platform) qs.set("platform", platform);
    navigate(`/discover?${qs.toString()}`);
  }

  const stats = [
    { value: t("landing.statCountriesValue"), label: t("landing.statCountries") },
    { value: t("landing.statEscrowValue"), label: t("landing.statEscrow") },
    { value: t("landing.statLangValue"), label: t("landing.statLang") },
    { value: t("landing.statFeeValue"), label: t("landing.statFee") }
  ];

  const steps = [
    { t: t("landing.step1t"), d: t("landing.step1d") },
    { t: t("landing.step2t"), d: t("landing.step2d") },
    { t: t("landing.step3t"), d: t("landing.step3d") },
    { t: t("landing.step4t"), d: t("landing.step4d") }
  ];

  const faqs = [
    { q: t("landing.faq1q"), a: t("landing.faq1a") },
    { q: t("landing.faq2q"), a: t("landing.faq2a") },
    { q: t("landing.faq3q"), a: t("landing.faq3a") },
    { q: t("landing.faq4q"), a: t("landing.faq4a") }
  ];

  return (
    <Layout>
      <section className="hero-dark">
        <div className="container">
          <h1>
            {t("landing.heroA")} <span className="accent">{t("landing.heroAccent")}</span> {t("landing.heroB")}
          </h1>
          <p className="hero-sub">{t("landing.lead")}</p>

          <form className="search-bar" onSubmit={onSearch}>
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label={t("landing.platform")}>
              <option value="">{t("landing.allPlatforms")}</option>
              {SOCIAL_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("landing.searchPlaceholder")} />
            <button className="btn btn-primary" type="submit">{t("landing.searchCreators")}</button>
          </form>

          <div className="chip-row">
            {CATEGORIES.slice(0, 8).map((c) => (
              <Link key={c} className="chip" to={`/discover?category=${c}`}>{t(`cat.${c}`)}</Link>
            ))}
          </div>
          <p style={{ textAlign: "center", color: "#8b93a7", fontSize: 13, marginTop: 18 }}>{t("landing.freeToSearch")}</p>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="container section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <div>
              <h2 style={{ margin: 0 }}>{t("landing.featured")}</h2>
              <p className="section-sub" style={{ margin: 0 }}>{t("landing.featuredSub")}</p>
            </div>
            <Link className="btn btn-ghost" to="/discover">{t("landing.seeAll")}</Link>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 16 }}>
            {featured.map((r) => <CreatorCard key={r.user_id} r={r} />)}
          </div>
        </section>
      )}

      <section className="container section-tight">
        <p style={{ textAlign: "center", color: "var(--muted)", fontSize: 13.5, marginBottom: 18 }}>{t("landing.trustedBy")}</p>
        <div className="logo-row">
          {PLACEHOLDER_BRANDS.map((b) => <span key={b} className="logo-chip">{b}</span>)}
        </div>
      </section>

      <section className="section" style={{ background: "var(--surface)" }}>
        <div className="container">
          <h2>{t("landing.howItWorks")}</h2>
          <p className="section-sub">{t("landing.howItWorksSub")}</p>
          <div className="step-grid">
            {steps.map((s, i) => (
              <div key={s.t}>
                <span className="step-num">{i + 1}</span>
                <h3 style={{ fontSize: 17 }}>{s.t}</h3>
                <p className="muted" style={{ fontSize: 14.5, margin: 0 }}>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container section">
        <h2>{t("landing.whyKolabo")}</h2>
        <p className="section-sub">{t("landing.whySub")}</p>
        <div className="feature-grid">
          {[
            { t: t("landing.f1t"), d: t("landing.f1d") },
            { t: t("landing.f2t"), d: t("landing.f2d") },
            { t: t("landing.f3t"), d: t("landing.f3d") }
          ].map((f) => (
            <div className="feature" key={f.t}>
              <div className="ic" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </div>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ background: "var(--surface)" }}>
        <div className="container">
          <div className="stat-grid">
            {stats.map((s) => (
              <div key={s.label}>
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container section">
        <h2>{t("landing.testimonials")}</h2>
        <p className="section-sub">{t("landing.testimonialsSub")}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
          {[1, 2, 3].map((n) => (
            <div className="quote-card" key={n}>
              <p>{t(`landing.quote${n}`)}</p>
              <div className="quote-who">
                <span className="quote-avatar" aria-hidden="true" />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{t(`landing.quote${n}Who`)}</div>
                  <div className="muted" style={{ fontSize: 12.5 }}>{t(`landing.quote${n}Role`)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="hint" style={{ marginTop: 14 }}>{t("landing.placeholderNote")}</p>
      </section>

      <section className="section" style={{ background: "var(--surface)" }}>
        <div className="container" style={{ maxWidth: 760 }}>
          <h2>{t("landing.faq")}</h2>
          <div style={{ marginTop: 14 }}>
            {faqs.map((f) => (
              <div className="faq-item" key={f.q}>
                <h4>{f.q}</h4>
                <p>{f.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="container">
          <h2>{t("landing.ctaTitle")}</h2>
          <p>{t("landing.ctaSub")}</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="btn btn-lg" style={{ background: "#fff", color: "var(--indigo)" }}
              onClick={() => navigate("/register?role=influencer")}>{t("landing.ctaCreator")}</button>
            <button className="btn btn-lg" style={{ background: "rgba(255,255,255,0.16)", color: "#fff", borderColor: "rgba(255,255,255,0.4)" }}
              onClick={() => navigate("/register?role=business")}>{t("landing.ctaBusiness")}</button>
          </div>
        </div>
      </section>
    </Layout>
  );
}
