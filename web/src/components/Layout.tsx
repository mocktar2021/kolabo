import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { ReactNode } from "react";
import { Logo } from "./Logo";
import { useAuth } from "../lib/auth";

function LanguageSwitch() {
  const { i18n } = useTranslation();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      <button className={i18n.language === "fr" ? "active" : ""} onClick={() => i18n.changeLanguage("fr")}>FR</button>
      <button className={i18n.language === "en" ? "active" : ""} onClick={() => i18n.changeLanguage("en")}>EN</button>
    </div>
  );
}

/* Two different navigations. Signed out visitors get a marketing menu; the app
   menu only appears once there is an account to use it with. */
function MarketingNav() {
  const { t } = useTranslation();
  return (
    <div className="nav-links">
      <Link className="nav-link" to="/discover">{t("marketingNav.findCreators")}</Link>
      <Link className="nav-link" to="/for-brands">{t("marketingNav.forBrands")}</Link>
      <Link className="nav-link" to="/for-creators">{t("marketingNav.forCreators")}</Link>
      <Link className="nav-link" to="/pricing">{t("marketingNav.pricing")}</Link>
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/login">{t("nav.login")}</Link>
      <Link className="btn btn-primary" to="/register">{t("nav.signup")}</Link>
    </div>
  );
}

function AppNav() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="nav-links">
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/discover">{t("nav.discover")}</Link>
      <Link className="btn btn-ghost" to="/campaigns">{t("nav.campaigns")}</Link>
      <Link className="btn btn-ghost" to="/invitations">{t("nav.invitations")}</Link>
      <Link className="btn btn-ghost" to="/contracts">{t("nav.contracts")}</Link>
      <Link className="btn btn-ghost" to="/profile">{t("nav.profile")}</Link>
      <button className="btn btn-ghost" onClick={() => { logout(); navigate("/"); }}>{t("nav.logout")}</button>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <Link to="/" aria-label="Kolabo home"><Logo /></Link>
          {isAuthenticated ? <AppNav /> : <MarketingNav />}
        </div>
      </header>
      {children}
      <SiteFooter />
    </>
  );
}

function SiteFooter() {
  const { t } = useTranslation();
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <Logo />
          <p className="muted" style={{ fontSize: 13.5, marginTop: 10, maxWidth: 260 }}>{t("footer.tagline")}</p>
        </div>
        <div>
          <h4>{t("footer.discover")}</h4>
          <Link to="/discover">{t("marketingNav.findCreators")}</Link>
          <Link to="/discover?category=fashion">{t("cat.fashion")}</Link>
          <Link to="/discover?category=beauty">{t("cat.beauty")}</Link>
          <Link to="/discover?category=tech">{t("cat.tech")}</Link>
        </div>
        <div>
          <h4>{t("footer.company")}</h4>
          <Link to="/for-brands">{t("marketingNav.forBrands")}</Link>
          <Link to="/for-creators">{t("marketingNav.forCreators")}</Link>
          <Link to="/pricing">{t("marketingNav.pricing")}</Link>
        </div>
        <div>
          <h4>{t("footer.support")}</h4>
          <Link to="/pricing">{t("footer.faq")}</Link>
          <a href="mailto:hello@kolaboafrica.com">{t("footer.contact")}</a>
        </div>
      </div>
      <div className="container" style={{ borderTop: "1px solid var(--line)", paddingTop: 18, marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
        Kolabo. {new Date().getFullYear()}. {t("footer.rights")}
      </div>
    </footer>
  );
}
