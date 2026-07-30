import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api, mediaSrc, uploadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { PLATFORMS, DELIVERABLE_TYPES, CURRENCIES } from "../lib/campaignOptions";
import type { InfluencerProfile, Package, PortfolioItem } from "../lib/types";

type Kind = "influencer" | "business";
type MediaOut = { id: string; url: string };

function PortfolioSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function load() {
    api<PortfolioItem[]>(`/profiles/${userId}/portfolio`).then(setItems).catch(() => undefined);
  }
  useEffect(load, [userId]);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const media = await uploadFile<MediaOut>(`/profiles/${userId}/media`, file, token);
      await api(`/profiles/${userId}/portfolio`, { method: "POST", token, body: { media_id: media.id } });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(id: string) {
    await api(`/profiles/${userId}/portfolio/${id}`, { method: "DELETE", token }).catch(() => undefined);
    load();
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("profile.portfolio")}</h3>
      {error && <div className="alert alert-error">{error}</div>}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {items.map((it) => (
          <div key={it.id} style={{ position: "relative" }}>
            <img src={mediaSrc(it.url)} alt="" style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 8, border: "1px solid var(--line)" }} />
            <button type="button" onClick={() => remove(it.id)} aria-label="remove"
              style={{ position: "absolute", top: -8, right: -8, width: 22, height: 22, borderRadius: 999, border: "none", background: "var(--ink)", color: "#fff", cursor: "pointer" }}>x</button>
          </div>
        ))}
      </div>
      <input ref={fileRef} type="file" accept="image/*" onChange={onFile} style={{ display: "none" }} />
      <button type="button" className="btn btn-ghost" style={{ marginTop: 12 }} disabled={busy} onClick={() => fileRef.current?.click()}>
        {busy ? t("auth.working") : t("profile.addImage")}
      </button>
    </div>
  );
}

const emptyPkg = { platform: "instagram", deliverable_type: "post", title: "", price: "", currency: "XOF", description: "" };

function PackagesSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [packages, setPackages] = useState<Package[]>([]);
  const [form, setForm] = useState({ ...emptyPkg });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<Package[]>(`/profiles/${userId}/packages`).then(setPackages).catch(() => undefined);
  }
  useEffect(load, [userId]);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!form.title || !form.price) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/profiles/${userId}/packages`, {
        method: "POST",
        token,
        body: {
          platform: form.platform,
          deliverable_type: form.deliverable_type,
          title: form.title,
          description: form.description || null,
          price_amount: Number(form.price),
          currency: form.currency
        }
      });
      setForm({ ...emptyPkg });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api(`/profiles/${userId}/packages/${id}`, { method: "DELETE", token }).catch(() => undefined);
    load();
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("profile.packages")}</h3>
      <p className="muted" style={{ marginTop: -6, fontSize: 13 }}>{t("profile.packagesHint")}</p>
      {error && <div className="alert alert-error">{error}</div>}

      {packages.length > 0 && (
        <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
          {packages.map((p) => (
            <div key={p.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px" }}>
              <div>
                <strong style={{ fontSize: 14 }}>{p.title}</strong>
                <div className="muted" style={{ fontSize: 12 }}>{p.platform} - {t(`deliverable.${p.deliverable_type}`, p.deliverable_type)}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <strong>{p.price_amount} {p.currency}</strong>
                <button type="button" className="btn btn-ghost" style={{ padding: "5px 9px" }} onClick={() => remove(p.id)}>x</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={add}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <select className="select" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
            {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="select" value={form.deliverable_type} onChange={(e) => setForm({ ...form, deliverable_type: e.target.value })}>
            {DELIVERABLE_TYPES.map((d) => <option key={d} value={d}>{t(`deliverable.${d}`, d)}</option>)}
          </select>
        </div>
        <input className="input" style={{ marginTop: 8 }} placeholder={t("profile.packageTitle")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 8, marginTop: 8 }}>
          <input className="input" inputMode="numeric" placeholder="50000" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value.replace(/\D/g, "") })} />
          <select className="select" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <button className="btn btn-ghost" type="submit" style={{ marginTop: 10 }} disabled={busy || !form.title || !form.price}>
          + {t("profile.addPackage")}
        </button>
      </form>
    </div>
  );
}

export default function ProfileSetup() {
  const { t } = useTranslation();
  const { userId, token, isAuthenticated } = useAuth();
  const stored = (localStorage.getItem("kolabo_role") as Kind) || "influencer";
  const [kind, setKind] = useState<Kind>(stored === "business" ? "business" : "influencer");

  // Influencer fields
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [location, setLocation] = useState("");
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [followers, setFollowers] = useState("");
  const [rate, setRate] = useState("");
  const [avatarMediaId, setAvatarMediaId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  // Business fields
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const avatarRef = useRef<HTMLInputElement>(null);

  // Load existing influencer profile to prefill the form.
  useEffect(() => {
    if (!userId) return;
    api<InfluencerProfile>(`/profiles/influencer/${userId}`)
      .then((p) => {
        setDisplayName(p.display_name ?? "");
        setHeadline(p.headline ?? "");
        setLocation(p.location ?? "");
        setBio(p.bio ?? "");
        setCategories(p.categories ?? []);
        setFollowers(p.follower_count ? String(p.follower_count) : "");
        setRate(p.rate_card && p.rate_card.post ? String(p.rate_card.post) : "");
        setAvatarMediaId(p.avatar_media_id ?? null);
        setAvatarUrl(p.avatar_url ?? null);
      })
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 404)) {
          setError(err instanceof Error ? err.message : "Error");
        }
      });
  }, [userId]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function toggleCategory(c: string) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    setBusy(true);
    try {
      if (kind === "influencer") {
        await api(`/profiles/influencer/${userId}`, {
          method: "PUT",
          body: {
            display_name: displayName || null,
            headline: headline || null,
            location: location || null,
            avatar_media_id: avatarMediaId,
            bio: bio || null,
            categories,
            rate_card: rate ? { post: Number(rate) } : {},
            follower_count: followers ? Number(followers) : null
          }
        });
      } else {
        await api(`/profiles/business/${userId}`, {
          method: "PUT",
          body: { company_name: company, industry: industry || null, description: description || null }
        });
      }
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0 }}>{t("profile.title")}</h1>
          {kind === "influencer" && userId && (
            <Link className="btn btn-ghost" to={`/u/${userId}`}>{t("profile.viewPublic")}</Link>
          )}
        </div>
        <p className="muted">{t("profile.sub")}</p>

        <div className="segment" style={{ margin: "8px 0 22px" }}>
          {(["influencer", "business"] as Kind[]).map((k) => (
            <div key={k} className={`segment-option ${kind === k ? "selected" : ""}`} onClick={() => setKind(k)}
              role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setKind(k); }}>
              <div className="t">{k === "influencer" ? t("profile.asCreator") : t("profile.asBusiness")}</div>
            </div>
          ))}
        </div>

        <div className="card">
          {error && <div className="alert alert-error">{error}</div>}
          {done && <div className="alert alert-success">{t("profile.saved")}</div>}
          <form onSubmit={onSubmit}>
            {kind === "influencer" ? (
              <>
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
                  <label className="label" htmlFor="dn">{t("profile.displayName")}</label>
                  <input id="dn" className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Ama K." />
                </div>
                <div className="field">
                  <label className="label" htmlFor="hl">{t("profile.headline")}</label>
                  <input id="hl" className="input" value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder={t("profile.headlinePlaceholder")} />
                </div>
                <div className="field">
                  <label className="label" htmlFor="loc">{t("profile.location")}</label>
                  <input id="loc" className="input" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Cotonou, BJ" />
                </div>
                <div className="field">
                  <label className="label" htmlFor="bio">{t("profile.bio")}</label>
                  <textarea id="bio" className="input" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
                </div>
                <div className="field">
                  <span className="label">{t("profile.categories")}</span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {CATEGORIES.map((c) => (
                      <button type="button" key={c} onClick={() => toggleCategory(c)}
                        className={`btn ${categories.includes(c) ? "btn-primary" : "btn-ghost"}`} style={{ padding: "7px 13px", fontSize: 13 }}>
                        {t(`cat.${c}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="field">
                  <label className="label" htmlFor="followers">{t("profile.followers")}</label>
                  <input id="followers" className="input" inputMode="numeric" value={followers}
                    onChange={(e) => setFollowers(e.target.value.replace(/\D/g, ""))} placeholder="10000" />
                </div>
                <div className="field">
                  <label className="label" htmlFor="rate">{t("profile.rate")}</label>
                  <input id="rate" className="input" inputMode="numeric" value={rate}
                    onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} placeholder="50000" />
                  <div className="hint">{t("profile.rateHint")}</div>
                </div>
              </>
            ) : (
              <>
                <div className="field">
                  <label className="label" htmlFor="company">{t("profile.company")}</label>
                  <input id="company" className="input" value={company} onChange={(e) => setCompany(e.target.value)} required />
                </div>
                <div className="field">
                  <label className="label" htmlFor="industry">{t("profile.industry")}</label>
                  <input id="industry" className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} />
                </div>
                <div className="field">
                  <label className="label" htmlFor="description">{t("profile.description")}</label>
                  <textarea id="description" className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
              </>
            )}
            <button className="btn btn-primary btn-lg" disabled={busy} type="submit">
              {busy ? t("auth.working") : t("profile.save")}
            </button>
          </form>
        </div>

        {kind === "influencer" && userId && (
          <>
            <PortfolioSection userId={userId} token={token} />
            <PackagesSection userId={userId} token={token} />
          </>
        )}
      </div>
    </Layout>
  );
}
