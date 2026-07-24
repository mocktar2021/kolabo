import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { CampaignDetail } from "../lib/types";

function shortId(id: string): string {
  return id.slice(0, 8);
}

export default function CampaignDetailPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { id } = useParams();
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api<CampaignDetail>(`/campaigns/${id}`, { token });
      setCampaign(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [id, token]);

  useEffect(() => {
    load();
    api<{ influencer_user_id: string }[]>("/discovery/favorites", { token })
      .then((f) => setFavorites(f.map((x) => x.influencer_user_id)))
      .catch(() => undefined);
  }, [load, token]);

  async function publish() {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/publish`, { method: "POST", token });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function invite(influencerId: string) {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/invitations`, { method: "POST", token, body: { influencer_id: influencerId } });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const invitedIds = new Set((campaign?.invitations ?? []).map((i) => i.influencer_user_id));
  const invitableFavorites = favorites.filter((f) => !invitedIds.has(f));

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : !campaign ? (
          <p className="muted">{t("campaign.notFound")}</p>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h1 style={{ margin: 0 }}>{campaign.title}</h1>
              <span style={{ fontSize: 12, fontWeight: 600, color: campaign.status === "published" ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                {t(`campaign.status_${campaign.status}`, campaign.status)}
              </span>
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              {campaign.budget_amount ? `${campaign.budget_amount} ${campaign.budget_currency}` : t("campaign.noBudget")}
              {campaign.deadline ? ` - ${campaign.deadline}` : ""}
            </p>
            <ul style={{ paddingLeft: 18, fontSize: 14 }}>
              {campaign.deliverables.map((d, i) => (
                <li key={i}>{d.quantity} x {t(`deliverable.${d.type}`, d.type)} - {d.platform}</li>
              ))}
            </ul>
            {campaign.status !== "published" && (
              <button className="btn btn-teal" disabled={busy} onClick={publish}>{t("campaign.publish")}</button>
            )}

            {campaign.status === "published" && (
              <div className="card" style={{ marginTop: 20 }}>
                <h3 style={{ marginTop: 0 }}>{t("campaign.inviteFromFavorites")}</h3>
                {invitableFavorites.length === 0 ? (
                  <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noFavorites")}</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {invitableFavorites.map((f) => (
                      <div key={f} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 14 }}>{t("discover.creator")} {shortId(f)}</span>
                        <button className="btn btn-ghost" disabled={busy} onClick={() => invite(f)}>{t("campaign.invite")}</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="card" style={{ marginTop: 20 }}>
              <h3 style={{ marginTop: 0 }}>{t("campaign.invitations")} ({campaign.invitations.length})</h3>
              {campaign.invitations.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noInvitations")}</p>
              ) : (
                campaign.invitations.map((inv) => (
                  <div key={inv.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
                    <span>{t("discover.creator")} {shortId(inv.influencer_user_id)}</span>
                    <span className="muted">{inv.status}</span>
                  </div>
                ))
              )}
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0 }}>{t("campaign.proposals")} ({campaign.proposals.length})</h3>
              {campaign.proposals.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noProposals")}</p>
              ) : (
                campaign.proposals.map((p) => (
                  <div key={p.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "6px 0", borderTop: "1px solid var(--line)" }}>
                    <span>{t("discover.creator")} {shortId(p.influencer_user_id)} - v{p.version}</span>
                    <span>{p.rate_amount} {p.rate_currency} - {p.timeline_days}d <span className="muted">({p.status})</span></span>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
