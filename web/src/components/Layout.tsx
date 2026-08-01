import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Logo } from "./Logo";
import { api } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";
import { awaitingMyAnswer } from "../lib/disputes";
import type { Dispute, MessageThread } from "../lib/types";

function LanguageSwitch() {
  const { i18n } = useTranslation();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      <button className={i18n.language === "fr" ? "active" : ""} onClick={() => i18n.changeLanguage("fr")}>FR</button>
      <button className={i18n.language === "en" ? "active" : ""} onClick={() => i18n.changeLanguage("en")}>EN</button>
    </div>
  );
}

/* Click-toggled dropdown listing what the product does today. Every entry
   links to a live route: payments point at the pricing page where the escrow
   model is explained, and messaging now points at the inbox rather than at
   campaigns, because conversations finally have a screen of their own.
   Nothing here advertises a feature that does not exist yet. */
function FeaturesMenu() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on any click outside the menu. A document listener needs no new
  // dependency and survives clicks on elements that never receive focus.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const items = [
    { to: "/discover", title: t("featuresMenu.searchT"), desc: t("featuresMenu.searchD") },
    { to: "/campaigns", title: t("featuresMenu.campaignsT"), desc: t("featuresMenu.campaignsD") },
    { to: "/contracts", title: t("featuresMenu.contractsT"), desc: t("featuresMenu.contractsD") },
    { to: "/pricing", title: t("featuresMenu.paymentsT"), desc: t("featuresMenu.paymentsD") },
    { to: "/messages", title: t("featuresMenu.messagingT"), desc: t("featuresMenu.messagingD") },
    { to: "/discover", title: t("featuresMenu.reviewsT"), desc: t("featuresMenu.reviewsD") }
  ];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button type="button" className="nav-link" aria-haspopup="true" aria-expanded={open}
        onClick={() => setOpen((o) => !o)}>
        {t("featuresMenu.label")} ▾
      </button>
      {open && (
        <div className="menu-panel" role="menu">
          {items.map((it) => (
            <Link key={it.title} className="menu-item" role="menuitem" to={it.to} onClick={() => setOpen(false)}>
              <span className="t">{it.title}</span>
              <span className="d">{it.desc}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* Two different navigations. Signed out visitors get a marketing menu; the app
   menu only appears once there is an account to use it with. The
   nav-secondary links hide first at laptop widths (see the nav
   responsiveness rules in theme.css); they stay reachable through the
   footer. */
function MarketingNav() {
  const { t } = useTranslation();
  return (
    <div className="nav-links">
      <Link className="nav-link" to="/discover">{t("marketingNav.findCreators")}</Link>
      <FeaturesMenu />
      <Link className="nav-link nav-secondary" to="/for-brands">{t("marketingNav.forBrands")}</Link>
      <Link className="nav-link nav-secondary" to="/for-creators">{t("marketingNav.forCreators")}</Link>
      <Link className="nav-link nav-secondary" to="/pricing">{t("marketingNav.pricing")}</Link>
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/login">{t("nav.login")}</Link>
      <Link className="btn btn-primary" to="/register">{t("nav.signup")}</Link>
    </div>
  );
}

/* The basket, with how much is in it. The count is the only thing worth
   putting in the nav: it is what tells a brand that the four packages they
   collected on four different profiles are still waiting to be ordered, which
   is precisely the thing a cart exists to remember. Zero renders no badge — a
   grey "0" is noise on every page of the app. */
function CartIndicator() {
  const { t } = useTranslation();
  const { count } = useCart();
  return (
    <Link className="btn btn-ghost" to="/cart" aria-label={t("cart.navAria", { n: count })}>
      {t("cart.nav")}
      {count > 0 && (
        <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 7px" }}>
          {count}
        </span>
      )}
    </Link>
  );
}

/* The inbox, with what is waiting in it. Both roles get this one: a contract
   has exactly two parties and either of them may be the one who has not
   replied yet.

   Fetched once when the nav mounts, which is once per navigation, and
   deliberately not polled. There is no websocket here, and a timer in the nav
   would hit /messaging/threads on every screen of the app for as long as the
   tab is open — to shave a few minutes off a badge that the messages page
   itself refreshes the moment somebody opens it. */
function MessagesIndicator() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!token) return;
    let live = true;
    api<MessageThread[]>("/messaging/threads", { token })
      .then((rows) => {
        if (live) setUnread(rows.reduce((total, row) => total + row.unread_count, 0));
      })
      // A nav badge is not worth an error state. Silence leaves the rest of
      // the navigation working.
      .catch(() => undefined);
    return () => { live = false; };
  }, [token]);

  return (
    <Link className="btn btn-ghost" to="/messages" aria-label={t("msg.navAria", { n: unread })}>
      {t("msg.nav")}
      {unread > 0 && (
        <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 7px" }}>
          {unread}
        </span>
      )}
    </Link>
  );
}

/* Disputes, with what is waiting on the CALLER. Both roles, for the reason
   messages are: a dispute is a claim on money held between two people and
   either of them may be the one who has not answered.

   The badge counts the cases awaiting THIS person's answer and not their open
   cases. The 72 h window is the only thing here that expires, it expires
   against the party who did not open the case, and a number that also counted
   the ones they raised themselves would sit there unclearable for as long as
   they waited for a reply — which is exactly when a badge stops being read.

   Fetched once on mount and not polled, like the messages badge and for the
   same reason. */
function DisputesIndicator() {
  const { t } = useTranslation();
  const { token, userId } = useAuth();
  const [waiting, setWaiting] = useState(0);

  useEffect(() => {
    if (!token || !userId) return;
    let live = true;
    api<Dispute[]>("/payments/disputes/mine", { token })
      .then((rows) => {
        if (live) setWaiting(awaitingMyAnswer(rows, userId).length);
      })
      .catch(() => undefined);
    return () => { live = false; };
  }, [token, userId]);

  return (
    <Link className="btn btn-ghost" to="/disputes" aria-label={t("dispute.navAria", { n: waiting })}>
      {t("dispute.nav")}
      {waiting > 0 && (
        <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 7px" }}>
          {waiting}
        </span>
      )}
    </Link>
  );
}

function AppNav() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  /* The two sides of the market get two different menus, from one question.
     Campaigns are a brand-side artifact: only businesses and agencies can own
     one, so for a creator /campaigns is a page that can never hold anything.
     Invitations run the other way — a business sends them and never receives
     one, so its invitations page would be empty by construction; the answers
     to what it sent arrive as proposals on its own campaign. The cart is the
     same question a third time: a creator has nothing to put in one and the
     checkout endpoint answers them 403, so the indicator is hidden rather
     than linking to a page that could only refuse them — which is exactly
     what BrandOnly does for the route itself. Earnings are the same question
     a fourth time: /payments/earnings answers a business empty totals on
     purpose, because what a buyer wants there is spend, which is a different
     question and a view that does not exist yet. Agencies buy the way
     businesses do, hence isBusinessLike.

     Messages are the exception that proves it: a contract has two parties and
     the thread belongs to both, so that entry is not asked the question at
     all. Disputes are the same exception for the same reason, and so is the
     account: every account has a login number and a password whichever side
     of the market it sits on. */
  const isBrand = isBusinessLike(getStoredRole());
  return (
    <div className="nav-links">
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/discover">{t("nav.discover")}</Link>
      {isBrand && <Link className="btn btn-ghost" to="/campaigns">{t("nav.campaigns")}</Link>}
      {!isBrand && <Link className="btn btn-ghost" to="/invitations">{t("nav.invitations")}</Link>}
      <Link className="btn btn-ghost" to="/contracts">{t("nav.contracts")}</Link>
      {!isBrand && <Link className="btn btn-ghost" to="/earnings">{t("nav.earnings")}</Link>}
      <MessagesIndicator />
      <DisputesIndicator />
      {isBrand && <CartIndicator />}
      <Link className="btn btn-ghost" to="/profile">{t("nav.profile")}</Link>
      {/* The profile is how the market sees you; the account is how you sign
          in. They were the same page until the account settings existed, and
          the delete-account block sitting at the bottom of a profile form was
          the clearest sign they should not be. */}
      <Link className="btn btn-ghost" to="/account">{t("nav.account")}</Link>
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
