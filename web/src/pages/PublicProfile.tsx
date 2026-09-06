import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ShareModal } from "../components/ShareModal";
import { api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { useCart } from "../lib/cart";
import { deliverablesFor, PLATFORM_LABELS } from "../lib/platforms";
import { minPrice } from "../lib/pricing";
import type { CreatorIdentity, DirectOrder, Package, PublicProfile } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py, so the
   limit is hit as a full textarea rather than as a 422 after the buyer has
   finished typing. */
const NOTE_MAX_LENGTH = 2000;

/* Quantities a negotiated offer can be built from. The API allows up to 100
   (campaigns.negotiated.MAX_OFFER_QUANTITY) and this stops at 20 on purpose:
   a select with a hundred rows is not a control anybody uses, and past twenty
   deliverables the buyer is writing a campaign brief — which is the other
   product, still one click away and better suited to it. */
const QUANTITY_OPTIONS = Array.from({ length: 20 }, (_, i) => i + 1);

/* Collabstr-style marketplace page: proof on the left (gallery, packages,
   audience, reviews, FAQ), a sticky order card on the right so the price and
   the escrow pitch never leave the screen. */
export default function PublicProfilePage() {
  const { t, i18n } = useTranslation();
  const { userId } = useParams();
  const { token, isAuthenticated } = useAuth();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Buyer-facing interactions.
  const [platformFilter, setPlatformFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedDesc, setExpandedDesc] = useState<Set<string>>(new Set());
  const [audienceTab, setAudienceTab] = useState<string | null>(null);
  const [openFaq, setOpenFaq] = useState<Set<string>>(new Set());
  const [howOpen, setHowOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  /* Ordering. The confirm panel lives inside the card rather than in a modal:
     the card is already the decision point — price, package picker and the
     escrow explainer are all here — and covering it with a dialog would hide
     the very things the buyer is confirming. orderedCampaignId doubles as the
     success flag and as the destination. */
  const [orderOpen, setOrderOpen] = useState(false);
  const [orderNote, setOrderNote] = useState("");
  const [orderBusy, setOrderBusy] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [orderedCampaignId, setOrderedCampaignId] = useState<string | null>(null);

  /* The basket, and the one line of feedback that adding to it produces.

     The immediate-order path below is left exactly as it was, on purpose: a
     brand buying one package from one creator should not have to visit a cart
     to do it. Making them would put a screen in the middle of the shortest
     journey on the site, to solve a problem that journey does not have. The
     cart is for the other case — four packages from three people, decided
     across four profiles and paid for once. */
  const { add: addToCart, count: cartCount } = useCart();
  const [cartMessage, setCartMessage] = useState<string | null>(null);

  /* Negotiating. A second panel in the same card, mutually exclusive with the
     confirm panel, which is why note, busy and error are shared rather than
     duplicated: only one of the two can be open, and a buyer who typed a note
     into one and switched should not have to type it again.

     Only the terms live in their own state, because only the terms are new —
     everything downstream (the 48 h window, the accept path, the contract,
     escrow) is the same object a package order produces. */
  const [negotiateOpen, setNegotiateOpen] = useState(false);
  const [negPlatform, setNegPlatform] = useState("");
  const [negDeliverable, setNegDeliverable] = useState("");
  const [negQuantity, setNegQuantity] = useState(1);
  const [negRate, setNegRate] = useState("");
  const [negCurrency, setNegCurrency] = useState(CURRENCIES[0]);
  const [negDays, setNegDays] = useState("");

  const lang = i18n.language.startsWith("en") ? "en" : "fr";
  const locale = lang === "fr" ? "fr-FR" : "en-US";

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    // The backend resolves the bio for the viewer's language, so the fetch
    // follows the language toggle.
    api<PublicProfile>(`/profiles/influencer/${userId}/public?language=${lang}`)
      .then((p) => {
        setProfile(p);
        setSelectedId((prev) => prev ?? p.packages.find((x) => x.is_active)?.id ?? null);
      })
      .catch((e) => setError(errorText(e, t)))
      .finally(() => setLoading(false));
  }, [userId, lang, t]);

  const packages = profile?.packages.filter((p) => p.is_active) ?? [];
  const packagePlatforms = [...new Set(packages.map((p) => p.platform))];
  const visiblePackages = platformFilter ? packages.filter((p) => p.platform === platformFilter) : packages;
  const selectedPackage = packages.find((p) => p.id === selectedId) ?? packages[0] ?? null;

  /* What this creator can actually be asked for. Their published packages
     first, then every connected account: somebody with a TikTok account and
     no TikTok package still sells TikTok, they simply never listed a bundle
     for it, and refusing to offer it would send that deal off-platform for
     no reason. Filtered against the shared catalog so the two selects can
     never build a pair the API answers 400 to. */
  const sellablePlatforms = [
    ...new Set([...packagePlatforms, ...(profile?.social_accounts ?? []).map((a) => a.platform)])
  ].filter((id) => deliverablesFor(id).length > 0);

  /* Only the buying side of the market may order, the same rule the API
     applies (POST /campaigns/orders answers 403 to an influencer). Agencies
     buy on behalf of brands, hence isBusinessLike rather than a comparison
     against "business". A signed-out visitor is not refused — they are simply
     not a buyer yet, so they get the way to become one. */
  const canOrder = isAuthenticated && isBusinessLike(getStoredRole());

  const audienceAccounts = profile?.social_accounts.filter((a) => a.follower_count !== null) ?? [];
  const audienceAccount = audienceAccounts.find((a) => a.id === audienceTab) ?? audienceAccounts[0] ?? null;

  const faqEntries = profile
    ? [
        { key: "audience", question: t("profile.faqAudience"), answer: profile.faq?.audience },
        { key: "brands", question: t("profile.faqBrands"), answer: profile.faq?.brands }
      ].filter((f) => f.answer)
    : [];

  const compact = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });
  const price = (p: Package) => `${p.price_amount.toLocaleString(locale)} ${p.currency}`;
  const platformLabel = (id: string) => PLATFORM_LABELS[id] ?? id;

  /* Placing the order. Nothing is charged here and the copy above the button
     says so: the creator has 48 h to accept, and escrow is funded only after
     they do — which is exactly why a decline costs the buyer nothing.

     A direct order is also a private transaction, not a public brief: it goes
     to this one creator, nobody else can see it and nobody else can bid on
     it. The success state therefore points at the order itself rather than at
     any listing. */
  async function placeOrder() {
    if (!selectedPackage) return;
    setOrderBusy(true);
    setOrderError(null);
    try {
      // Omitted entirely when empty, like every other optional note in the
      // app: a buyer who wants to send the bare package still can.
      const trimmed = orderNote.trim();
      const res = await api<DirectOrder>("/campaigns/orders", {
        method: "POST",
        token,
        body: { package_id: selectedPackage.id, ...(trimmed ? { note: trimmed } : {}) }
      });
      setOrderedCampaignId(res.campaign_id);
      setOrderOpen(false);
    } catch (e) {
      // Every refusal here — ordering your own package, a package that was
      // deactivated, a creator trying to buy — arrives with a code, and
      // errorText turns that code into the sentence for the reader's
      // language. Shown inline, rather than replaced by a generic failure
      // line.
      setOrderError(errorText(e, t));
    } finally {
      setOrderBusy(false);
    }
  }

  /* How this creator has to be named on a basket line.

     The cart groups by creator and renders each pile with CreatorChip, the
     same component every other list a brand reads uses. The cart page has no
     way to look anybody up — there is no "who is this user id" endpoint and
     there should not be one — so the four identity fields are captured here,
     on the one screen that already has them on display.

     top_platform is the single biggest connected account and never a sum
     across them: somebody following on two networks would otherwise be
     counted twice. Same rule app/core/identity.py applies server-side, so a
     creator reads the same size in the basket as on their proposal. */
  function cartIdentity(p: PublicProfile): CreatorIdentity {
    const top = p.social_accounts
      .filter((a) => a.follower_count !== null)
      .sort((a, b) => (b.follower_count ?? 0) - (a.follower_count ?? 0))[0];
    return {
      display_name: p.display_name,
      avatar_url: p.avatar_url,
      top_platform: top ? top.platform : null,
      top_follower_count: top ? top.follower_count : null
    };
  }

  /* The package as listed, put aside instead of ordered now. Nothing is sent:
     the basket is the client's until checkout, and the price stored on the
     line is only what to show — the order is priced from the live package row
     when the cart is checked out. */
  function addPackageToCart() {
    if (!profile || !selectedPackage) return;
    const trimmed = orderNote.trim();
    const added = addToCart({
      creator_user_id: profile.user_id,
      creator: cartIdentity(profile),
      note: trimmed || null,
      label: selectedPackage.title,
      package_id: selectedPackage.id,
      platform: selectedPackage.platform,
      deliverable_type: selectedPackage.deliverable_type,
      quantity: selectedPackage.quantity ?? 1,
      // A package carries the creator's own timeline; the buyer never names
      // one, so there is nothing to put here.
      timeline_days: null,
      amount: selectedPackage.price_amount,
      currency: selectedPackage.currency
    });
    setCartMessage(added ? t("cart.added") : t("cart.full"));
  }

  /* The buyer's own terms, added to the basket rather than ordered
     immediately. The terms are NOT validated here beyond "all four boxes are
     filled": the floor price, the quantity range, the timeline range and the
     platform/deliverable pair are all checked at checkout, and the answer
     comes back naming the line and the rule in campaigns/negotiated.py's own
     words. Re-stating any of it here would be a second copy of those rules,
     and the copy is the one that drifts. */
  function addNegotiatedToCart() {
    if (!profile) return;
    const trimmed = orderNote.trim();
    const added = addToCart({
      creator_user_id: profile.user_id,
      creator: cartIdentity(profile),
      note: trimmed || null,
      label: t(`deliverable.${negDeliverable}`, negDeliverable),
      package_id: null,
      platform: negPlatform,
      deliverable_type: negDeliverable,
      quantity: negQuantity,
      timeline_days: Number(negDays),
      amount: Number(negRate),
      currency: negCurrency
    });
    if (added) {
      setNegotiateOpen(false);
      setOrderNote("");
    }
    setCartMessage(added ? t("cart.added") : t("cart.full"));
  }

  /* Opening the negotiation panel seeded from the package on screen rather
     than blank: the buyer got here by looking at that offer, and the thing
     they want to change is usually one field of it. */
  function openNegotiate() {
    const platform = selectedPackage?.platform ?? sellablePlatforms[0] ?? "";
    setNegPlatform(platform);
    setNegDeliverable(
      selectedPackage && selectedPackage.platform === platform
        ? selectedPackage.deliverable_type
        : deliverablesFor(platform)[0] ?? ""
    );
    setNegQuantity(1);
    setNegRate("");
    setNegCurrency(selectedPackage?.currency ?? CURRENCIES[0]);
    setNegDays("");
    setOrderError(null);
    setCartMessage(null);
    setNegotiateOpen(true);
  }

  /* The deliverable list is per-platform, so a platform change has to reset
     it. Left alone, "Reel" would survive a switch to LinkedIn and the offer
     would be rejected for a pair the form itself built. */
  function changeNegPlatform(platform: string) {
    setNegPlatform(platform);
    setNegDeliverable(deliverablesFor(platform)[0] ?? "");
  }

  /* The buyer's own terms, sent as the custom form of the same endpoint. What
     comes back is the same order a package produces — same 48 h clock, same
     accept path, same contract — so the success state below is shared rather
     than written twice. */
  async function placeNegotiatedOrder() {
    if (!profile) return;
    setOrderBusy(true);
    setOrderError(null);
    try {
      const trimmed = orderNote.trim();
      const res = await api<DirectOrder>("/campaigns/orders", {
        method: "POST",
        token,
        body: {
          creator_user_id: profile.user_id,
          platform: negPlatform,
          deliverable_type: negDeliverable,
          quantity: negQuantity,
          rate_amount: Number(negRate),
          currency: negCurrency,
          timeline_days: Number(negDays),
          ...(trimmed ? { note: trimmed } : {})
        }
      });
      setOrderedCampaignId(res.campaign_id);
      setNegotiateOpen(false);
    } catch (e) {
      /* Resolved from the refusal's code, never restated here.
         campaigns/negotiated.py still decides what is wrong and what is
         allowed — the deliverable that does not exist on that platform, the
         floor for this currency, the range a quantity or a timeline has to
         sit in — and errorText turns the code it sends into the sentence
         for the reader's language. Restating any of it here would be a
         second copy of those rules, and the copy is the one that drifts. */
      setOrderError(errorText(e, t));
    } finally {
      setOrderBusy(false);
    }
  }

  /* The ×N and duration chips shown on package rows and the order card. Both
     fields are optional server-side: quantity 1 stays silent, and duration
     only renders when value and unit arrived together. */
  const pkgChips = (p: Package) => {
    const chips: string[] = [];
    if ((p.quantity ?? 1) > 1) chips.push(t("pkg.qty", { n: p.quantity }));
    if (p.duration_value != null && p.duration_unit) chips.push(t(`pkg.duration_${p.duration_unit}`, { n: p.duration_value }));
    if (chips.length === 0) return null;
    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
        {chips.map((c) => (
          <span key={c} className="pp-chip" style={{ fontSize: 12, padding: "3px 10px" }}>{c}</span>
        ))}
      </div>
    );
  };

  /* Verified accounts get a quiet checkmark; pending ones simply show none:
     the absence of the checkmark is the signal. A loud "unverified" label
     would punish every pilot creator while OAuth verification does not exist
     yet. */
  const verifiedMark = (status: string) =>
    status === "verified" ? (
      <span title={t("public.verifiedAccount")} style={{ color: "var(--success)", marginRight: 4 }}>✓</span>
    ) : null;

  const toggleDesc = (id: string) =>
    setExpandedDesc((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  const toggleFaq = (key: string) =>
    setOpenFaq((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });

  return (
    <Layout>
      <div className="container page">
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : error || !profile ? (
          <p className="muted">{t("public.notFound")}</p>
        ) : (
          <>
          <div className="pp-grid">
            <div>
              {/* Banner gallery: the first three portfolio images. No lightbox
                  in this pass; the overlay button just jumps to the full grid. */}
              {profile.portfolio.length > 0 && (
                <div className="pp-banner" style={{ gridTemplateColumns: `repeat(${Math.min(profile.portfolio.length, 3)}, 1fr)` }}>
                  {profile.portfolio.slice(0, 3).map((p) => (
                    <img key={p.id} src={mediaSrc(p.url)} alt="" />
                  ))}
                  {profile.portfolio.length > 3 && (
                    <button type="button" className="pp-banner-all"
                      onClick={() => document.getElementById("portfolio")?.scrollIntoView({ behavior: "smooth" })}>
                      {t("public.allPhotos")}
                    </button>
                  )}
                </div>
              )}

              <div className="pp-head">
                <div className="pp-avatar">
                  {profile.avatar_url && <img src={mediaSrc(profile.avatar_url)} alt="" />}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <h1 style={{ margin: 0 }}>{profile.display_name || t("discover.creator")}</h1>
                    {profile.review_count > 0 && (
                      <a className="pp-rating" href="#reviews">
                        <span className="star">★</span> {profile.average_stars} · {t("public.reviewCount", { count: profile.review_count })}
                      </a>
                    )}
                  </div>
                  {profile.headline && <p className="muted" style={{ margin: "4px 0 0" }}>{profile.headline}</p>}
                  {profile.location && <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{profile.location}</div>}
                </div>
                <button className="btn btn-ghost" style={{ marginLeft: "auto" }} onClick={() => setShareOpen(true)}>{t("public.share")}</button>
              </div>

              {profile.social_accounts.length > 0 && (
                <div className="pp-chips">
                  {profile.social_accounts.map((a) => (
                    <span key={a.id} className="pp-chip">
                      {verifiedMark(a.status)}
                      {platformLabel(a.platform)}
                      {a.follower_count !== null && ` · ${compact.format(a.follower_count)}`}
                    </span>
                  ))}
                </div>
              )}

              {profile.bio && <p style={{ marginTop: 16 }}>{profile.bio}</p>}

              <section className="pp-section" id="packages">
                <h2>{t("public.packages")}</h2>
                {packages.length === 0 ? (
                  <p className="muted" style={{ fontSize: 14 }}>{t("public.noPackages")}</p>
                ) : (
                  <>
                    <div className="pp-tabs">
                      <button type="button" className={`pp-tab${platformFilter === "" ? " active" : ""}`}
                        aria-pressed={platformFilter === ""} onClick={() => setPlatformFilter("")}>
                        {t("public.filterAll")}
                      </button>
                      {packagePlatforms.map((pl) => (
                        <button key={pl} type="button" className={`pp-tab${platformFilter === pl ? " active" : ""}`}
                          aria-pressed={platformFilter === pl} onClick={() => setPlatformFilter(pl)}>
                          {platformLabel(pl)}
                        </button>
                      ))}
                    </div>
                    <div style={{ display: "grid", gap: 10 }} role="radiogroup" aria-label={t("public.choosePackage")}>
                      {visiblePackages.map((p) => {
                        const isSelected = selectedPackage?.id === p.id;
                        const isExpanded = expandedDesc.has(p.id);
                        return (
                          <div key={p.id} className={`pp-pkg${isSelected ? " selected" : ""}`} onClick={() => setSelectedId(p.id)}>
                            <input type="radio" name="package" checked={isSelected} onChange={() => setSelectedId(p.id)} aria-label={p.title} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <strong style={{ fontFamily: "var(--font-display)", fontSize: 15.5 }}>{p.title}</strong>
                              <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
                                {platformLabel(p.platform)} · {t(`deliverable.${p.deliverable_type}`, p.deliverable_type)}
                              </div>
                              {pkgChips(p)}
                              {p.description && (
                                <>
                                  <p className={isExpanded ? "" : "clamp-2"} style={{ fontSize: 13.5, margin: "8px 0 0" }}>{p.description}</p>
                                  {p.description.length > 120 && (
                                    <button type="button" className="pp-see-more"
                                      onClick={(e) => { e.stopPropagation(); toggleDesc(p.id); }}>
                                      {isExpanded ? t("public.seeLess") : t("public.seeMore")}
                                    </button>
                                  )}
                                </>
                              )}
                            </div>
                            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, whiteSpace: "nowrap" }}>{price(p)}</div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
              </section>

              {/* Real, connected data only: no self-reported demographics. A
                  buyer must never see a figure the platform cannot back, per
                  product decision. Pending accounts appear too, without the
                  checkmark. */}
              {audienceAccounts.length > 0 && (
                <section className="pp-section" id="analytics">
                  <h2>{t("public.audienceTitle")}</h2>
                  <div className="pp-tabs">
                    {audienceAccounts.map((a) => (
                      <button key={a.id} type="button" className={`pp-tab${audienceAccount?.id === a.id ? " active" : ""}`}
                        aria-pressed={audienceAccount?.id === a.id} onClick={() => setAudienceTab(a.id)}>
                        {a.status === "verified" && <span title={t("public.verifiedAccount")} style={{ marginRight: 4 }}>✓</span>}
                        {platformLabel(a.platform)}
                      </button>
                    ))}
                  </div>
                  {audienceAccount && (
                    <>
                      <div className="pp-big-number">{(audienceAccount.follower_count ?? 0).toLocaleString(locale)}</div>
                      <div className="muted" style={{ fontSize: 14 }}>{t("public.audienceUnit")}</div>
                      <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>{t("public.audienceNote")}</p>
                    </>
                  )}
                </section>
              )}

              {profile.portfolio.length > 0 && (
                <section className="pp-section" id="portfolio">
                  <h2>{t("public.portfolio")}</h2>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                    {profile.portfolio.map((p) => (
                      <img key={p.id} src={mediaSrc(p.url)} alt="" style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", borderRadius: 10, border: "1px solid var(--line)" }} />
                    ))}
                  </div>
                </section>
              )}

              {profile.reviews.length > 0 && (
                <section className="pp-section" id="reviews">
                  <h2>{t("public.reviewsTitle")}</h2>
                  <div style={{ fontSize: 14.5, marginBottom: 6 }}>
                    <span className="pp-stars">★</span> <strong>{profile.average_stars}</strong> · {t("public.reviewCount", { count: profile.review_count })}
                  </div>
                  {profile.reviews.map((r, i) => (
                    <div key={i} className="pp-review">
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <div>
                          <span className="pp-stars" aria-label={`${r.stars}/5`}>{"★".repeat(r.stars)}</span>
                          <strong style={{ marginLeft: 8, fontSize: 14 }}>{r.reviewer_display_name || t("public.verifiedClient")}</strong>
                        </div>
                        <span className="muted" style={{ fontSize: 13 }}>
                          {new Date(r.created_at).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}
                        </span>
                      </div>
                      {r.comment && <p style={{ fontSize: 14, margin: "6px 0 0" }}>{r.comment}</p>}
                    </div>
                  ))}
                </section>
              )}

              {faqEntries.length > 0 && (
                <section className="pp-section">
                  <h2>{t("profile.faqTitle")}</h2>
                  {faqEntries.map((f) => (
                    <div key={f.key} className="pp-faq-item">
                      <button type="button" className="pp-faq-q" aria-expanded={openFaq.has(f.key)} onClick={() => toggleFaq(f.key)}>
                        {f.question}
                        <span className={`pp-chevron${openFaq.has(f.key) ? " open" : ""}`} aria-hidden="true">▾</span>
                      </button>
                      {openFaq.has(f.key) && <p className="pp-faq-a">{f.answer}</p>}
                    </div>
                  ))}
                </section>
              )}

              {profile.categories.length > 0 && (
                <section className="pp-section">
                  <h2>{t("public.relatedCategories")}</h2>
                  <div className="pp-chips" style={{ marginTop: 0 }}>
                    {profile.categories.map((c) => (
                      <Link key={c} className="pp-chip" to={`/discover?category=${c}`}>{t(`cat.${c}`, c)}</Link>
                    ))}
                  </div>
                </section>
              )}
            </div>

            <aside className="pp-rail">
              <div className="card" style={{ padding: 22 }}>
                {selectedPackage ? (
                  <>
                    <div className="pp-order-price">{price(selectedPackage)}</div>
                    <select className="select" style={{ marginTop: 12 }} aria-label={t("public.choosePackage")}
                      value={selectedPackage.id} onChange={(e) => setSelectedId(e.target.value)}>
                      {packages.map((p) => (
                        <option key={p.id} value={p.id}>{p.quantity ?? 1} × {p.title} · {price(p)}</option>
                      ))}
                    </select>
                    {pkgChips(selectedPackage)}
                    {selectedPackage.description && <p className="pp-order-desc">{selectedPackage.description}</p>}

                    {orderedCampaignId ? (
                      /* Inline success rather than a redirect: the buyer just
                         acted on this card and losing the page would cost them
                         the context of what they ordered. The link goes to the
                         order's campaign, which is where a direct order lives
                         until the creator answers — there is no contract to
                         link to yet, and the contracts list would be empty.
                         Shared by both forms of order, because from here on
                         there is only one kind of thing. */
                      <div className="alert alert-success" style={{ marginTop: 14, marginBottom: 0 }}>
                        <div>{t("public.orderSent")}</div>
                        <Link to={`/campaigns/${orderedCampaignId}`} style={{ fontWeight: 600 }}>{t("public.orderView")}</Link>
                      </div>
                    ) : !isAuthenticated ? (
                      /* A visitor is not refused, they are routed: the button
                         becomes the way to become a buyer, pre-selecting the
                         brand role so they do not land as a creator and find
                         the same button disabled a minute later. */
                      <Link className="btn btn-primary btn-block" style={{ marginTop: 14 }} to="/register?role=business">
                        {t("public.orderSignedOut")}
                      </Link>
                    ) : !canOrder ? (
                      /* A creator looking at another creator. Disabled with the
                         reason spelled out, because a button that silently
                         does nothing reads as a bug — and the API would answer
                         403 anyway. The cart is not offered here either: it is
                         the same rule one step earlier. */
                      <>
                        <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} disabled>
                          {t("public.order")}
                        </button>
                        <p className="muted" style={{ fontSize: 13, margin: "8px 0 0" }}>{t("public.orderBrandsOnly")}</p>
                      </>
                    ) : orderOpen ? (
                      <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                        <span className="label">{t("public.orderConfirm")}</span>
                        <strong style={{ fontFamily: "var(--font-display)", fontSize: 15.5, display: "block" }}>
                          {selectedPackage.title}
                        </strong>
                        {pkgChips(selectedPackage)}
                        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 18, marginTop: 8 }}>
                          {price(selectedPackage)}
                        </div>

                        <label className="label" style={{ marginTop: 12 }} htmlFor="order-note">{t("public.orderNote")}</label>
                        <textarea id="order-note" className="input" rows={3} maxLength={NOTE_MAX_LENGTH}
                          style={{ resize: "vertical" }} value={orderNote} onChange={(e) => setOrderNote(e.target.value)} />

                        {/* The one rule that decides whether this is safe to
                            click, said before the button and not after it. */}
                        <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>{t("public.orderRule")}</p>

                        {orderError && <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{orderError}</div>}

                        <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} disabled={orderBusy} onClick={placeOrder}>
                          {t("public.orderSend")}
                        </button>
                        <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }} disabled={orderBusy}
                          onClick={() => { setOrderOpen(false); setOrderError(null); }}>
                          {t("public.orderCancel")}
                        </button>
                      </div>
                    ) : negotiateOpen ? (
                      /* The second panel in the same card. Everything a
                         package would have decided, decided by the buyer —
                         and nothing more: the 48 h rule, the note and the
                         success state are the package order's, because the
                         thing this produces IS a package order's twin. */
                      <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                        <span className="label">{t("public.negotiateTitle")}</span>

                        <label className="label" style={{ marginTop: 10 }} htmlFor="neg-platform">{t("public.negotiatePlatform")}</label>
                        <select id="neg-platform" className="select" value={negPlatform}
                          onChange={(e) => changeNegPlatform(e.target.value)}>
                          {sellablePlatforms.map((p) => <option key={p} value={p}>{platformLabel(p)}</option>)}
                        </select>

                        <label className="label" style={{ marginTop: 10 }} htmlFor="neg-deliverable">{t("public.negotiateDeliverable")}</label>
                        <select id="neg-deliverable" className="select" value={negDeliverable}
                          onChange={(e) => setNegDeliverable(e.target.value)}>
                          {deliverablesFor(negPlatform).map((d) => (
                            <option key={d} value={d}>{t(`deliverable.${d}`, d)}</option>
                          ))}
                        </select>

                        <label className="label" style={{ marginTop: 10 }} htmlFor="neg-quantity">{t("public.negotiateQuantity")}</label>
                        <select id="neg-quantity" className="select" value={negQuantity}
                          onChange={(e) => setNegQuantity(Number(e.target.value))}>
                          {QUANTITY_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
                        </select>

                        <label className="label" style={{ marginTop: 10 }} htmlFor="neg-rate">{t("public.negotiatePrice")}</label>
                        <div style={{ display: "flex", gap: 8 }}>
                          <input id="neg-rate" className="input" inputMode="numeric" value={negRate}
                            onChange={(e) => setNegRate(e.target.value.replace(/\D/g, ""))} placeholder="40000" />
                          <select className="select" style={{ width: 110 }} aria-label={t("campaign.currency")}
                            value={negCurrency} onChange={(e) => setNegCurrency(e.target.value)}>
                            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </div>
                        {/* The same floor the package form states, from the
                            same table (lib/pricing.ts mirrors
                            backend/app/core/pricing.py). A negotiated price
                            cannot undercut it either — that is the point of
                            having one. */}
                        <p className="hint">{t("profile.minPrice", { n: minPrice(negCurrency), currency: negCurrency })}</p>

                        <label className="label" style={{ marginTop: 10 }} htmlFor="neg-days">{t("public.negotiateDays")}</label>
                        <input id="neg-days" className="input" inputMode="numeric" value={negDays}
                          onChange={(e) => setNegDays(e.target.value.replace(/\D/g, ""))} placeholder="7" />

                        <label className="label" style={{ marginTop: 12 }} htmlFor="neg-note">{t("public.orderNote")}</label>
                        <textarea id="neg-note" className="input" rows={3} maxLength={NOTE_MAX_LENGTH}
                          style={{ resize: "vertical" }} value={orderNote} onChange={(e) => setOrderNote(e.target.value)} />

                        <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>{t("public.orderRule")}</p>

                        {orderError && <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{orderError}</div>}

                        <button className="btn btn-primary btn-block" style={{ marginTop: 12 }}
                          disabled={orderBusy || !negPlatform || !negDeliverable || !negRate || !negDays}
                          onClick={placeNegotiatedOrder}>
                          {t("public.negotiateSend")}
                        </button>
                        {/* The negotiated offer put aside instead of sent. A
                            brand assembling one basket across several
                            profiles needs this as much as it needs it for a
                            listed package — and a bespoke offer is exactly
                            the line most likely to be one of four. */}
                        <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 8 }}
                          disabled={orderBusy || !negPlatform || !negDeliverable || !negRate || !negDays}
                          onClick={addNegotiatedToCart}>
                          {t("cart.add")}
                        </button>
                        <button className="btn btn-ghost btn-block" style={{ marginTop: 8 }} disabled={orderBusy}
                          onClick={() => { setNegotiateOpen(false); setOrderError(null); }}>
                          {t("public.orderCancel")}
                        </button>
                      </div>
                    ) : (
                      <>
                        <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={() => setOrderOpen(true)}>
                          {t("public.order")}
                        </button>
                        {/* Beside the order button, not instead of it. One
                            package from one creator stays a single click;
                            this is the path for the brand who is still
                            shopping and will pay for everything at once. */}
                        <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 8 }} onClick={addPackageToCart}>
                          {t("cart.add")}
                        </button>
                        {/* Secondary on purpose: the published price is still
                            the fast path, and this is the way out for the
                            deals that do not fit it — the ones that were
                            being agreed on WhatsApp instead. */}
                        <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "12px 0 0" }}>
                          <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
                          <span className="muted" style={{ fontSize: 12.5 }}>{t("public.negotiateOr")}</span>
                          <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
                        </div>
                        <button type="button" className="pp-see-more" style={{ display: "block", margin: "10px auto 0", fontSize: 14 }}
                          onClick={openNegotiate}>
                          {t("public.negotiate")}
                        </button>
                      </>
                    )}

                    {/* Shared by both add-to-cart buttons: one line saying it
                        worked, and the way to the basket. Nothing was sent to
                        the server, so this is not a receipt and does not read
                        like one. */}
                    {cartMessage && (
                      <div className="alert alert-success" style={{ marginTop: 12, marginBottom: 0 }}>
                        <div>{cartMessage}</div>
                        <Link to="/cart" style={{ fontWeight: 600 }}>{t("cart.view", { n: cartCount })}</Link>
                      </div>
                    )}

                    {/* The escrow explainer sits at the decision point on
                        purpose: this is the trust pitch, right next to the
                        price. */}
                    <button type="button" className="pp-how-toggle" aria-expanded={howOpen} onClick={() => setHowOpen((o) => !o)}>
                      {t("public.howItWorks")}
                    </button>
                    {howOpen && (
                      <ul className="pp-how-steps">
                        <li>{t("public.how1")}</li>
                        <li>{t("public.how2")}</li>
                        <li>{t("public.how3")}</li>
                      </ul>
                    )}
                  </>
                ) : (
                  <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("public.noPackages")}</p>
                )}
                <button className="btn btn-ghost btn-block" style={{ marginTop: 16 }} onClick={() => setShareOpen(true)}>{t("public.share")}</button>
              </div>
            </aside>
          </div>
          {shareOpen && (
            <ShareModal name={profile.display_name || t("discover.creator")}
              url={`${window.location.origin}/u/${profile.user_id}`}
              onClose={() => setShareOpen(false)} />
          )}
          </>
        )}
      </div>
    </Layout>
  );
}
