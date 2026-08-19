import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorCard } from "../components/CreatorCard";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import type { SearchResult } from "../lib/types";

export default function Discover() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [params, setParams] = useSearchParams();
  const [category, setCategory] = useState(params.get("category") || "");
  const [country, setCountry] = useState(params.get("country") || "");
  // Seeded from the URL so the landing hero's platform choice (passed the same
  // way as the free-text q) lands directly in the filter.
  const [platform, setPlatform] = useState(params.get("platform") || "");
  const [minFollowers, setMinFollowers] = useState(params.get("min_followers") || "");
  const q = params.get("q") || "";
  const [results, setResults] = useState<SearchResult[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (category) qs.set("category", category);
      if (country) qs.set("country", country);
      if (platform) qs.set("platform", platform);
      if (minFollowers) qs.set("min_followers", minFollowers);
      if (q) qs.set("q", q);
      const data = await api<SearchResult[]>(`/discovery/search?${qs.toString()}`);
      setResults(data);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setLoading(false);
    }
  }, [category, country, platform, minFollowers, q, t]);

  useEffect(() => {
    search();
  }, [search]);

  // Favorites are a signed-in feature; browsing stays public.
  useEffect(() => {
    if (!isAuthenticated) return;
    api<{ influencer_user_id: string }[]>("/discovery/favorites", { token })
      .then((favs) => setFavorites(new Set(favs.map((f) => f.influencer_user_id))))
      .catch(() => undefined);
  }, [isAuthenticated, token]);

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
      setError(errorText(err, t));
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams();
    if (category) next.set("category", category);
    if (country) next.set("country", country);
    if (platform) next.set("platform", platform);
    if (minFollowers) next.set("min_followers", minFollowers);
    if (q) next.set("q", q);
    setParams(next);
    search();
  }

  return (
    <Layout>
      <div className="container page">
        <h1>{t("discover.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("discover.sub")}</p>

        <form className="card" style={{ marginTop: 16, padding: 18 }} onSubmit={onSubmit}>
          <div className="filter-grid">
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
              <label className="label" htmlFor="f-platform">{t("discover.platform")}</label>
              <select id="f-platform" className="select" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option value="">{t("discover.any")}</option>
                {SOCIAL_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="f-min">{t("discover.minFollowers")}</label>
              <input id="f-min" className="input" inputMode="numeric" value={minFollowers}
                onChange={(e) => setMinFollowers(e.target.value.replace(/\D/g, ""))} placeholder="1000" />
            </div>
            <button className="btn btn-primary filter-submit" type="submit">{t("discover.searchBtn")}</button>
          </div>
        </form>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 20 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : results.length === 0 ? (
            <p className="muted">{t("discover.empty")}</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
              {results.map((r) => (
                <CreatorCard
                  key={r.user_id}
                  r={r}
                  action={isAuthenticated ? (
                    <button className="btn btn-ghost" style={{ padding: "4px 9px" }}
                      onClick={() => toggleFavorite(r.user_id)} aria-label={t("discover.favorite")}>
                      {favorites.has(r.user_id) ? "♥" : "♡"}
                    </button>
                  ) : undefined}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
