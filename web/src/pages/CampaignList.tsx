import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { ListFilter, type FilterOption } from "../components/ListFilter";
import type { Campaign } from "../lib/types";

function StatusPill({ status }: { status: string }) {
  const { t } = useTranslation();
  const published = status === "published";
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color: published ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
      {t(`campaign.status_${status}`, status)}
    </span>
  );
}

export default function CampaignList() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /* "" is all. Filtered in memory below — /campaigns/mine returns the whole
     set and it is short at pilot volume. */
  const [statusFilter, setStatusFilter] = useState("");
  /* A campaign is a brand-side artifact: only businesses and agencies can own
     one, and the API answers 403 to a creator who posts to /campaigns/. A
     creator's equivalent is a package on their profile, so they get no create
     button here rather than a button that fails. */
  const canCreate = isBusinessLike(getStoredRole());

  useEffect(() => {
    api<Campaign[]>("/campaigns/mine", { token })
      .then(setCampaigns)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [token]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  /* Chips are built from the statuses actually present, so no chip ever
     matches an empty set (draft / published / cancelled, whichever exist).
     The label reuses the same key the row's pill renders, so a status is
     worded one way across the screen. */
  const statusOptions: FilterOption[] = Array.from(new Set(campaigns.map((c) => c.status))).map((s) => ({
    value: s,
    label: t(`campaign.status_${s}`, s)
  }));
  const shown = statusFilter ? campaigns.filter((c) => c.status === statusFilter) : campaigns;

  return (
    <Layout>
      <div className="container page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0 }}>{t("campaign.listTitle")}</h1>
          {canCreate && <Link className="btn btn-primary" to="/campaigns/new">{t("campaign.new")}</Link>}
        </div>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {!loading && campaigns.length > 0 && (
          <ListFilter options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        )}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : campaigns.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("campaign.listEmpty")}</p></div>
          ) : shown.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("filt.none")}</p></div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {shown.map((c) => (
                <Link key={c.id} to={`/campaigns/${c.id}`} className="card" style={{ textDecoration: "none", color: "inherit", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>{c.title}</strong>
                    <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                      {c.budget_amount ? `${c.budget_amount} ${c.budget_currency}` : t("campaign.noBudget")}
                      {c.deadline ? ` - ${c.deadline}` : ""}
                    </div>
                  </div>
                  <StatusPill status={c.status} />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
