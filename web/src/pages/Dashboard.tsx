import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { getStoredRole, useAuth } from "../lib/auth";

function ActionCard({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="card" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
      <strong style={{ fontFamily: "var(--font-display)", fontSize: 17 }}>{title}</strong>
      <p className="muted" style={{ margin: "6px 0 0", fontSize: 14 }}>{desc}</p>
    </Link>
  );
}

type ReferralInfo = { code: string; referred_count: number };

/* Creator referral card. The code is minted lazily by the backend on first
   read; the card mirrors ShareModal's copy pattern and pushes WhatsApp first
   because it is the dominant sharing channel in the pilot markets. */
function ReferralCard({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Silent failure by design: referrals are a bonus feature, so if the
    // endpoint errors the card simply never appears. The dashboard must not
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
    <div className="card" style={{ marginTop: 24 }}>
      <strong style={{ fontFamily: "var(--font-display)", fontSize: 17 }}>{t("dash.referralTitle")}</strong>
      {/* Rewards are a later business decision; this line is a teaser and
          deliberately promises nothing specific. */}
      <p className="muted" style={{ margin: "6px 0 14px", fontSize: 14 }}>{t("dash.referralExplain")}</p>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 700, letterSpacing: "0.08em" }}>{info.code}</div>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <input className="input" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
        <button className="btn btn-ghost" onClick={copy}>{copied ? t("public.copied") : t("public.copy")}</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 14, flexWrap: "wrap" }}>
        <a className="btn btn-teal" href={waHref} target="_blank" rel="noreferrer">{t("dash.referralWhatsapp")}</a>
        <span className="muted" style={{ fontSize: 13.5 }}>{t("dash.referralCount", { n: info.referred_count })}</span>
      </div>
    </div>
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
          <ActionCard to="/campaigns" title={t("dash.campaignTitle")} desc={t("dash.campaignDesc")} />
          <ActionCard to="/invitations" title={t("dash.invitationsTitle")} desc={t("dash.invitationsDesc")} />
          <ActionCard to="/contracts" title={t("dash.contractsTitle")} desc={t("dash.contractsDesc")} />
        </div>
        {/* Influencers only: businesses and agencies (isBusinessLike) buy, they
            do not recruit fellow creators. */}
        {role === "influencer" && <ReferralCard token={token} />}
      </div>
    </Layout>
  );
}
