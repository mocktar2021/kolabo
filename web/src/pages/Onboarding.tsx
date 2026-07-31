import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api, mediaSrc, uploadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES, joinLocation, splitLocation } from "../lib/countries";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import { CURRENCIES } from "../lib/campaignOptions";
import { SELLABLE_PLATFORMS, deliverablesFor } from "../lib/platforms";
import type { InfluencerProfile, Package } from "../lib/types";

type Social = { id: string; platform: string; handle: string; status: string; enriched?: boolean };
type MediaOut = { id: string; url: string };
type Status = {
  has_bio: boolean; has_categories: boolean; has_pricing: boolean;
  has_packages: boolean; has_social: boolean; is_live: boolean;
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
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [followers, setFollowers] = useState("");
  const [avatarMediaId, setAvatarMediaId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const avatarRef = useRef<HTMLInputElement>(null);

  // Packages
  const [packages, setPackages] = useState<Package[]>([]);
  const [pkg, setPkg] = useState({ platform: "instagram", deliverable_type: "post", title: "", price: "", currency: "XOF" });

  const loadProfile = useCallback(() => {
    if (!userId) return;
    api<InfluencerProfile>(`/profiles/influencer/${userId}`)
      .then((p) => {
        setDisplayName(p.display_name ?? "");
        setHeadline(p.headline ?? "");
        const loc = splitLocation(p.location);
        setLocCity(loc.city);
        setLocCountry(loc.country);
        setBio(p.bio ?? "");
        setCategories(p.categories ?? []);
        setFollowers(p.follower_count ? String(p.follower_count) : "");
        setAvatarMediaId(p.avatar_media_id ?? null);
        setAvatarUrl(p.avatar_url ?? null);
      })
      .catch((err) => { if (!(err instanceof ApiError && err.status === 404)) setError(err.message); });
  }, [userId]);

  const loadAll = useCallback(() => {
    if (!userId) return;
    loadProfile();
    api<Social[]>(`/profiles/${userId}/social-accounts`).then(setSocials).catch(() => undefined);
    api<Package[]>(`/profiles/${userId}/packages`).then(setPackages).catch(() => undefined);
    api<Status>(`/profiles/${userId}/onboarding-status`).then(setStatus).catch(() => undefined);
  }, [userId, loadProfile]);

  useEffect(loadAll, [loadAll]);

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
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
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
      setError(err instanceof Error ? err.message : "Error");
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
          bio: bio || null, categories, rate_card: {},
          follower_count: followers ? Number(followers) : null
        }
      });
      loadAll();
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function addPackage() {
    if (!userId || !pkg.title || !pkg.price) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/profiles/${userId}/packages`, {
        method: "POST", token,
        body: {
          platform: pkg.platform, deliverable_type: pkg.deliverable_type, title: pkg.title,
          price_amount: Number(pkg.price), currency: pkg.currency
        }
      });
      setPkg({ ...pkg, title: "", price: "" });
      loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  const connected = new Set(socials.map((s) => s.platform));
  const publicUrl = userId ? `${window.location.origin}/u/${userId}` : "";

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
                  const isOn = connected.has(p.id);
                  return (
                    <button key={p.id} type="button" className="btn btn-ghost"
                      style={{ flexDirection: "column", padding: "18px 10px", borderColor: isOn ? "var(--teal)" : undefined, background: isOn ? "#e7f7f5" : undefined }}
                      onClick={() => !isOn && setModal({ id: p.id, label: p.label, prefix: p.prefix })}>
                      <span style={{ fontWeight: 600 }}>{p.label}</span>
                      {isOn && <span style={{ fontSize: 11.5, color: "var(--teal-600)" }}>{t("onb.added")}</span>}
                    </button>
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
                  <select className="select" aria-label={t("profile.locationCountry")} value={locCountry} onChange={(e) => setLocCountry(e.target.value)}>
                    <option value="">{t("profile.locationCountry")}</option>
                    {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                  </select>
                  <input className="input" aria-label={t("profile.locationCity")} value={locCity} onChange={(e) => setLocCity(e.target.value)} placeholder="Cotonou" />
                </div>
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
              <button className="btn btn-primary btn-lg" disabled={busy || !bio || categories.length === 0} onClick={saveProfile}>
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
                  {SELLABLE_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
                <select className="select" value={pkg.deliverable_type} onChange={(e) => setPkg({ ...pkg, deliverable_type: e.target.value })}>
                  {deliverablesFor(pkg.platform).map((d) => <option key={d} value={d}>{t(`deliverable.${d}`, d)}</option>)}
                </select>
              </div>
              <input className="input" style={{ marginTop: 8 }} placeholder={t("profile.packageTitle")}
                value={pkg.title} onChange={(e) => setPkg({ ...pkg, title: e.target.value })} />
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 8, marginTop: 8 }}>
                <input className="input" inputMode="numeric" placeholder="50000" value={pkg.price}
                  onChange={(e) => setPkg({ ...pkg, price: e.target.value.replace(/\D/g, "") })} />
                <select className="select" value={pkg.currency} onChange={(e) => setPkg({ ...pkg, currency: e.target.value })}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button className="btn btn-ghost" style={{ marginTop: 10 }} disabled={busy || !pkg.title || !pkg.price} onClick={addPackage}>
                + {t("profile.addPackage")}
              </button>
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <button className="btn btn-ghost" onClick={() => setStep(1)}>{t("onb.back")}</button>
              <button className="btn btn-primary btn-lg" disabled={packages.length === 0} onClick={() => setStep(3)}>
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
