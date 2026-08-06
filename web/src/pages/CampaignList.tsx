import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { ListFilter, type FilterOption } from "../components/ListFilter";
import { ListTabs, type Tab } from "../components/ListTabs";
import { campaignIsCompleted, partitionByCompletion, type CompletableContract } from "../lib/lifecycle";
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
  /* The caller's contracts, fetched ONLY to work out which campaigns are
     finished. A campaign has no completed status of its own — what ends it is
     the work underneath it ending — and that work lives on the contracts. See
     lib/lifecycle.ts.

     A second request rather than a second field on the campaign, because the
     campaign endpoint would have to answer "are all your contracts settled"
     for every row, and the client already has a reason to hold this list.
     Both are whole-set fetches at pilot volume, which is the same call
     ListFilter's docstring makes about filtering in memory. */
  const [contracts, setContracts] = useState<CompletableContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("active");
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
      .catch((e) => setError(errorText(e, t)))
      .finally(() => setLoading(false));
  }, [token, t]);

  useEffect(() => {
    /* Failing here is not worth an error state. It costs the Completed shelf
       its accuracy — every campaign reads as active — and leaves the rest of
       the page working, which is a far better outcome than a list of
       campaigns replaced by an error about contracts. */
    api<CompletableContract[]>("/contracts/mine", { token })
      .then(setContracts)
      .catch(() => setContracts([]));
  }, [token]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const { active, completed } = partitionByCompletion(campaigns, (c) =>
    campaignIsCompleted(c, contracts)
  );
  const inTab = tab === "completed" ? completed : active;

  /* Chips are built from the statuses present IN THIS TAB, so no chip ever
     matches an empty set (draft / published / cancelled, whichever exist
     here). The label reuses the same key the row's pill renders, so a status
     is worded one way across the screen. */
  const statusOptions: FilterOption[] = Array.from(new Set(inTab.map((c) => c.status))).map((s) => ({
    value: s,
    label: t(`campaign.status_${s}`, s)
  }));
  const shown = statusFilter ? inTab.filter((c) => c.status === statusFilter) : inTab;

  function selectTab(next: Tab) {
    setTab(next);
    setStatusFilter("");
  }

  return (
    <Layout>
      <div className="container page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0 }}>{t("campaign.listTitle")}</h1>
          {canCreate && <Link className="btn btn-primary" to="/campaigns/new">{t("campaign.new")}</Link>}
        </div>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {!loading && campaigns.length > 0 && (
          <>
            <ListTabs
              active={tab}
              activeCount={active.length}
              completedCount={completed.length}
              onChange={selectTab}
            />
            <ListFilter options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
          </>
        )}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : campaigns.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("campaign.listEmpty")}</p></div>
          ) : shown.length === 0 ? (
            <div className="card">
              <p className="muted" style={{ margin: 0 }}>
                {inTab.length === 0
                  ? t(tab === "completed" ? "lf.noneCompleted" : "lf.noneActive")
                  : t("filt.none")}
              </p>
            </div>
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
