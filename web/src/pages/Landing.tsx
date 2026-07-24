import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { Logo } from "../components/Logo";

function Feature({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="feature">
      <div className="ic" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

export default function Landing() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <Layout>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <span className="eyebrow">{t("landing.eyebrow")}</span>
            <h1>{t("landing.title")}</h1>
            <p className="lead">{t("landing.lead")}</p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-lg" onClick={() => navigate("/register?role=influencer")}>{t("landing.ctaCreator")}</button>
              <button className="btn btn-ghost btn-lg" onClick={() => navigate("/register?role=business")}>{t("landing.ctaBusiness")}</button>
            </div>
          </div>
          <div className="hero-art" aria-hidden="true">
            <Logo size={92} withWordmark={false} />
          </div>
        </div>
      </section>

      <section className="features">
        <div className="container feature-grid">
          <Feature title={t("landing.f1t")} desc={t("landing.f1d")} />
          <Feature title={t("landing.f2t")} desc={t("landing.f2d")} />
          <Feature title={t("landing.f3t")} desc={t("landing.f3d")} />
        </div>
      </section>
    </Layout>
  );
}
