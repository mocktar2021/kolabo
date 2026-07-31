import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import type { ReferralInfo } from "../lib/types";

function ActionCard({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="card" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
      <strong style={{ fontFamily: "var(--font-display)", fontSize: 17 }}>{title}</strong>
      <p className="muted" style={{ margin: "6px 0 0", fontSize: 14 }}>{desc}</p>
    </Link>
  );
}

/* Creator referral panel. The code is minted lazily by the backend on first
   read; the sharing block mirrors ShareModal's copy pattern and pushes
   WhatsApp first because it is the dominant sharing channel in the pilot
   markets. */
function ReferralPanel({ token }: { token: string | null }) {
  const { t, i18n } = useTranslation();
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [copied, setCopied] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  useEffect(() => {
    // Silent failure by design: referrals are a bonus feature, so if the
    // endpoint errors the panel simply never appears. The dashboard must not
    // show an error state for it.
    api<ReferralInfo>("/auth/me/referral", { token }).then(setInfo).catch(() => undefined);
  }, [token]);

  if (!info) return null;

  const link = `${window.location.origin}/register?ref=${info.code}`;
  const waHref = `https://wa.me/?text=${encodeURIComponent(t("dash.referralInvite", { link }))}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be unavailable (insecure context); the input stays
      // selectable as the fallback.
    }
  }

  return (
    <section className="ref-panel">
      <div className="ref-banner">
        <div>
          <h2>{t("dash.referralTitle")}</h2>
          {/* The rule exactly as the backend applies it: credit is minted on
              the referred account's first completed order, not at signup.
              Promising it earlier would be a promise we break every time. */}
          <p>{t("dash.referralExplain")}</p>
        </div>
        {/* The button reveals the sharing affordances rather than replacing
            them: a raw URL field and a code would otherwise dominate a banner
            whose job is to explain the offer. */}
        <button type="button" className="btn ref-share-btn" aria-expanded={shareOpen}
          onClick={() => setShareOpen((o) => !o)}>
          {t("dash.referralShare")}
        </button>
      </div>

      {shareOpen && (
        <div className="ref-share">
          <div className="ref-code">{info.code}</div>
          <div className="ref-share-row">
            <input className="input" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
            <button className="btn btn-ghost" onClick={copy}>{copied ? t("public.copied") : t("public.copy")}</button>
            <a className="btn btn-teal" href={waHref} target="_blank" rel="noreferrer">{t("dash.referralWhatsapp")}</a>
          </div>
        </div>
      )}

      <div className="ref-tiles">
        <div className="ref-tile">
          <div className="ref-tile-label">{t("dash.referralStatTotal")}</div>
          <div className="ref-tile-value">{info.referred_count}</div>
          <div className="ref-tile-sub">
            {t("dash.referralBreakdown", { c: info.referred_creators, b: info.referred_businesses })}
          </div>
        </div>
        <div className="ref-tile">
          <div className="ref-tile-label">{t("dash.referralStatCredit")}</div>
          <div className="ref-tile-value">
            {info.credit_total} <span className="ref-cur">{info.credit_currency}</span>
          </div>
        </div>
      </div>

      {info.referrals.length === 0 ? (
        <p className="ref-empty muted">{t("dash.referralEmpty")}</p>
      ) : (
        <table className="ref-table">
          <thead>
            <tr>
              <th>{t("dash.referralColDate")}</th>
              <th>{t("dash.referralColType")}</th>
              <th>{t("dash.referralColStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {info.referrals.map((r, i) => (
              <tr key={i}>
                {/* The active language, not the browser's: someone reading the
                    app in French should not get an en-US date beside it. */}
                <td>{new Date(r.joined_at).toLocaleDateString(i18n.language)}</td>
                {/* Agencies buy the way businesses do (isBusinessLike), so both
                    read as "Marque" rather than exposing a third label the
                    referrer has no use for. */}
                <td>{isBusinessLike(r.role) ? t("dash.referralTypeBrand") : t("dash.referralTypeCreator")}</td>
                <td>
                  <span className={`ref-chip ${r.status === "ordered" ? "ok" : ""}`}>
                    {r.status === "ordered" ? t("dash.referralStatusOrdered") : t("dash.referralStatusSignedUp")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const role = getStoredRole();
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page">
        <h1>{t("dash.welcome")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("dash.sub")}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16, marginTop: 18 }}>
          <ActionCard to="/profile" title={t("dash.profileTitle")} desc={t("dash.profileDesc")} />
          <ActionCard to="/discover" title={t("dash.discoverTitle")} desc={t("dash.discoverDesc")} />
          {/* "Créez et gérez vos campagnes" is an authoring promise the API
              will not keep for a creator (403). Campaigns are a brand-side
              artifact; a creator's equivalent is a package on their profile,
              and the briefs aimed at them arrive under Invitations. */}
          {isBusinessLike(role) && <ActionCard to="/campaigns" title={t("dash.campaignTitle")} desc={t("dash.campaignDesc")} />}
          <ActionCard to="/invitations" title={t("dash.invitationsTitle")} desc={t("dash.invitationsDesc")} />
          <ActionCard to="/contracts" title={t("dash.contractsTitle")} desc={t("dash.contractsDesc")} />
        </div>
        {/* Influencers only: businesses and agencies (isBusinessLike) buy, they
            do not recruit fellow creators. Full width under the action cards
            so the panel never competes with them for a grid column. */}
        {role === "influencer" && <ReferralPanel token={token} />}
      </div>
    </Layout>
  );
}
