import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* Placeholder marketing pages so the header links resolve. Real copy replaces
   these as positioning is finalised. */
export default function MarketingPage({ titleKey, bodyKey }: { titleKey: string; bodyKey: string }) {
  const { t } = useTranslation();
  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        <h1>{t(titleKey)}</h1>
        <p className="muted">{t(bodyKey)}</p>
        <div className="card" style={{ marginTop: 18 }}>
          <p style={{ margin: 0 }}>{t("marketingPage.placeholder")}</p>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 20, flexWrap: "wrap" }}>
          <Link className="btn btn-primary" to="/register">{t("nav.signup")}</Link>
          <Link className="btn btn-ghost" to="/discover">{t("marketingNav.findCreators")}</Link>
        </div>
      </div>
    </Layout>
  );
}
