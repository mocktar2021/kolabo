import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorCard } from "../components/CreatorCard";
import { api } from "../lib/api";
import { CATEGORIES } from "../lib/categories";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import type { SearchResult } from "../lib/types";

/* The featured grid renders only with at least this many creators. Fewer than
   four and the landing page shows a half-empty shelf: one or two lonely cards
   read as "nobody is here", which is worse than showing nothing at all. The
   same guard keeps our honesty automatic; until enough real profiles are
   seeded and searchable, the section simply stays hidden. */
const MIN_FEATURED_CREATORS = 4;

/* How many workflow tabs the rotation cycles through. Kept as a constant
   rather than read off the tab array, which is rebuilt on every render (and
   swapped wholesale on a language change): the timer only needs to know how
   far to count, so it should not depend on a value that changes identity. */
const WF_TAB_COUNT = 6;

/* How long each workflow tab stays up. The progress hint on the active pill
   mirrors this duration in CSS (.wf-tab-timing::after in theme.css); if one
   moves, the other has to move with it. */
const WF_ROTATE_MS = 5000;

/* Shared attributes for the tool glyphs below: currentColor everywhere so a
   tile's own colour drives the drawing, and aria-hidden because the label
   right underneath already says what the glyph means. */
const GLYPH_PROPS = {
  width: 30,
  height: 30,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": "true"
} as const;

/* The six tools Kolabo replaces, each with a small hand-drawn glyph.
   Deliberately generic shapes rather than the real logos: what is being
   replaced here are habits — a WhatsApp thread, cash handed over, a contract
   printed and signed — more than SaaS products, so a plain chat bubble says
   it better than a brand mark would. Copying those marks would also carry
   trademark exposure for nothing in return. */
const TOOL_TILES = [
  {
    key: "toolsT1",
    /* Chat bubble. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <path d="M4 6.5h16v10h-10l-4 3.5v-3.5H4Z" />
        <path d="M8 10h8M8 13.2h5" />
      </svg>
    )
  },
  {
    key: "toolsT2",
    /* Spreadsheet grid. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
        <path d="M3.5 9.5h17M3.5 14.5h17M9.2 4.5v15M14.8 4.5v15" />
      </svg>
    )
  },
  {
    key: "toolsT3",
    /* Banknote. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <rect x="2.5" y="6.5" width="19" height="11" rx="2" />
        <circle cx="12" cy="12" r="2.6" />
        <path d="M6 10.2v3.6M18 10.2v3.6" />
      </svg>
    )
  },
  {
    key: "toolsT4",
    /* Paper document with a folded corner and written lines. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <path d="M6 3.5h7.6L18.5 8.4V20.5H6Z" />
        <path d="M13.6 3.5v4.9h4.9" />
        <path d="M9 9.2h2.5M9 12.5h6.5M9 15.8h6.5" />
      </svg>
    )
  },
  {
    key: "toolsT5",
    /* Envelope. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <rect x="2.5" y="5.5" width="19" height="13" rx="2" />
        <path d="m3.4 7.2 8.6 6.1 8.6-6.1" />
      </svg>
    )
  },
  {
    key: "toolsT6",
    /* Notebook with a pencil beside it. */
    glyph: (
      <svg {...GLYPH_PROPS}>
        <path d="M7 4h8v16H7z" />
        <path d="M4.5 6.6h2.5M4.5 10h2.5M4.5 13.4h2.5M4.5 16.8h2.5" />
        <path d="m16.4 18.6 3.9-4.4-1.7-1.5-3.9 4.4-.5 2z" />
      </svg>
    )
  }
];

