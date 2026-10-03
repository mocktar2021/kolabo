import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Logo } from "./Logo";
import { NotificationsBell } from "./NotificationsBell";
import { api, mediaSrc } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { setStoredLanguage, type AppLanguage } from "../lib/language";
import { useCart } from "../lib/cart";
import { awaitingMyAnswer } from "../lib/disputes";
import { useMe } from "../lib/me";
import type { Dispute, MessageThread } from "../lib/types";

/* The one control that must never end up behind anything: a visitor who
   landed on the French UI by accident has to be able to find EN, and a
   francophone one has to be able to find FR. It is rendered twice below 960 px
   — once inside the collapsible list (hidden there by CSS) and once out in the
   bar — so exactly one copy is ever in the document flow. */
function LanguageSwitch({ className }: { className?: string }) {
  const { i18n } = useTranslation();
  /* THE CHOICE IS WRITTEN DOWN, which the two handlers here used not to do.
     changeLanguage alone lives in one JavaScript heap: the switch worked, and
     then a refresh, a second tab or tomorrow put the reader back into French
     with nothing on screen to say why. The paired write is what makes this a
     setting rather than a filter, and src/i18n.ts reads it back at init. See
     lib/language.ts.

     Doing nothing when the language is already the one asked for keeps a
     second press on the lit button from writing a value that is already
     there, and from making i18next re-render the tree for no change. */
  function choose(lang: AppLanguage) {
    if (i18n.language === lang) return;
    i18n.changeLanguage(lang);
    setStoredLanguage(lang);
  }
  return (
    <div className={className ? `lang-switch ${className}` : "lang-switch"} role="group" aria-label="Language">
      <button className={i18n.language === "fr" ? "active" : ""} onClick={() => choose("fr")}>FR</button>
      <button className={i18n.language === "en" ? "active" : ""} onClick={() => choose("en")}>EN</button>
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
function MarketingNav({ open }: { open: boolean }) {
  const { t } = useTranslation();
  return (
    <div id="primary-nav" className={open ? "nav-links open" : "nav-links"}>
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
   destinations (Découvrir, Briefs or Campagnes, Invitations, Contrats,
   Messages, Litiges) readable at laptop widths instead of wrapping onto a
   second row.

   THE AVATAR IS NOW THE SIGNED-IN USER'S OWN PHOTO, and what changed was the
   API rather than this component's mind. It used to draw the brand gradient
   with a neutral glyph, and that was a decision and not a placeholder: no
   endpoint handed a caller their own avatar without also handing over a whole
   profile, and a third request on every page of the app to decorate a 28 px
   button was a bad trade. GET /auth/me carries display_name and avatar_url
   now, and lib/me.tsx fetches it ONCE PER SESSION rather than once per page —
   keyed on the token, mounted above the router — which is the only reason
   this is worth doing at all. Fetching it here instead would be exactly the
   per-navigation request that was refused.

   THE GRADIENT REMAINS, as the fallback and permanently. A business has a
   company name and no avatar anywhere in this system, and a creator who has
   not uploaded a photo is an ordinary state rather than a failure, so the
   no-image path is the common one and has to look deliberate.

   Closes on an outside click and on Escape, and every entry is a real link or
   button, so the whole menu is reachable and operable from the keyboard
   without a roving-tabindex implementation to get wrong. */
function AccountMenu() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { me, loading } = useMe();
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

  /* The money entry, and it is a different question on each side of the
     market — which is why it is two routes and not one. A creator opens
     /earnings and reads NET figures, because the commission comes off at
     release. A buyer opens /payments and reads GROSS ones, because the
     commission never came out of their payment; their screen also carries a
     refunded column, which is a line that does not exist in a creator's
     ledger at all. Each side is offered the one that will answer it. */
  const items = [
    { to: "/profile", label: t("nav.profile") },
    isBrand
      ? { to: "/payments", label: t("nav.payments") }
      : { to: "/earnings", label: t("nav.earnings") },
    /* The profile is how the market sees you; the account is how you sign
       in. They were the same page until the account settings existed, and
       the delete-account block sitting at the bottom of a profile form was
       the clearest sign they should not be. */
    { to: "/account", label: t("nav.account") }
  ];

  // mediaSrc turns the server path ("/profiles/media/{id}") into an absolute
  // URL against VITE_API_URL, and answers undefined for a null path — so this
  // is also the null test.
  const avatar = mediaSrc(me?.avatar_url);

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
        <span aria-hidden="true" className="menu-dashes">
          <span style={MENU_DASH} />
          <span style={MENU_DASH} />
          <span style={MENU_DASH} />
        </span>
        <span
          aria-hidden="true"
          style={{
            width: 28, height: 28, borderRadius: "50%", flexShrink: 0, overflow: "hidden",
            /* The gradient only paints where there is no photo. Leaving it
               underneath an image would show through while the image loads,
               which reads as a flash rather than as a placeholder. */
            background: avatar ? "var(--surface-2)" : "var(--gradient-brand)", color: "#fff",
            display: "inline-flex", alignItems: "center", justifyContent: "center"
          }}
        >
          {avatar ? (
            <img src={avatar} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8.4" r="3.4" />
              <path d="M4.8 19.4c1.1-3.2 3.9-5 7.2-5s6.1 1.8 7.2 5" />
            </svg>
          )}
        </span>
        {/* The name of the control, shown only where it is needed: below
            960 px this button and the nav toggle end up one under the other,
            both drawn as three dashes, and the second one reads as the first
            one repeated. There the dashes come off this one (see
            .menu-dashes in theme.css) and the label goes on. It is the
            aria-label the button already carried, so there is no new string
            to translate. */}
        <span className="nav-item-label">{t("menu.account")}</span>
      </button>
      {open && (
        <div className="menu-panel menu-panel-end menu-panel-account" role="menu">
          {/* Who is signed in, at the top of the menu that is about them. The
              name only — NOT the email address, which /auth/me does carry and
              which belongs on the account screen where somebody is checking
              which address they sign in with, not under an avatar in a nav
              that is open on a shared screen.

              While the first request is in flight this renders nothing rather
              than the fallback: "Votre compte" appearing for a frame and then
              turning into a name is worse than a beat of empty space. */}
          {!loading && (
            <div style={{ padding: "2px 12px 9px", borderBottom: "1px solid var(--line)", marginBottom: 5 }}>
              <strong style={{
                fontFamily: "var(--font-display)", fontSize: 14.5, display: "block",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
              }}>
                {me?.display_name || t("menu.noName")}
              </strong>
            </div>
          )}
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

function AppNav({ open }: { open: boolean }) {
  const { t } = useTranslation();
  /* The two sides of the market get two different menus, from one question.
     Campaigns are a brand-side artifact: only businesses and agencies can own
     one, so for a creator /campaigns is a page that can never hold anything.
     Invitations run the other way — a business sends them and never receives
     one, so its invitations page would be empty by construction; the answers
     to what it sent arrive as proposals on its own campaign. The open board
     is the same question a third time and the sharpest version of it: GET
     /campaigns/open answers a brand 403, because a brief carries a budget and
     the shape of a competitor's quarter. The cart is the fourth: a creator has
     nothing to put in one and checkout answers them 403. Agencies buy the way
     businesses do, hence isBusinessLike.

     Messages are the exception that proves it: a contract has two parties and
     the thread belongs to both, so that entry is not asked the question at
     all. Disputes are the same exception for the same reason, AND SO ARE
     NOTIFICATIONS — both sides of the market are told about things, and an
     invitation and a proposal are the same event read from two ends.

     What is NOT here any more: the profile, the money screen, the account
     settings and sign out. They live behind the avatar in AccountMenu — they
     are not places somebody goes while working, and as flat buttons they were
     four of the nine that made this row wrap. */
  const isBrand = isBusinessLike(getStoredRole());
  return (
    <div id="primary-nav" className={open ? "nav-links open" : "nav-links"}>
      <LanguageSwitch />
      <Link className="btn btn-ghost" to="/discover">{t("nav.discover")}</Link>
      {!isBrand && <Link className="btn btn-ghost" to="/board">{t("nav.board")}</Link>}
      {isBrand && <Link className="btn btn-ghost" to="/campaigns">{t("nav.campaigns")}</Link>}
      {!isBrand && <Link className="btn btn-ghost" to="/invitations">{t("nav.invitations")}</Link>}
      <Link className="btn btn-ghost" to="/contracts">{t("nav.contracts")}</Link>
      <MessagesIndicator />
      <DisputesIndicator />
      {isBrand && <CartIndicator />}
      {/* An icon rather than a word, and next to the avatar rather than out
          with the destinations: the bell is not a place you go, it is what
          tells you where to go. */}
      <NotificationsBell />
      <AccountMenu />
    </div>
  );
}

/* The header, and the one thing it has to survive: a 320 px phone.

   The row is a flex line that never wrapped, holding items that never shrink
   (.btn sets white-space: nowrap, and a flex item's automatic minimum keeps
   text at its content size). The signed-in French set asks for 760 px of it.
   On a 360 px screen the destinations therefore ran off the right edge and
   were simply unreachable — no scrollbar, no wrap, nothing.

   Below 960 px — the width at which the last of them stops fitting, measured,
   and the breakpoint the nav already used to start shedding links — the list
   collapses behind one control and the language switch stays out in the bar.
   Above 960 px both of those are display:none, so they are not flex items and
   the desktop row is byte-for-byte the row it was.

   What the control OPENS is a column: one destination per row. It used to be
   this same flex line re-flowed, which wrapped onto three lines of pills and
   does not read as a menu — see the nav rules in theme.css. */
export function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  return (
    <>
      <header className="nav">
        <div className="container nav-inner">
          <Link to="/" aria-label="Kolabo home"><Logo /></Link>
          <LanguageSwitch className="lang-switch-bar" />
          <button
            type="button"
            className="btn btn-ghost nav-toggle"
            aria-expanded={navOpen}
            aria-controls="primary-nav"
            aria-label={navOpen ? t("menu.closeNav") : t("menu.openNav")}
            onClick={() => setNavOpen((o) => !o)}
          >
            <span aria-hidden="true" className="menu-dashes">
              <span style={MENU_DASH} />
              <span style={MENU_DASH} />
              <span style={MENU_DASH} />
            </span>
          </button>
          {isAuthenticated ? <AppNav open={navOpen} /> : <MarketingNav open={navOpen} />}
        </div>
      </header>
      {children}
      <SiteFooter />
    </>
  );
}

/* PARENT-COMPANY ATTRIBUTION, and the last thing on every page.

   Kolabo is one of two products built by Mocktar Technologies — Mocktar
   Technologies (Benin) and Mocktar Technologies LLC (North Carolina) —
   FastaNow being the other. The strip states that relationship once, at the
   bottom, in the same muted grey the rest of the footer's small print already
   uses: it is provenance rather than promotion, and it earns none of the
   footer's emphasis.

   PRIVACY LEADS THE ROW, which is what this comment used to say was missing.
   It was absent because the page was: App.tsx declared no route for it, there
   was no catch-all to catch the miss, and a link would have dropped a visitor
   on a blank document — worse than the placeholder PR #131 removed from this
   same footer, because a placeholder at least says something. The page now
   exists at /legal/privacy, unguarded, so a signed-out visitor and an
   app-store reviewer typing the URL cold both reach it.

   TERMS JOIN IT HERE, which is what the previous version of this comment
   said was still missing. /legal/terms now exists, carrying the governing-law
   clause that was blocking it, so the row is what TikTok's developer review
   asks for: a privacy policy and a set of terms, both reachable without
   opening a menu.

   THE LINK AND THE ROUTE SHIP TOGETHER OR NOT AT ALL, for the reason the
   paragraph above gives: do not merge one without the other.

   THE COPY IS STILL A DRAFT AWAITING A LAWYER, AND THE TERMS MORE SO THAN THE
   POLICY. Both were written from what the code actually does rather than from
   a template, but the Terms' governing-law clause rests on counsel's reading
   of party autonomy and of creators being sellers rather than consumers, and
   nothing in this repo settles either. Linking them here does not make them
   approved; see lib/legalStrings.ts.

   Both are <Link>s while Support is a mailto and Mocktar Technologies is an
   external anchor, which is the same distinction the rest of this footer
   makes: inside the app, react-router; outside it, an <a>.

   Support points where support actually happens today: the address the
   Support column above already publishes. Not a help centre that has not been
   built.

   THE LAYOUT IS ONE WRAPPING FLEX LINE with no media query, which is what
   keeps it safe below 400 px. The brand and the links are two groups sharing
   a row for as long as both fit; the links drop to a second row when they do
   not. Nothing in it is nowrap and nothing carries a fixed width, so there is
   no viewport at which this row can demand more than the container gives it —
   which is the property PRs #133 and #142 bought for the header and that this
   must not spend. */

/* A link in the strip. Ink-dark and bold against the muted attribution beside
   it, and 44 px tall because a footer link is still a thumb target. Focus and
   hover are left to the stylesheet: an <a> keeps the browser's focus ring
   (nothing in theme.css clears it) and picks up the global a:hover underline,
   which is exactly what the other links in this footer do.

   600 rather than 700 because index.html loads Inter at 400, 500 and 600 and
   at no other weight: 700 would resolve to the 600 face anyway on a device
   that has the webfont, and to a synthesised faux-bold on one that fell back
   to the system stack — two different renderings of one declaration. */
const PARENT_LINK: React.CSSProperties = {
  display: "inline-flex", alignItems: "center", minHeight: 44,
  fontSize: 13.5, fontWeight: 600, color: "var(--ink)", textDecoration: "none"
};

function ParentCompanyStrip() {
  const { t } = useTranslation();
  return (
    <div
      className="container"
      style={{
        borderTop: "1px solid var(--line)", marginTop: 18, paddingTop: 12, paddingBottom: 12,
        display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between",
        columnGap: 24, rowGap: 6
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        {/* The mark without the wordmark: "Kolabo" is already set in type at
            the top of this footer, and repeating it here would make the strip
            about Kolabo when the sentence beside it is about its publisher. */}
        <span style={{ display: "inline-flex", flexShrink: 0 }}>
          <Logo size={26} withWordmark={false} />
        </span>
        <span style={{ fontSize: 13.5, color: "var(--muted)", minWidth: 0 }}>
          {t("footer.parentProduct")}
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", columnGap: 22 }}>
        <Link to="/legal/privacy" style={PARENT_LINK}>{t("footer.privacy")}</Link>
        <Link to="/legal/terms" style={PARENT_LINK}>{t("footer.terms")}</Link>
        <a href="mailto:hello@kolaboafrica.com" style={PARENT_LINK}>{t("footer.support")}</a>
        {/* The one link in this footer that leaves the product, hence the
            noopener/noreferrer pair on the new tab. The company name is a
            proper noun and is not translated in either bundle. */}
        <a href="https://mocktar.com" target="_blank" rel="noopener noreferrer" style={PARENT_LINK}>
          Mocktar Technologies
        </a>
      </div>
    </div>
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
          {/* The FAQ answers live in the section at the bottom of the
              landing page; there is no FAQ page, and inventing one would mean
              writing content nobody has approved. This pointed at /pricing,
              which answers one of those four questions and none of the other
              three. The anchor is id="faq" in pages/Landing.tsx, and that
              section scrolls itself into view — react-router does not do it
              for a hash on a client-side navigation. */}
          <Link to="/#faq">{t("footer.faq")}</Link>
          <a href="mailto:hello@kolaboafrica.com">{t("footer.contact")}</a>
        </div>
      </div>
      <div className="container" style={{ borderTop: "1px solid var(--line)", paddingTop: 18, marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
        Kolabo. {new Date().getFullYear()}. {t("footer.rights")}
      </div>
      <ParentCompanyStrip />
    </footer>
  );
}
