import { useCallback, useEffect, useRef, useState, type ChangeEvent, type CSSProperties } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api, mediaSrc, uploadFile } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { CITIES, COUNTRIES, joinLocation, splitLocation } from "../lib/countries";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import { CURRENCIES } from "../lib/campaignOptions";
import { SELLABLE_PLATFORMS, deliverablesFor } from "../lib/platforms";
import { minPrice } from "../lib/pricing";
import type { InfluencerProfile, Package } from "../lib/types";

type Social = { id: string; platform: string; handle: string; status: string; enriched?: boolean };
type MediaOut = { id: string; url: string };
type Status = {
  has_bio: boolean; has_categories: boolean; has_pricing: boolean;
  has_packages: boolean; has_social: boolean; has_birth_date: boolean;
  active_package_count: number; is_live: boolean;
};

/* Small neutral chips for quantity (×3) and duration (30 s) on package rows;
   the same shape is used in profile setup. */
const pkgChipStyle: CSSProperties = {
  fontSize: 11.5, fontWeight: 600, padding: "2px 8px", borderRadius: 999,
  background: "var(--surface-2)", color: "var(--muted)", whiteSpace: "nowrap"
};

function Steps({ step }: { step: number }) {
  const { t } = useTranslation();
  const labels = [t("onb.step1"), t("onb.step2"), t("onb.step3")];
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 28, flexWrap: "wrap" }}>
      {labels.map((label, i) => {
        const n = i + 1;
        const done = step > n;
        const active = step === n;
        return (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{
                width: 26, height: 26, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 600,
                background: done || active ? "var(--teal)" : "var(--surface-2)",
                color: done || active ? "#fff" : "var(--muted)"
              }}>{done ? "✓" : n}</span>
              <span style={{ fontSize: 14, fontWeight: active ? 600 : 400, color: active ? "var(--ink)" : "var(--muted)" }}>{label}</span>
            </div>
            {n < 3 && <span style={{ width: 24, height: 1, background: "var(--line)" }} />}
          </div>
        );
      })}
    </div>
  );
}

