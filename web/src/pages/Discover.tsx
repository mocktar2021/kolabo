import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";

type Result = {
  user_id: string;
  bio: string | null;
  categories: string[];
  follower_count: number | null;
  country_code: string;
  is_verified: boolean;
};

function formatFollowers(n: number | null): string {
  if (n === null) return "-";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function Discover() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [category, setCategory] = useState("");
  const [country, setCountry] = useState("");
  const [minFollowers, setMinFollowers] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (category) params.set("category", category);
      if (country) params.set("country", country);
      if (minFollowers) params.set("min_followers", minFollowers);
      const data = await api<Result[]>(`/discovery/search?${params.toString()}`);
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [category, country, minFollowers]);

  useEffect(() => {
    search();
    api<{ influencer_user_id: string }[]>("/discovery/favorites", { token })
      .then((favs) => setFavorites(new Set(favs.map((f) => f.influencer_user_id))))
      .catch(() => undefined);
  }, [search, token]);

  async function toggleFavorite(id: string) {
    const isFav = favorites.has(id);
    try {
      if (isFav) {
        await api(`/discovery/favorites/${id}`, { method: "DELETE", token });
        setFavorites((prev) => { const n = new Set(prev); n.delete(id); return n; });
      } else {
        await api(`/discovery/favorites/${id}`, { method: "POST", token });
        setFavorites((prev) => new Set(prev).add(id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    search();
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page">
        <h1>{t("discover.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("discover.sub")}</p>

        <form className="card" style={{ marginTop: 16, padding: 18 }} onSubmit={onSubmit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12, alignItems: "end" }}>
            <div>
              <label className="label" htmlFor="f-cat">{t("discover.category")}</label>
              <select id="f-cat" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">{t("discover.any")}</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{t(`cat.${c}`)}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="f-country">{t("discover.country")}</label>
              <select id="f-country" className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
                <option value="">{t("discover.any")}</option>
                {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="f-min">{t("discover.minFollowers")}</label>
              <input id="f-min" className="input" inputMode="numeric" value={minFollowers}
                onChange={(e) => setMinFollowers(e.target.value.replace(/\D/g, ""))} placeholder="1000" />
            </div>
            <button className="btn btn-primary" type="submit">{t("discover.searchBtn")}</button>
          </div>
        </form>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 20 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : results.length === 0 ? (
            <p className="muted">{t("discover.empty")}</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
              {results.map((r) => (
                <div key={r.user_id} className="card" style={{ padding: 18 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ width: 44, height: 44, borderRadius: 12, background: "var(--gradient-brand)" }} aria-hidden="true" />
                    <button
                      className="btn btn-ghost"
                      style={{ padding: "6px 10px" }}
                      onClick={() => toggleFavorite(r.user_id)}
                      aria-label={t("discover.favorite")}
                    >
                      {favorites.has(r.user_id) ? "♥" : "♡"}
                    </button>
                  </div>
                  <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
                    <strong>{t("discover.creator")}</strong>
                    {r.is_verified && (
                      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--teal-600)", background: "#e7f7f5", padding: "2px 8px", borderRadius: 999 }}>
                        {t("discover.verified")}
                      </span>
                    )}
                  </div>
                  <div className="muted" style={{ fontSize: 13, margin: "4px 0 10px" }}>
                    {formatFollowers(r.follower_count)} {t("discover.followers")} - {r.country_code}
                  </div>
                  {r.bio && <p style={{ fontSize: 13.5, margin: "0 0 10px" }}>{r.bio}</p>}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {r.categories.slice(0, 3).map((c) => (
                      <span key={c} style={{ fontSize: 11.5, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 9px", borderRadius: 999 }}>
                        {t(`cat.${c}`, c)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