export default function Landing() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { hash } = useLocation();
  const [platform, setPlatform] = useState("");
  const [q, setQ] = useState("");
  const [featured, setFeatured] = useState<SearchResult[]>([]);
  const [wfActive, setWfActive] = useState(0);
  /* True until the visitor clicks a workflow tab; see selectWfTab below. */
  const [wfAuto, setWfAuto] = useState(true);

  useEffect(() => {
    /* /discovery/featured rather than /discovery/search, and the difference is
       the whole point. Search is DETERMINISTIC by design — verified first,
       then biggest audience, then oldest profile — which is exactly right when
       somebody is looking for a creator and exactly wrong when the page is
       looking for somebody to show them. Called with a limit of eight it put
       the same eight faces above the fold on every visit, forever: the
       ninth-ranked creator was invisible to every brand that never scrolled
       and never searched, and the top eight collected every impression the
       platform had to give. On a pilot roster that is not a ranking, it is a
       lottery nobody can re-enter. Same eligibility rule, same card, random
       order, so the roster actually gets seen.

       Silent failure by design: if discovery is down the list stays empty and
       the featured section simply does not render. The landing page must never
       show an error state for an optional proof section. */
    api<SearchResult[]>("/discovery/featured?limit=8").then(setFeatured).catch(() => undefined);
  }, []);

  /* The footer's FAQ link points at "/#faq", and this is the half that makes
     it arrive. The answers live in the section near the bottom of this page
     and there is no FAQ page to send anybody to, so the link is an anchor —
     but react-router does not scroll to a hash on a client-side navigation,
     which would land the visitor at the top of the landing page with the FAQ
     eight sections below the fold. That is the same "nothing happened" the
     wrong link produced, so the section scrolls itself into view.

     prefers-reduced-motion gets an instant jump rather than a smooth one,
     the same guard the workflow rotation below uses: a page that scrolls
     itself for several hundred milliseconds is exactly the unrequested
     movement that setting asks us to stop. */
  useEffect(() => {
    if (hash !== "#faq") return;
    const el = document.getElementById("faq");
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [hash]);

  /* The workflow section walks through its six tabs on its own, so a visitor
     who never clicks still sees that the flow does not stop at discovery.
     Two guards on that:
     - prefers-reduced-motion: a panel that swaps its own contents is exactly
       the unrequested movement that setting asks us to stop, and it can be
       genuinely disorienting, so the timer never starts at all.
     - wfAuto: the first click hands control over for good, so we do not
       fight the visitor for the panel. */
  useEffect(() => {
    if (!wfAuto) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setWfActive((i) => (i + 1) % WF_TAB_COUNT), WF_ROTATE_MS);
    return () => window.clearInterval(id);
  }, [wfAuto]);

  /* A click selects the tab and permanently stops the rotation: once the
     visitor has taken control, yanking the panel away from them five seconds
     into their reading is hostile. There is no path back to auto. */
  function selectWfTab(i: number) {
    setWfActive(i);
    setWfAuto(false);
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (platform) qs.set("platform", platform);
    navigate(`/discover?${qs.toString()}`);
  }

  /* PLACEHOLDER metrics — replace with real numbers before public launch.
     This is the one band allowed to carry made-up numbers, and only with the
     visible "exemples" note right under it. */
  const trustStats = [
    { v: t("landing.tb1v"), l: t("landing.tb1l") },
    { v: t("landing.tb2v"), l: t("landing.tb2l") },
    { v: t("landing.tb3v"), l: t("landing.tb3l") },
    { v: t("landing.tb4v"), l: t("landing.tb4l") }
  ];

  const steps = [
    { t: t("landing.step1t"), d: t("landing.step1d") },
    { t: t("landing.step2t"), d: t("landing.step2d") },
    { t: t("landing.step3t"), d: t("landing.step3d") },
    { t: t("landing.step4t"), d: t("landing.step4d") }
  ];

  /* The market running the other way, for brands: post a brief and let
     creators come to you, instead of contacting them one at a time.

     NOT ONE NUMBER IN THIS COPY, and unlike the trust band above there is no
     "exemples" note to excuse one. We do not know how many creators are on
     the platform, how fast a brief fills, or what a typical application looks
     like — and a marketing figure nobody can stand behind is how a brand
     stops believing the rest of the page. The only digits rendered here are
     the step ordinals .step-grid draws, which are structure and not a claim.

     The copy also has to be honest about the soft filter, because a brand
     that thinks it set a hard one declines off-target applications unread:
     targeting ranks who sees the brief first, it stops nobody applying. */
  const briefSteps = [
    { t: t("landing.brief1t"), d: t("landing.brief1d") },
    { t: t("landing.brief2t"), d: t("landing.brief2d") },
    { t: t("landing.brief3t"), d: t("landing.brief3d") }
  ];

  /* Workflow tabs: one per shipped product area, nothing aspirational. The
     copy lives in marketingStrings.ts; the tab label doubles as the panel
     title. Six entries, matching WF_TAB_COUNT above. */
  const wfTabs = [
    { tab: t("landing.wf1Tab"), d: t("landing.wf1D"), chips: [t("landing.wf1C1"), t("landing.wf1C2"), t("landing.wf1C3")] },
    { tab: t("landing.wf2Tab"), d: t("landing.wf2D"), chips: [t("landing.wf2C1"), t("landing.wf2C2"), t("landing.wf2C3")] },
    { tab: t("landing.wf3Tab"), d: t("landing.wf3D"), chips: [t("landing.wf3C1"), t("landing.wf3C2"), t("landing.wf3C3")] },
    { tab: t("landing.wf4Tab"), d: t("landing.wf4D"), chips: [t("landing.wf4C1"), t("landing.wf4C2"), t("landing.wf4C3")] },
    { tab: t("landing.wf5Tab"), d: t("landing.wf5D"), chips: [t("landing.wf5C1"), t("landing.wf5C2")] },
    { tab: t("landing.wf6Tab"), d: t("landing.wf6D"), chips: [t("landing.wf6C1"), t("landing.wf6C2"), t("landing.wf6C3")] }
  ];
  const wfTints = ["wf-tint-a", "wf-tint-b", "wf-tint-c", "wf-tint-d"];

  /* Illustrative vignettes for the workflow panels: styled divs only, no
     images to load and almost nothing extra to localise. */
  function wfArt(i: number) {
    switch (i) {
      case 0:
        return (
          <div className="mock-card">
            <div className="mock-row">
              <span className="mock-avatar" />
              <span className="mock-lines"><span className="mock-line w-60" /><span className="mock-line w-40" /></span>
              <span className="mock-pill">25 000 XOF</span>
            </div>
            <div className="mock-row">
              <span className="mock-avatar" />
              <span className="mock-lines"><span className="mock-line w-70" /><span className="mock-line w-50" /></span>
              <span className="mock-pill">40 000 XOF</span>
            </div>
            <div className="mock-row">
              <span className="mock-avatar" />
              <span className="mock-lines"><span className="mock-line w-50" /><span className="mock-line w-40" /></span>
              <span className="mock-pill">15 000 XOF</span>
            </div>
          </div>
        );
      case 1:
        return (
          <div className="mock-card">
            <span className="mock-line w-70" style={{ height: 10 }} />
            <div className="mock-chip-row">
              <span className="mock-chip">2 × Reel</span>
              <span className="mock-chip">1 × Story</span>
              <span className="mock-chip">500 000 XOF</span>
            </div>
            <span className="mock-line w-40" />
          </div>
        );
      case 2:
        return (
          <div className="mock-card">
            <span className="mock-line w-80" />
            <span className="mock-line w-60" />
            <div className="mock-sign"><span className="mock-check">✓</span>{t("contract.businessSigned")}</div>
            <div className="mock-sign"><span className="mock-check">✓</span>{t("contract.creatorSigned")}</div>
          </div>
        );
      case 3:
        return (
          <div className="mock-card">
            <div className="mock-kv"><span>{t("contract.escrowStatus")}</span><span className="mock-status held">{t("escrow.status_held")}</span></div>
            <div className="mock-amount">250 000 XOF</div>
            <div className="mock-kv"><span>Mobile Money</span><span className="mock-status released">{t("escrow.status_released")}</span></div>
          </div>
        );
      case 4:
        return (
          <div className="mock-chat">
            <div className="mock-bubble">{t("landing.wfChat1")}</div>
            <div className="mock-bubble me">{t("landing.wfChat2")}</div>
          </div>
        );
      default:
        return (
          <div className="mock-card">
            <div className="mock-stars">★★★★★</div>
            <p className="mock-quote">{t("landing.wfReview")}</p>
            <div className="mock-row">
              <span className="mock-avatar" />
              <span className="mock-lines"><span className="mock-line w-40" /></span>
            </div>
          </div>
        );
    }
  }

  const teams = [
    { t: t("landing.team1t"), d: t("landing.team1d"), b: t("landing.team1b"), to: "/discover", tint: "wf-tint-a" },
    { t: t("landing.team2t"), d: t("landing.team2d"), b: t("landing.team2b"), to: "/register?role=agency", tint: "wf-tint-b" },
    { t: t("landing.team3t"), d: t("landing.team3d"), b: t("landing.team3b"), to: "/discover", tint: "wf-tint-c" },
    { t: t("landing.team4t"), d: t("landing.team4d"), b: t("landing.team4b"), to: "/register", tint: "wf-tint-d" }
  ];

  const faqs = [
    { q: t("landing.faq1q"), a: t("landing.faq1a") },
    { q: t("landing.faq2q"), a: t("landing.faq2a") },
    { q: t("landing.faq3q"), a: t("landing.faq3a") },
    { q: t("landing.faq4q"), a: t("landing.faq4a") }
  ];

  return (
    <Layout>
      <section className="hero-dark">
        <div className="container">
          <h1>
            {t("landing.heroA")} <span className="accent">{t("landing.heroAccent")}</span> {t("landing.heroB")}
          </h1>
          <p className="hero-sub">{t("landing.lead")}</p>

          <form className="search-bar" onSubmit={onSearch}>
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} aria-label={t("landing.platform")}>
              <option value="">{t("landing.allPlatforms")}</option>
              {SOCIAL_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("landing.searchPlaceholder")} />
            <button className="btn btn-primary" type="submit">{t("landing.searchCreators")}</button>
          </form>

          <div className="chip-row">
            {CATEGORIES.slice(0, 8).map((c) => (
              <Link key={c} className="chip" to={`/discover?category=${c}`}>{t(`cat.${c}`)}</Link>
            ))}
          </div>
          <p style={{ textAlign: "center", color: "#8b93a7", fontSize: 13, marginTop: 18 }}>{t("landing.freeToSearch")}</p>
        </div>
      </section>

      {featured.length >= MIN_FEATURED_CREATORS && (
        <section className="container section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <div>
              <h2 style={{ margin: 0 }}>{t("landing.featured")}</h2>
              <p className="section-sub" style={{ margin: 0 }}>{t("landing.featuredSub")}</p>
            </div>
            <Link className="btn btn-ghost" to="/discover">{t("landing.seeAll")}</Link>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 16 }}>
            {featured.map((r) => <CreatorCard key={r.user_id} r={r} />)}
          </div>
        </section>
      )}

      {/* PLACEHOLDER metrics — replace with real numbers before public launch */}
      <section className="container section tb-band">
        {/* The heading is a heading. It used to be a small grey label above
            four large stat cards, which made it read as a caption belonging to
            the numbers rather than as the title of the section — backwards,
            and the only section on the page doing it. The size comes from
            `.section h2` in theme.css, the same rule every other section
            heading here uses, so nothing is invented: the band simply carries
            `.section` (its padding stays `.tb-band`'s either way, that rule
            comes later in the file). Only the centring is local, matching the
            centred grid underneath. */}
        <h2 style={{ textAlign: "center", marginBottom: 26 }}>{t("landing.trustedBy")}</h2>
        <div className="tb-grid">
          {trustStats.map((s) => (
            <div key={s.l} className="tb-cell">
              <div className="tb-value">{s.v}</div>
              <div className="tb-label">{s.l}</div>
            </div>
          ))}
        </div>
        <p className="hint" style={{ textAlign: "center", marginTop: 18 }}>{t("landing.trustedByNote")}</p>
      </section>

      <section className="section" style={{ background: "var(--surface)" }}>
        <div className="container">
          <h2>{t("landing.howItWorks")}</h2>
          <p className="section-sub">{t("landing.howItWorksSub")}</p>
          <div className="step-grid">
            {steps.map((s, i) => (
              <div key={s.t}>
                <span className="step-num">{i + 1}</span>
                <h3 style={{ fontSize: 17 }}>{s.t}</h3>
                <p className="muted" style={{ fontSize: 14.5, margin: 0 }}>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container section">
        <h2>{t("landing.wfTitle")}</h2>
        <p className="section-sub">{t("landing.wfSub")}</p>
        {/* wf-tab-timing draws the progress hint on the active pill while the
            rotation is still running. The class moving to a different button
            on every tick is what restarts the CSS animation, so React never
            has to reset it by hand. */}
        <div className="wf-tabs" role="tablist">
          {wfTabs.map((w, i) => (
            <button
              key={w.tab}
              type="button"
              role="tab"
              aria-selected={i === wfActive}
              className={`wf-tab${i === wfActive ? " active" : ""}${i === wfActive && wfAuto ? " wf-tab-timing" : ""}`}
              onClick={() => selectWfTab(i)}
            >
              {w.tab}
            </button>
          ))}
        </div>
        <div className={`wf-panel ${wfTints[wfActive % wfTints.length]}`}>
          <div>
            <h3>{wfTabs[wfActive].tab}</h3>
            <p className="wf-desc">{wfTabs[wfActive].d}</p>
            <div className="wf-chips">
              {wfTabs[wfActive].chips.map((c) => (
                <span key={c} className="wf-chip"><span className="wf-check" aria-hidden="true">✓</span>{c}</span>
              ))}
            </div>
          </div>
          <div aria-hidden="true">{wfArt(wfActive)}</div>
        </div>
      </section>

      {/* Tool tiles: deliberately generic glyphs rather than third-party
          logos. The tools being replaced here are habits (WhatsApp, cash,
          paper) more than SaaS products, so a drawn chat bubble or banknote
          carries the meaning just as well — and copying brand marks would
          carry trademark exposure for no gain. Shapes live in TOOL_TILES. */}
      <section className="section tools-band">
        <div className="container tools-grid">
          <div>
            <h2>{t("landing.toolsTitle")}</h2>
            <p className="section-sub" style={{ marginBottom: 0 }}>{t("landing.toolsBody")}</p>
          </div>
          <div className="tool-tiles" aria-hidden="true">
            {TOOL_TILES.map((tile) => (
              <span key={tile.key} className="tool-tile">
                {tile.glyph}
                <span className="tool-tile-label">{t(`landing.${tile.key}`)}</span>
              </span>
            ))}
            <span className="tool-tile tool-hub">{t("landing.toolsHub")}</span>
          </div>
        </div>
      </section>

      <section className="time-band">
        <div className="container">
          <p className="time-kicker">{t("landing.timeKicker")}</p>
          <h2><s>{t("landing.timeOld")}</s> <span className="time-arrow">→</span> {t("landing.timeNew")}</h2>
          <p className="time-line">{t("landing.timeLine")}</p>
          <Link className="btn btn-teal btn-lg" to="/register">{t("landing.timeCta")}</Link>
        </div>
      </section>

      <section className="container section">
        <h2>{t("landing.whyKolabo")}</h2>
        <p className="section-sub">{t("landing.whySub")}</p>
        <div className="feature-grid">
          {[
            { t: t("landing.f1t"), d: t("landing.f1d") },
            { t: t("landing.f2t"), d: t("landing.f2d") },
            { t: t("landing.f3t"), d: t("landing.f3d") }
          ].map((f) => (
            <div className="feature" key={f.t}>
              <div className="ic" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6 9 17l-5-5" />
                </svg>
              </div>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* The other direction of the market, for brands: post a brief and let
          creators apply, instead of finding every one of them yourself. Placed
          beside the other brand-facing blocks (it sits directly above "Pour
          les équipes") and built from the same .step-grid the how-it-works
          section uses, so it reads as part of the page rather than as a
          bolted-on announcement. See briefSteps above for why there is not a
          single figure in this copy. */}
      <section className="container section">
        <h2>{t("landing.briefTitle")}</h2>
        <p className="section-sub">{t("landing.briefSub")}</p>
        <div className="step-grid">
          {briefSteps.map((s, i) => (
            <div key={s.t}>
              <span className="step-num">{i + 1}</span>
              <h3 style={{ fontSize: 17 }}>{s.t}</h3>
              <p className="muted" style={{ fontSize: 14.5, margin: 0 }}>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ background: "var(--surface)" }}>
        <div className="container">
          <h2>{t("landing.teamsTitle")}</h2>
          <p className="section-sub">{t("landing.teamsSub")}</p>
          <div className="team-grid">
            {teams.map((c) => (
              <div key={c.t} className={`team-card ${c.tint}`}>
                <h3>{c.t}</h3>
                <p>{c.d}</p>
                <Link className="btn btn-ghost" to={c.to}>{c.b}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container section">
        <h2>{t("landing.testimonials")}</h2>
        <p className="section-sub">{t("landing.testimonialsSub")}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
          {[1, 2, 3].map((n) => (
            <div className="quote-card" key={n}>
              <p>{t(`landing.quote${n}`)}</p>
              <div className="quote-who">
                <span className="quote-avatar" aria-hidden="true" />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{t(`landing.quote${n}Who`)}</div>
                  <div className="muted" style={{ fontSize: 12.5 }}>{t(`landing.quote${n}Role`)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="hint" style={{ marginTop: 14 }}>{t("landing.placeholderNote")}</p>
      </section>

      {/* id="faq" is where the footer's "Questions fréquentes" / "FAQ" link
          lands (SiteFooter in components/Layout.tsx). That link used to point
          at /pricing, which answers one of the four questions below and none
          of the other three. Renaming or removing this id breaks it again. */}
      <section id="faq" className="section" style={{ background: "var(--surface)" }}>
        <div className="container" style={{ maxWidth: 760 }}>
          <h2>{t("landing.faq")}</h2>
          <div style={{ marginTop: 14 }}>
            {faqs.map((f) => (
              <div className="faq-item" key={f.q}>
                <h4>{f.q}</h4>
                <p>{f.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Closing band: one dark door out, with the same two audience cards as
          before — brands go straight to the catalogue, creators to
          registration with the same role hint the old CTA used. */}
      <section className="close-band">
        <div className="container">
          <h2>
            {t("landing.closeA")} <span className="close-accent">{t("landing.closeAccent")}</span>{t("landing.closeB")}
          </h2>
          <p className="close-sub">{t("landing.closeSub")}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18, maxWidth: 760, margin: "0 auto", textAlign: "left" }}>
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ fontSize: 18, color: "var(--ink)", marginBottom: 8 }}>{t("landing.ctaBrandTitle")}</h3>
              <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 18px" }}>{t("landing.ctaBrandSub")}</p>
              <Link className="btn btn-primary" to="/discover">{t("landing.ctaBrandBtn")}</Link>
            </div>
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ fontSize: 18, color: "var(--ink)", marginBottom: 8 }}>{t("landing.ctaCreatorTitle")}</h3>
              <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 18px" }}>{t("landing.ctaCreatorSub")}</p>
              <Link className="btn btn-teal" to="/register?role=influencer">{t("landing.ctaCreatorBtn")}</Link>
            </div>
          </div>
          <div className="close-chips">
            <span className="close-chip">{t("landing.closeChip1")}</span>
            <span className="close-chip">{t("landing.closeChip2")}</span>
            <span className="close-chip">{t("landing.closeChip3")}</span>
          </div>
        </div>
      </section>
    </Layout>
  );
}
