import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { mediaSrc } from "../lib/api";
import type { SearchResult } from "../lib/types";

export function formatFollowers(n: number | null): string {
  if (n === null) return "-";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function CreatorCard({ r, action }: { r: SearchResult; action?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <Link to={`/u/${r.user_id}`} style={{ display: "block", aspectRatio: "4/3", background: r.avatar_url ? "var(--surface-2)" : "var(--gradient-brand)" }}>
        {r.avatar_url && <img src={mediaSrc(r.avatar_url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />}
      </Link>
      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>
                {r.display_name || t("discover.creator")}
              </strong>
              {r.is_verified && (
                <span style={{ fontSize: 10.5, fontWeight: 600, color: "var(--teal-600)", background: "#e7f7f5", padding: "2px 7px", borderRadius: 999 }}>
                  {t("discover.verified")}
                </span>
              )}
            </div>
            {r.headline && <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>{r.headline}</div>}
          </div>
          {action}
        </div>

        <div className="muted" style={{ fontSize: 12.5 }}>
          {formatFollowers(r.follower_count)} {t("discover.followers")} - {r.country_code}
          {r.review_count > 0 && <span> - ★ {r.average_stars} ({r.review_count})</span>}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {r.categories.slice(0, 3).map((c) => (
            <span key={c} style={{ fontSize: 11, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 8px", borderRadius: 999 }}>
              {t(`cat.${c}`, c)}
            </span>
          ))}
        </div>

        <div style={{ marginTop: "auto", paddingTop: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {r.starting_price_amount !== null ? (
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>
              {r.starting_price_amount} {r.starting_price_currency}
            </span>
          ) : (
            <span className="muted" style={{ fontSize: 12.5 }}>{t("discover.onRequest")}</span>
          )}
          <Link to={`/u/${r.user_id}`} className="btn btn-ghost" style={{ padding: "6px 12px", fontSize: 13 }}>
            {t("discover.viewProfile")}
          </Link>
        </div>
      </div>
    </div>
  );
}
