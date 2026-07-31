import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ShareModal } from "../components/ShareModal";
import { api, mediaSrc } from "../lib/api";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { Package, PublicProfile } from "../lib/types";

/* Collabstr-style marketplace page: proof on the left (gallery, packages,
   audience, reviews, FAQ), a sticky order card on the right so the price and
   the escrow pitch never leave the screen. */
export default function PublicProfilePage() {
  const { t, i18n } = useTranslation();
  const { userId } = useParams();
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
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [userId, lang]);

  const packages = profile?.packages.filter((p) => p.is_active) ?? [];
  const packagePlatforms = [...new Set(packages.map((p) => p.platform))];
  const visiblePackages = platformFilter ? packages.filter((p) => p.platform === platformFilter) : packages;
  const selectedPackage = packages.find((p) => p.id === selectedId) ?? packages[0] ?? null;

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
                        <option key={p.id} value={p.id}>1 × {p.title} — {price(p)}</option>
                      ))}
                    </select>
                    {selectedPackage.description && <p className="pp-order-desc">{selectedPackage.description}</p>}
                    {/* Direct ordering ships separately; the card sells the flow
                        before the checkout exists. */}
                    <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} disabled title={t("public.orderSoon")}>
                      {t("public.order")}
                    </button>
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
