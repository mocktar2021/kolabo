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

export function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <Link to="/" aria-label="Kolabo home"><Logo /></Link>
          <div className="nav-links">
            <LanguageSwitch />
            {isAuthenticated ? (
              <>
                <Link className="btn btn-ghost" to="/dashboard">{t("nav.dashboard")}</Link>
                <button className="btn btn-ghost" onClick={() => { logout(); navigate("/"); }}>{t("nav.logout")}</button>
              </>
            ) : (
              <>
                <Link className="btn btn-ghost" to="/login">{t("nav.login")}</Link>
                <Link className="btn btn-primary" to="/register">{t("nav.signup")}</Link>
              </>
            )}
          </div>
        </div>
      </header>
      {children}
      <footer className="footer">
        <div className="container">Kolabo. {new Date().getFullYear()}.</div>
      </footer>
    </>
  );
}
