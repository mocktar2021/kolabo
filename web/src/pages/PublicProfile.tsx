import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api, mediaSrc } from "../lib/api";
import type { PublicProfile } from "../lib/types";

export default function PublicProfilePage() {
  const { t } = useTranslation();
  const { userId } = useParams();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    api<PublicProfile>(`/profiles/influencer/${userId}/public`)
      .then(setProfile)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [userId]);

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 820 }}>
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : error || !profile ? (
          <p className="muted">{t("public.notFound")}</p>
        ) : (
          <>
            <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ width: 96, height: 96, borderRadius: "50%", background: profile.avatar_url ? "transparent" : "var(--gradient-brand)", overflow: "hidden", flexShrink: 0 }}>
                {profile.avatar_url && <img src={mediaSrc(profile.avatar_url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
              </div>
              <div>
                <h1 style={{ margin: 0 }}>{profile.display_name || t("discover.creator")}</h1>
                {profile.headline && <p className="muted" style={{ margin: "4px 0 0" }}>{profile.headline}</p>}
                <div className="muted" style={{ fontSize: 13, marginTop: 6, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {profile.location && <span>{profile.location}</span>}
                  {profile.follower_count !== null && <span>{profile.follower_count.toLocaleString()} {t("discover.followers")}</span>}
                  {profile.review_count > 0 && <span>★ {profile.average_stars} ({profile.review_count})</span>}
                </div>
              </div>
            </div>

            {profile.categories.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 16 }}>
                {profile.categories.map((c) => (
                  <span key={c} style={{ fontSize: 12.5, color: "var(--muted)", background: "var(--surface-2)", padding: "4px 11px", borderRadius: 999 }}>{t(`cat.${c}`, c)}</span>
                ))}
              </div>
            )}

            {profile.bio && <p style={{ marginTop: 16 }}>{profile.bio}</p>}

            {profile.portfolio.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <h3>{t("public.portfolio")}</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                  {profile.portfolio.map((p) => (
                    <img key={p.id} src={mediaSrc(p.url)} alt="" style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", borderRadius: 10, border: "1px solid var(--line)" }} />
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginTop: 24 }}>
              <h3>{t("public.packages")}</h3>
              {profile.packages.length === 0 ? (
                <p className="muted" style={{ fontSize: 14 }}>{t("public.noPackages")}</p>
              ) : (
                <div style={{ display: "grid", gap: 12 }}>
                  {profile.packages.map((p) => (
                    <div key={p.id} className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: 18 }}>
                      <div>
                        <strong style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>{p.title}</strong>
                        <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>{p.platform} - {t(`deliverable.${p.deliverable_type}`, p.deliverable_type)}</div>
                        {p.description && <p style={{ fontSize: 13.5, margin: "8px 0 0" }}>{p.description}</p>}
                      </div>
                      <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
                        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 18 }}>{p.price_amount} {p.currency}</div>
                        <button className="btn btn-primary" style={{ marginTop: 8 }} disabled title={t("public.orderSoon")}>{t("public.order")}</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className="hint" style={{ marginTop: 10 }}>{t("public.orderSoon")}</p>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
