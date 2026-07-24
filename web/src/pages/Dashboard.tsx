import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";

export default function Dashboard() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page">
        <h1>{t("dash.welcome")}</h1>
        <div className="card" style={{ marginTop: 16 }}>
          <p className="muted" style={{ margin: 0 }}>{t("dash.placeholder")}</p>
        </div>
      </div>
    </Layout>
  );
}
