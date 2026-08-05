import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import { ListFilter, type FilterOption } from "../components/ListFilter";
import { ListTabs, type Tab } from "../components/ListTabs";
import { contractIsCompleted, partitionByCompletion } from "../lib/lifecycle";
import type { Contract } from "../lib/types";

/* A row of GET /contracts/mine. The base contract plus what the card needs to
   be read at a glance: the campaign it is for and the OTHER party, named the
   shared way — a creator by display name and photo, a business by company name
   with no avatar, null when they have written no profile yet — and the escrow
   status, which is the only field that says whether the job is over. Local to
   this page because it is the only reader; the base Contract stays in
   lib/types. */
type ContractListItem = Contract & {
  campaign_title: string | null;
  counterparty_name: string | null;
  counterparty_avatar_url: string | null;
  created_at: string;
  escrow_status: string | null;
};

export default function ContractsList() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /* The lifecycle shelf, asked before anything else: work still running, or
     work that is history. Active first, because that is what somebody opening
     this screen came to do something about. */
  const [tab, setTab] = useState<Tab>("active");
  /* "" is all. Signed vs pending-signature is the split most people want here,
     and it falls out of filtering on contract.status. Filtered in memory. */
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    api<ContractListItem[]>("/contracts/mine", { token })
      .then(setContracts)
      .catch((e) => setError(errorText(e, t)))
      .finally(() => setLoading(false));
  }, [token, t]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const { active, completed } = partitionByCompletion(contracts, contractIsCompleted);
  const inTab = tab === "completed" ? completed : active;

  /* Chips from the statuses present IN THIS TAB, not in the whole list. Built
     from the full set they would offer a "cancelled" chip on the Active shelf
     that matches nothing — a control whose only outcome is an empty screen. */
  const statusOptions: FilterOption[] = Array.from(new Set(inTab.map((c) => c.status))).map((s) => ({
    value: s,
    label: t(`contract.status_${s}`, s)
  }));
  const shown = statusFilter ? inTab.filter((c) => c.status === statusFilter) : inTab;

  /* Changing shelf clears the chip. The two shelves hold different statuses,
     so carrying a selection across is how somebody lands on an empty list and
     concludes the tab is broken. */
  function selectTab(next: Tab) {
    setTab(next);
    setStatusFilter("");
  }

  return (
    <Layout>
      <div className="container page">
        <h1>{t("contract.listTitle")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("contract.listSub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {!loading && contracts.length > 0 && (
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
          ) : contracts.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("contract.listEmpty")}</p></div>
          ) : shown.length === 0 ? (
            /* Three different emptinesses, said differently: an empty shelf is
               not the same as a chip that matched nothing on a shelf that has
               rows. */
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
                <Link key={c.id} to={`/contracts/${c.id}`} className="card" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      {/* The job, named. A card that led with a bare rate made
                          somebody open every contract to remember which one it
                          was for. */}
                      <strong style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>
                        {c.campaign_title || t("contract.untitled")}
                      </strong>
                      {/* The other party, the shared way: a creator's face and
                          name, a business's company name and no avatar, a
                          neutral fallback rather than a user id when they have
                          written no profile yet. */}
                      <div className="muted" style={{ fontSize: 13, marginTop: 3, display: "flex", alignItems: "center", gap: 7 }}>
                        {c.counterparty_avatar_url && (
                          <img
                            src={mediaSrc(c.counterparty_avatar_url)}
                            alt=""
                            width={20}
                            height={20}
                            style={{ borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
                          />
                        )}
                        <span>{c.counterparty_name || t("contract.party")}</span>
                      </div>
                    </div>
                    <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: c.fully_signed ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                        {t(`contract.status_${c.status}`, c.status)}
                      </span>
                      {/* Where the money got to, when there is any. On the
                          Completed shelf this is the line that says WHICH
                          ending it was — paid, or refunded after a dispute —
                          which the contract's own status cannot tell apart. */}
                      {c.escrow_status && (
                        <span className="muted" style={{ fontSize: 11.5 }}>
                          {t(`escrow.status_${c.escrow_status}`, c.escrow_status)}
                        </span>
                      )}
                    </div>
                  </div>
                  {/* The terms and the date, on one muted line under the title:
                      the rate leads because it is what a contract is about. */}
                  <div className="muted" style={{ fontSize: 13, marginTop: 10, display: "flex", flexWrap: "wrap", gap: "2px 14px" }}>
                    <span style={{ fontWeight: 700, color: "var(--ink)" }}>{c.rate_amount} {c.rate_currency}</span>
                    <span>{c.timeline_days} {t("campaign.daysShort")}</span>
                    <span>{c.language.toUpperCase()}</span>
                    <span>{new Date(parseApiDate(c.created_at)).toLocaleDateString(i18n.language)}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