function HandleModal({ prefix, label, onCancel, onSave, busy }:
  { prefix: string; label: string; onCancel: () => void; onSave: (h: string) => void; busy: boolean }) {
  const { t } = useTranslation();
  const [handle, setHandle] = useState("");
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(21,24,36,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 20 }}
      onClick={onCancel}>
      <div className="card" style={{ maxWidth: 460, width: "100%" }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>{t("onb.handleQuestion", { platform: label })}</h3>
        <div style={{ display: "flex", alignItems: "stretch", marginTop: 12 }}>
          <span style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRight: "none", borderRadius: "8px 0 0 8px", padding: "11px 12px", fontSize: 14, color: "var(--muted)", whiteSpace: "nowrap" }}>
            {prefix}
          </span>
          <input className="input" autoFocus style={{ borderRadius: "0 8px 8px 0" }} placeholder={t("onb.yourHandle")}
            value={handle} onChange={(e) => setHandle(e.target.value.replace(/^@/, "").trim())}
            onKeyDown={(e) => { if (e.key === "Enter" && handle) onSave(handle); }} />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 18 }}>
          <button className="btn btn-ghost" onClick={onCancel}>{t("onb.cancel")}</button>
          <button className="btn btn-primary" disabled={!handle || busy} onClick={() => onSave(handle)}>
            {busy ? t("auth.working") : t("onb.addToProfile")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Onboarding() {
  const { t } = useTranslation();
  const { userId, token, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [socials, setSocials] = useState<Social[]>([]);
  const [modal, setModal] = useState<{ id: string; label: string; prefix: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);

  // Profile fields (prefilled from any existing profile or enrichment).
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  // Country + city compose into the backend's single `location` string on
  // save; see joinLocation/splitLocation in lib/countries.
  const [locCountry, setLocCountry] = useState("");
  const [locCity, setLocCity] = useState("");
  const [cityOther, setCityOther] = useState(false);
  // The go-live gate requires a birth date, so it is the one identity field
  // asked here. Gender and languages live in profile setup: onboarding stays
  // deliberately lean.
  const [birthDate, setBirthDate] = useState("");
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [followers, setFollowers] = useState("");
  const [avatarMediaId, setAvatarMediaId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const avatarRef = useRef<HTMLInputElement>(null);

  // Packages
  const [packages, setPackages] = useState<Package[]>([]);
  const [pkg, setPkg] = useState({ platform: "instagram", deliverable_type: "post", title: "", price: "", currency: "XOF", description: "", quantity: "1", durationValue: "", durationUnit: "" });

  const loadProfile = useCallback(() => {
    if (!userId) return;
    api<InfluencerProfile>(`/profiles/influencer/${userId}`)
      .then((p) => {
        setDisplayName(p.display_name ?? "");
        setHeadline(p.headline ?? "");
        const loc = splitLocation(p.location);
        setLocCity(loc.city);
        setLocCountry(loc.country);
        setBirthDate(p.birth_date ?? "");
        setBio(p.bio ?? "");
        setCategories(p.categories ?? []);
        setFollowers(p.follower_count ? String(p.follower_count) : "");
        setAvatarMediaId(p.avatar_media_id ?? null);
        setAvatarUrl(p.avatar_url ?? null);
      })
      .catch((err) => { if (!(err instanceof ApiError && err.status === 404)) setError(errorText(err, t)); });
  }, [userId, t]);

  const loadAll = useCallback(() => {
    if (!userId) return;
    loadProfile();
    api<Social[]>(`/profiles/${userId}/social-accounts`).then(setSocials).catch(() => undefined);
    api<Package[]>(`/profiles/${userId}/packages`).then(setPackages).catch(() => undefined);
    api<Status>(`/profiles/${userId}/onboarding-status`).then(setStatus).catch(() => undefined);
  }, [userId, loadProfile]);

  useEffect(loadAll, [loadAll]);

  // Sell only where the creator exists: the default ("instagram") may not be
  // connected, so snap the package platform to the first allowed option.
  useEffect(() => {
    setPkg((f) => {
      if (f.platform === "ugc" || socials.some((s) => s.platform === f.platform)) return f;
      const first = SELLABLE_PLATFORMS.find((p) => p.id === "ugc" || socials.some((s) => s.platform === p.id));
      return first ? { ...f, platform: first.id, deliverable_type: deliverablesFor(first.id)[0] || "" } : f;
    });
  }, [socials]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  async function addHandle(handle: string) {
    if (!modal || !userId) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/profiles/${userId}/social-accounts`, {
        method: "POST", token,
        body: { platform: modal.id, handle, method: "manual", proof_url: `https://${modal.prefix}${handle}` }
      });
      setModal(null);
      loadAll();
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function removeSocial(id: string) {
    await api(`/profiles/${userId}/social-accounts/${id}`, { method: "DELETE", token }).catch(() => undefined);
    loadAll();
  }

  async function onAvatar(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !userId) return;
    setBusy(true);
    setError(null);
    try {
      const media = await uploadFile<MediaOut>(`/profiles/${userId}/media`, file, token);
      setAvatarMediaId(media.id);
      setAvatarUrl(media.url);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function saveProfile() {
    if (!userId) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/profiles/influencer/${userId}`, {
        method: "PUT",
        body: {
          display_name: displayName || null, headline: headline || null,
          location: joinLocation(locCity, locCountry),
          avatar_media_id: avatarMediaId,
          // The API enforces 18+; the sentence errorText picks for its
          // refusal code lands in the banner above.
          birth_date: birthDate || null,
          bio: bio || null, categories, rate_card: {},
          follower_count: followers ? Number(followers) : null
        }
      });
      loadAll();
      setStep(2);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function addPackage() {
    if (!userId || !pkg.title || !pkg.price || pkgQtyInvalid || pkgDurationMismatch) return;
    setBusy(true);
    setError(null);
    try {
      // The backend re-checks the price floor and the duration pairing if
      // the form checks are ever bypassed; its refusal carries a code, and
      // the sentence errorText picks for it lands in the banner above.
      await api(`/profiles/${userId}/packages`, {
        method: "POST", token,
        body: {
          platform: pkg.platform, deliverable_type: pkg.deliverable_type, title: pkg.title,
          description: pkg.description || null,
          quantity: Number(pkg.quantity) || 1,
          duration_value: pkg.durationValue ? Number(pkg.durationValue) : null,
          duration_unit: pkg.durationUnit || null,
          price_amount: Number(pkg.price), currency: pkg.currency
        }
      });
      setPkg({ ...pkg, title: "", price: "", description: "", quantity: "1", durationValue: "", durationUnit: "" });
      loadAll();
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  const publicUrl = userId ? `${window.location.origin}/u/${userId}` : "";

  const cityList = CITIES[locCountry] ?? [];
  // The droplist covers major cities only. "Other…" flips back to free text so
  // an unusual or missing city never blocks saving, and a saved city outside
  // the list also renders as free text instead of being silently dropped.
  const cityIsFree = cityList.length === 0 || cityOther || (locCity !== "" && !cityList.includes(locCity));

  // Sell only where the creator exists. UGC is always offered because it is
  // delivered to the brand, never posted on the creator's own account.
  const pkgPlatformOptions = SELLABLE_PLATFORMS.filter((p) => p.id === "ugc" || socials.some((s) => s.platform === p.id));
  const pkgFloor = minPrice(pkg.currency);
  const pkgBelowFloor = pkg.price !== "" && Number(pkg.price) < pkgFloor;
  const pkgQtyNum = Number(pkg.quantity);
  const pkgQtyInvalid = !Number.isInteger(pkgQtyNum) || pkgQtyNum < 1 || pkgQtyNum > 100;
  // Mirror of the server rule: a duration value and its unit travel together
  // or not at all. Checking here keeps the error inline instead of a 422.
  const pkgDurationMismatch = (pkg.durationValue !== "") !== (pkg.durationUnit !== "");

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        <Steps step={step} />
        {error && <div className="alert alert-error">{error}</div>}

        {step === 1 && (
          <>
            <h1>{t("onb.title1")}</h1>
            <p className="muted" style={{ marginTop: -6 }}>{t("onb.sub1")}</p>

            <div className="card" style={{ marginTop: 16 }}>
              <span className="label">{t("onb.addSocials")}</span>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10, marginTop: 8 }}>
                {SOCIAL_PLATFORMS.map((p) => {
                  const account = socials.find((s) => s.platform === p.id);
                  return (
                    <div key={p.id} style={{ position: "relative" }}>
                      <button type="button" className="btn btn-ghost"
                        style={{ width: "100%", flexDirection: "column", padding: "18px 10px", borderColor: account ? "var(--teal)" : undefined, background: account ? "#e7f7f5" : undefined }}
                        onClick={() => !account && setModal({ id: p.id, label: p.label, prefix: p.prefix })}>
                        <span style={{ fontWeight: 600 }}>{p.label}</span>
                        {account && <span style={{ fontSize: 11.5, color: "var(--teal-600)" }}>{t("onb.added")}</span>}
                      </button>
                      {/* The ✕ sits outside the tile button: nesting buttons is
                          invalid HTML and breaks keyboard focus. */}
                      {account && (
                        <button type="button" aria-label={t("onb.removeSocial")} title={t("onb.removeSocial")}
                          onClick={() => removeSocial(account.id)}
                          style={{ position: "absolute", top: -7, right: -7, width: 20, height: 20, borderRadius: 999, border: "none", background: "var(--ink)", color: "#fff", cursor: "pointer", fontSize: 11, lineHeight: 1 }}>
                          ✕
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="hint" style={{ marginTop: 10 }}>{t("onb.socialHint")}</div>
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <div className="field" style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{ width: 72, height: 72, borderRadius: "50%", background: avatarUrl ? "transparent" : "var(--gradient-brand)", overflow: "hidden", flexShrink: 0 }}>
                  {avatarUrl && <img src={mediaSrc(avatarUrl)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
                </div>
                <div>
                  <input ref={avatarRef} type="file" accept="image/*" onChange={onAvatar} style={{ display: "none" }} />
                  <button type="button" className="btn btn-ghost" onClick={() => avatarRef.current?.click()} disabled={busy}>{t("profile.uploadPhoto")}</button>
                </div>
              </div>
              <div className="field">
                <label className="label" htmlFor="o-dn">{t("profile.displayName")}</label>
                <input id="o-dn" className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Ama K." />
              </div>
              <div className="field">
                <label className="label" htmlFor="o-hl">{t("profile.headline")}</label>
                <input id="o-hl" className="input" value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder={t("profile.headlinePlaceholder")} />
              </div>
              <div className="field">
                <span className="label">{t("profile.location")}</span>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <select className="select" aria-label={t("profile.locationCountry")} value={locCountry}
                    onChange={(e) => { setLocCountry(e.target.value); setCityOther(false); }}>
                    <option value="">{t("profile.locationCountry")}</option>
                    {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                  </select>
                  {cityIsFree ? (
                    <input className="input" aria-label={t("profile.locationCity")} value={locCity} onChange={(e) => setLocCity(e.target.value)} placeholder="Cotonou" />
                  ) : (
                    <select className="select" aria-label={t("profile.locationCity")} value={locCity}
                      onChange={(e) => {
                        if (e.target.value === "__other__") { setCityOther(true); setLocCity(""); }
                        else setLocCity(e.target.value);
                      }}>
                      <option value="">{t("profile.locationCity")}</option>
                      {cityList.map((c) => <option key={c} value={c}>{c}</option>)}
                      <option value="__other__">{t("profile.cityOther")}</option>
                    </select>
                  )}
                </div>
              </div>
              <div className="field">
                <label className="label" htmlFor="o-bd">{t("profile.birthDate")}</label>
                <input id="o-bd" type="date" className="input" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
                <div className="hint">{t("profile.birthDateHint")}</div>
              </div>
              <div className="field">
                <label className="label" htmlFor="o-bio">{t("profile.bio")}</label>
                <textarea id="o-bio" className="input" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
              </div>
              <div className="field">
                <label className="label" htmlFor="o-fol">{t("profile.followers")}</label>
                <input id="o-fol" className="input" inputMode="numeric" value={followers}
                  onChange={(e) => setFollowers(e.target.value.replace(/\D/g, ""))} placeholder="10000" />
              </div>
              <div className="field">
                <span className="label">{t("profile.categories")}</span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {CATEGORIES.map((c) => (
                    <button type="button" key={c}
                      onClick={() => setCategories((prev) => prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c])}
                      className={`btn ${categories.includes(c) ? "btn-primary" : "btn-ghost"}`} style={{ padding: "7px 13px", fontSize: 13 }}>
                      {t(`cat.${c}`)}
                    </button>
                  ))}
                </div>
              </div>
              {/* birthDate gates Continue because the go-live check requires it;
                  finding that out only at step 3 would send the creator back. */}
              <button className="btn btn-primary btn-lg" disabled={busy || !bio || categories.length === 0 || !birthDate} onClick={saveProfile}>
                {busy ? t("auth.working") : t("onb.continue")}
              </button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h1>{t("onb.title2")}</h1>
            <p className="muted" style={{ marginTop: -6 }}>{t("onb.sub2")}</p>

            <div className="card" style={{ marginTop: 16 }}>
              {packages.length > 0 && (
                <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
                  {packages.map((p) => (
                    <div key={p.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px" }}>
                      <div>
                        <strong style={{ fontSize: 14 }}>{p.title}</strong>
                        <div className="muted" style={{ fontSize: 12 }}>{p.platform} - {t(`deliverable.${p.deliverable_type}`, p.deliverable_type)}</div>
                        {((p.quantity ?? 1) > 1 || (p.duration_value != null && p.duration_unit)) && (
                          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                            {(p.quantity ?? 1) > 1 && <span style={pkgChipStyle}>{t("pkg.qty", { n: p.quantity })}</span>}
                            {p.duration_value != null && p.duration_unit && (
                              <span style={pkgChipStyle}>{t(`pkg.duration_${p.duration_unit}`, { n: p.duration_value })}</span>
                            )}
                          </div>
                        )}
                      </div>
                      <strong>{p.price_amount} {p.currency}</strong>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <select className="select" value={pkg.platform}
                  onChange={(e) => {
                    const platform = e.target.value;
                    // The old deliverable may not exist on the new platform, so reset it.
                    setPkg({ ...pkg, platform, deliverable_type: deliverablesFor(platform)[0] || "" });
                  }}>
                  {pkgPlatformOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
                <select className="select" value={pkg.deliverable_type} onChange={(e) => setPkg({ ...pkg, deliverable_type: e.target.value })}>
                  {deliverablesFor(pkg.platform).map((d) => <option key={d} value={d}>{t(`deliverable.${d}`, d)}</option>)}
                </select>
              </div>
              {socials.length === 0 && (
                <div className="hint">{t("profile.connectSocialHint")}</div>
              )}
              <input className="input" style={{ marginTop: 8 }} placeholder={t("profile.packageTitle")}
                value={pkg.title} onChange={(e) => setPkg({ ...pkg, title: e.target.value })} />
              <textarea className="input" style={{ marginTop: 8 }} rows={2} maxLength={2000} placeholder={t("profile.description")}
                value={pkg.description} onChange={(e) => setPkg({ ...pkg, description: e.target.value })} />
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 8, marginTop: 8 }}>
                <input className="input" inputMode="numeric" placeholder="50000" value={pkg.price}
                  onChange={(e) => setPkg({ ...pkg, price: e.target.value.replace(/\D/g, "") })} />
                <select className="select" value={pkg.currency} onChange={(e) => setPkg({ ...pkg, currency: e.target.value })}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              {pkgFloor > 0 && (
                <div className="hint" style={{ color: pkgBelowFloor ? "var(--danger)" : undefined }}>
                  {t("profile.minPrice", { n: pkgFloor, currency: pkg.currency })}
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 8, marginTop: 8 }}>
                <div>
                  <span className="label">{t("profile.packageQuantity")}</span>
                  <input className="input" type="number" min={1} max={100} aria-label={t("profile.packageQuantity")}
                    value={pkg.quantity} onChange={(e) => setPkg({ ...pkg, quantity: e.target.value })} />
                </div>
                <div>
                  <span className="label">{t("profile.packageDuration")}</span>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <input className="input" inputMode="numeric" placeholder="30" aria-label={t("profile.packageDuration")}
                      value={pkg.durationValue} onChange={(e) => setPkg({ ...pkg, durationValue: e.target.value.replace(/\D/g, "") })} />
                    <select className="select" aria-label={t("profile.packageDuration")} value={pkg.durationUnit}
                      onChange={(e) => setPkg({ ...pkg, durationUnit: e.target.value })}>
                      <option value="">—</option>
                      <option value="seconds">{t("profile.durationUnitSeconds")}</option>
                      <option value="minutes">{t("profile.durationUnitMinutes")}</option>
                      <option value="hours">{t("profile.durationUnitHours")}</option>
                    </select>
                  </div>
                </div>
              </div>
              {pkgDurationMismatch && (
                <div className="hint" style={{ color: "var(--danger)" }}>{t("profile.durationTogether")}</div>
              )}
              <button className="btn btn-ghost" style={{ marginTop: 10 }}
                disabled={busy || !pkg.title || !pkg.price || pkgBelowFloor || pkgQtyInvalid || pkgDurationMismatch}
                onClick={addPackage}>
                + {t("profile.addPackage")}
              </button>
            </div>

            {/* Three active packages gate go-live. The local list length is used
                rather than active_package_count from onboarding-status: it
                updates instantly after each add and new packages are always
                active; the server re-checks at go-live anyway. */}
            <p className="muted" style={{ fontSize: 13.5, marginTop: 14 }}>{t("onb.pkgProgress", { n: packages.length })}</p>
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <button className="btn btn-ghost" onClick={() => setStep(1)}>{t("onb.back")}</button>
              <button className="btn btn-primary btn-lg" disabled={packages.length < 3} onClick={() => setStep(3)}>
                {t("onb.continue")}
              </button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h1>{t("onb.title3")}</h1>
            <p className="muted" style={{ marginTop: -6 }}>{t("onb.sub3")}</p>

            <div className="card" style={{ marginTop: 16 }}>
              {[
                { ok: status?.has_bio, label: t("onb.checkBio") },
                { ok: status?.has_categories, label: t("onb.checkCategories") },
                { ok: status?.has_birth_date, label: t("onb.checkBirthDate") },
                { ok: status?.has_pricing, label: t("onb.checkPricing") },
                { ok: status?.has_social, label: t("onb.checkSocial") }
              ].map((row) => (
                <div key={row.label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", fontSize: 14 }}>
                  <span style={{ color: row.ok ? "var(--teal-600)" : "var(--muted)" }}>{row.ok ? "✓" : "○"}</span>
                  <span style={{ color: row.ok ? "var(--ink)" : "var(--muted)" }}>{row.label}</span>
                </div>
              ))}

              {status?.is_live ? (
                <>
                  <div className="alert alert-success" style={{ marginTop: 14 }}>{t("onb.liveNow")}</div>
                  <span className="label">{t("onb.yourLink")}</span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input className="input" readOnly value={publicUrl} onFocus={(e) => e.currentTarget.select()} />
                    <button className="btn btn-ghost" onClick={() => navigator.clipboard?.writeText(publicUrl)}>{t("onb.copy")}</button>
                  </div>
                  <div className="hint" style={{ marginTop: 8 }}>{t("onb.linkHint")}</div>
                  <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
                    <Link className="btn btn-primary" to={`/u/${userId}`}>{t("onb.viewProfile")}</Link>
                    <button className="btn btn-ghost" onClick={() => navigate("/dashboard")}>{t("onb.goDashboard")}</button>
                  </div>
                </>
              ) : (
                <>
                  <div className="alert alert-info" style={{ marginTop: 14 }}>{t("onb.notLive")}</div>
                  <button className="btn btn-ghost" onClick={() => setStep(1)}>{t("onb.back")}</button>
                </>
              )}
            </div>
          </>
        )}

        {modal && (
          <HandleModal label={modal.label} prefix={modal.prefix} busy={busy}
            onCancel={() => setModal(null)} onSave={addHandle} />
        )}
      </div>
    </Layout>
  );
}
