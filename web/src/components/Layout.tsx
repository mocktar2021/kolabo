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

/* One of the three dashes on the menu control. A shared object rather than
   three copies of the same six declarations. */
const MENU_DASH: React.CSSProperties = {
  display: "block", width: 15, height: 1.6, borderRadius: 2, background: "var(--ink)"
};

/* The account menu: everything that is about YOU rather than about the work.

   WHY IT EXISTS. The signed-in nav listed every destination as its own
   button — nine of them plus a language switch — and four were not
   destinations somebody navigates to WHILE working: the profile, the money
   screen, the account settings and signing out. They are what you go looking
   for once you have stopped, which is the shape a profile menu has in every
   product that has one. Moving them behind the avatar leaves the live
   destinations (Découvrir, Campagnes or Invitations, Contrats, Messages,
   Litiges) readable at laptop widths instead of wrapping onto a second row.

   THE AVATAR IS A GRADIENT AND NOT A PHOTO, and that is a decision rather
   than a placeholder. Layout mounts on every screen of the app and already
   spends two requests per navigation on the message and dispute badges;
   there is no endpoint that hands a caller their own avatar without also
   handing over a whole profile (and a business has no avatar in this system
   at all — it has a company name). A third request on every page to decorate
   a 28 px button is a bad trade, so the control draws the brand gradient with
   a neutral glyph. The day a cheap /auth/me-style response carries an
   avatar_url, this component is the only thing that changes.

   Closes on an outside click and on Escape, and every entry is a real link or
   button, so the whole menu is reachable and operable from the keyboard
   without a roving-tabindex implementation to get wrong. */
function AccountMenu() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const isBrand = isBusinessLike(getStoredRole());

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      /* Focus goes back to the control that opened the panel. Without it
         Escape leaves a keyboard user at the top of the document with
         nothing selected and no idea where the menu went. */
      triggerRef.current?.focus();
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  /* The money entry is a different question on each side of the market — a
     creator receives net of commission, a buyer pays gross — so the two are
     two screens rather than one. Only the creator's exists so far; the
     buyer's spend screen adds its own entry here when it lands. Offering a
     brand a link now would be a menu item whose only outcome is a redirect
     back to the dashboard, which is what the FeaturesMenu rule above
     forbids: every entry links to a live route. */
  const items = [
    { to: "/profile", label: t("nav.profile") },
    ...(isBrand ? [] : [{ to: "/earnings", label: t("nav.earnings") }]),
    /* The profile is how the market sees you; the account is how you sign
       in. They were the same page until the account settings existed, and
       the delete-account block sitting at the bottom of a profile form was
       the clearest sign they should not be. */
    { to: "/account", label: t("nav.account") }
  ];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        type="button"
        ref={triggerRef}
        className="btn btn-ghost"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("menu.account")}
        onClick={() => setOpen((o) => !o)}
        style={{ display: "inline-flex", alignItems: "center", gap: 9, borderRadius: 999, padding: "3px 4px 3px 12px" }}
      >
        <span aria-hidden="true" style={{ display: "grid", gap: 3.4 }}>
          <span style={MENU_DASH} />
          <span style={MENU_DASH} />
          <span style={MENU_DASH} />
        </span>
        <span
          aria-hidden="true"
          style={{
            width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
            background: "var(--gradient-brand)", color: "#fff",
            display: "inline-flex", alignItems: "center", justifyContent: "center"
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8.4" r="3.4" />
            <path d="M4.8 19.4c1.1-3.2 3.9-5 7.2-5s6.1 1.8 7.2 5" />
          </svg>
        </span>
      </button>
      {open && (
        <div className="menu-panel" role="menu" style={{ left: "auto", right: 0, width: 220 }}>
          {items.map((it) => (
            <Link key={it.to} className="menu-item" role="menuitem" to={it.to} onClick={() => setOpen(false)}>
              <span className="t">{it.label}</span>
            </Link>
          ))}
          <button
            type="button"
            className="menu-item"
            role="menuitem"
            onClick={() => { setOpen(false); logout(); navigate("/"); }}
            style={{ width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer", fontFamily: "var(--font-body)" }}
          >
            <span className="t">{t("nav.logout")}</span>
          </button>
        </div>
      )}
    </div>
  );
}

function AppNav() {
  const { t } = useTranslation();
  /* The two sides of the market get two different menus, from one question.
     Campaigns are a brand-side artifact: only businesses and agencies can own
     one, so for a creator /campaigns is a page that can never hold anything.
     Invitations run the other way — a business sends them and never receives
     one, so its invitations page would be empty by construction; the answers
     to what it sent arrive as proposals on its own campaign. The cart is the
     same question a third time: a creator has nothing to put in one and the
     checkout endpoint answers them 403, so the indicator is hidden rather
     than linking to a page that could only refuse them — which is exactly
     what BrandOnly does for the route itself. Agencies buy the way businesses
     do, hence isBusinessLike.

     Messages are the exception that proves it: a contract has two parties and
     the thread belongs to both, so that entry is not asked the question at
     all. Disputes are the same exception for the same reason.

     What is NOT here any more: the profile, the money screen, the account
     settings and sign out. They live behind the avatar in AccountMenu — they
     are not places somebody goes while working, and as flat buttons they were
     four of the nine that made this row wrap. */
  const isBrand = isBusinessLike(getStoredRole());
  return (
    <div className="nav-links">
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/discover">{t("nav.discover")}</Link>
      {isBrand && <Link className="btn btn-ghost" to="/campaigns">{t("nav.campaigns")}</Link>}
      {!isBrand && <Link className="btn btn-ghost" to="/invitations">{t("nav.invitations")}</Link>}
      <Link className="btn btn-ghost" to="/contracts">{t("nav.contracts")}</Link>
      <MessagesIndicator />
      <DisputesIndicator />
      {isBrand && <CartIndicator />}
      <AccountMenu />
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
