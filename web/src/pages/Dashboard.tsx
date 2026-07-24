import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";

function ActionCard({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="card" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
      <strong style={{ fontFamily: "var(--font-display)", fontSize: 17 }}>{title}</strong>
      <p className="muted" style={{ margin: "6px 0 0", fontSize: 14 }}>{desc}</p>
    </Link>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page">
        <h1>{t("dash.welcome")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("dash.sub")}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16, marginTop: 18 }}>
          <ActionCard to="/profile" title={t("dash.profileTitle")} desc={t("dash.profileDesc")} />
          <ActionCard to="/discover" title={t("dash.discoverTitle")} desc={t("dash.discoverDesc")} />
          <ActionCard to="/campaigns/new" title={t("dash.campaignTitle")} desc={t("dash.campaignDesc")} />
        </div>
      </div>
    </Layout>
  );
}
