import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorCard } from "../components/CreatorCard";
import { api } from "../lib/api";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";
import type { SearchResult } from "../lib/types";

function Feature({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="feature">
      <div className="ic" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

export default function Landing() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const [country, setCountry] = useState("");
  const [featured, setFeatured] = useState<SearchResult[]>([]);

  // Real creators, shown before anyone is asked to sign up.
  useEffect(() => {
    api<SearchResult[]>("/discovery/search?limit=8").then(setFeatured).catch(() => undefined);
  }, []);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const qs = new URLSearchParams();
    if (category) qs.set("category", category);
    if (country) qs.set("country", country);
    navigate(`/discover?${qs.toString()}`);
  }

  return (
    <Layout>
      <section className="hero">
        <div className="container" style={{ padding: "56px 0 44px" }}>
          <div style={{ maxWidth: 720 }}>
            <span className="eyebrow">{t("landing.eyebrow")}</span>
            <h1 style={{ fontSize: 42 }}>{t("landing.title")}</h1>
            <p className="lead">{t("landing.lead")}</p>
          </div>

          <form className="card" style={{ marginTop: 8, padding: 16 }} onSubmit={onSearch}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 12, alignItems: "end" }}>
              <div>
                <label className="label" htmlFor="h-cat">{t("discover.category")}</label>
                <select id="h-cat" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="">{t("discover.any")}</option>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="h-country">{t("discover.country")}</label>
                <select id="h-country" className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
                  <option value="">{t("discover.any")}</option>
                  {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                </select>
              </div>
              <button className="btn btn-primary btn-lg" type="submit">{t("landing.searchCreators")}</button>
            </div>
            <div className="hint" style={{ marginTop: 10 }}>{t("landing.freeToSearch")}</div>
          </form>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
            {CATEGORIES.slice(0, 8).map((c) => (
              <Link key={c} to={`/discover?category=${c}`} className="btn btn-ghost" style={{ padding: "7px 14px", fontSize: 13, background: "#fff" }}>
                {t(`cat.${c}`)}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="container" style={{ padding: "40px 0 8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 24 }}>{t("landing.featured")}</h2>
            <Link className="btn btn-ghost" to="/discover">{t("landing.seeAll")}</Link>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
            {featured.map((r) => <CreatorCard key={r.user_id} r={r} />)}
          </div>
        </section>
      )}

      <section className="features">
        <div className="container">
          <h2 style={{ fontSize: 24, marginBottom: 18 }}>{t("landing.whyKolabo")}</h2>
          <div className="feature-grid">
            <Feature title={t("landing.f1t")} desc={t("landing.f1d")} />
            <Feature title={t("landing.f2t")} desc={t("landing.f2d")} />
            <Feature title={t("landing.f3t")} desc={t("landing.f3d")} />
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 28 }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate("/register?role=influencer")}>{t("landing.ctaCreator")}</button>
            <button className="btn btn-ghost btn-lg" onClick={() => navigate("/register?role=business")}>{t("landing.ctaBusiness")}</button>
          </div>
        </div>
      </section>
    </Layout>
  );
}
