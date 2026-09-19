import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties, type FormEvent } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api, mediaSrc, uploadFile } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { CITIES, COUNTRIES, joinLocation, splitLocation } from "../lib/countries";
import { CURRENCIES } from "../lib/campaignOptions";
import { PLATFORM_LABELS, SELLABLE_PLATFORMS, deliverablesFor } from "../lib/platforms";
import { MIN_LIVE_PACKAGES, deactivationHidesProfile, minPrice } from "../lib/pricing";
import { CONNECTABLE_PLATFORMS, SOCIAL_PLATFORMS, platformHasAudience } from "../lib/socialPlatforms";
import type { InfluencerProfile, Package, PortfolioItem } from "../lib/types";

type Kind = "influencer" | "business";
type MediaOut = { id: string; url: string };
type BusinessProfileOut = { user_id: string; company_name: string; industry: string | null; description: string | null };
type SocialAccount = { id: string; platform: string; handle: string; status: string; follower_count: number | null };
/* What POST /profiles/oauth/{platform}/start answers with: the platform's own
   consent screen, already carrying the state and the scopes. Nothing else is
   in the body. */
type OAuthStartOut = { authorize_url: string };

/* Small neutral chips for quantity (×3) and duration (30 s) on package rows;
   the same shape is used in onboarding step 2. */
const pkgChipStyle: CSSProperties = {
  fontSize: 11.5, fontWeight: 600, padding: "2px 8px", borderRadius: 999,
  background: "var(--surface-2)", color: "var(--muted)", whiteSpace: "nowrap"
};

/* The same chip outlined rather than filled, so "Inactive" does not read as
   one more spec sitting alongside ×3 and 30 s. */
const inactiveChipStyle: CSSProperties = {
  ...pkgChipStyle, background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)"
};

function PortfolioSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function load() {
    api<PortfolioItem[]>(`/profiles/${userId}/portfolio`).then(setItems).catch(() => undefined);
  }
  useEffect(load, [userId]);

  async function onFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      // The backend takes one file per request, so the selection is uploaded
      // sequentially: a failure stays attributable to a single photo, and the
      // photos already attached before it survive.
      for (let i = 0; i < files.length; i++) {
        setProgress({ done: i + 1, total: files.length });
        const media = await uploadFile<MediaOut>(`/profiles/${userId}/media`, files[i], token);
        await api(`/profiles/${userId}/portfolio`, { method: "POST", token, body: { media_id: media.id } });
      }
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
      setProgress(null);
      if (fileRef.current) fileRef.current.value = "";
      load();
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
      <input ref={fileRef} type="file" accept="image/*" multiple onChange={onFiles} style={{ display: "none" }} />
      <button type="button" className="btn btn-ghost" style={{ marginTop: 12 }} disabled={busy} onClick={() => fileRef.current?.click()}>
        {busy
          ? progress
            ? t("profile.uploadingCount", { done: progress.done, total: progress.total })
            : t("auth.working")
          : t("profile.addImage")}
      </button>
    </div>
  );
}

/* Connected social accounts: list, inline edit, delete, and add. The add flow
   reuses the platform-tile + handle-modal pattern from onboarding as a light
   local implementation rather than a shared component.

   THE FOLLOWER COUNT IS NOT ASKED FOR ON EVERY PLATFORM. platformHasAudience
   mirrors PLATFORMS_WITH_AUDIENCE in backend/app/core/platforms.py: WhatsApp
   Status publishes no public metric, so there is no number to type, nothing
   to verify it against later, and no figure a brand could compare with
   anybody else's. Offering the box anyway would collect a guess and then show
   it on a profile card as though the platform had confirmed it. */
function SocialSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editHandle, setEditHandle] = useState("");
  const [editFollowers, setEditFollowers] = useState("");
  const [adding, setAdding] = useState<{ id: string; label: string; prefix: string } | null>(null);
  const [newHandle, setNewHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* The success banner this section owns, beside the error one it already
     had. Its own state rather than a flag on `error`, because the two answers
     a creator can come back from a consent screen with are a success and a
     failure, and they must not look alike. */
  const [notice, setNotice] = useState<string | null>(null);
  /* Which platform's Connect button is mid-handshake, or null. NOT the `busy`
     flag above, which gates the handle modal and the inline editor: a creator
     whose browser is on its way to Facebook should not find the edit buttons
     of their other accounts disabled for the moment that takes. */
  const [connecting, setConnecting] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  function load() {
    api<SocialAccount[]>(`/profiles/${userId}/social-accounts`).then(setAccounts).catch(() => undefined);
  }
  useEffect(load, [userId]);

  /* COMING BACK FROM A CONSENT SCREEN, and the other half of startConnect
     below. The API 302s to this page with ?connected=<platform> when it
     worked and ?social_error=<code> when it did not; see finish_social_oauth
     in backend/app/modules/profiles/router.py. This effect is the only place
     a creator is told which of the two happened.

     THE FAILURE SENTENCE IS NOT WRITTEN HERE. The code on the query string is
     one complete_authorization already raises (oauth_exchange_failed,
     oauth_state_expired, oauth_state_invalid) and both catalogues already
     carry a French and an English sentence for each, so errorText does the
     same lookup it does for every other refusal in this file. New copy for
     them would be a second sentence for the same fact, free to drift from the
     first.

     THE ACCOUNTS ARE RE-READ because the handle and the follower count only
     exist after the exchange: what is on screen was fetched before the
     creator ever left for the consent screen.

     THE MARKER IS CLEARED AS SOON AS IT IS READ, through the router rather
     than history.replaceState so react-router's own idea of the location
     stays true, and with replace so the back button does not gain a step.
     Left on the URL it would mean a refresh, a bookmark or the back button
     re-announcing a handshake that happened once and may have been hours
     ago. */
  const connectedParam = searchParams.get("connected");
  const socialErrorParam = searchParams.get("social_error");
  useEffect(() => {
    if (!connectedParam && !socialErrorParam) return;
    if (connectedParam) {
      const platform = SOCIAL_PLATFORMS.find((p) => p.id === connectedParam);
      setError(null);
      setNotice(t("profile.socialConnected", { platform: platform?.label ?? connectedParam }));
    } else if (socialErrorParam) {
      setNotice(null);
      setError(errorText({ code: socialErrorParam }, t));
    }
    load();
    const next = new URLSearchParams(searchParams);
    next.delete("connected");
    next.delete("social_error");
    setSearchParams(next, { replace: true });
  }, [connectedParam, socialErrorParam]);

  function startEdit(a: SocialAccount) {
    setEditingId(a.id);
    setEditHandle(a.handle);
    setEditFollowers(a.follower_count ? String(a.follower_count) : "");
  }

  async function saveEdit(id: string) {
    if (!editHandle) return;
    setBusy(true);
    setError(null);
    try {
      /* Null for a platform with no audience, whatever is in the box.
         Belt and braces: the input is not rendered there, so the state cannot
         normally hold anything — but it CAN hold a stale value from the
         previous row, because startEdit fills it from whichever account was
         opened before. Reading the platform here rather than trusting the
         form is what stops an Instagram figure being saved onto a WhatsApp
         account. */
      const platform = accounts.find((a) => a.id === id)?.platform;
      const withAudience = platform ? platformHasAudience(platform) : true;
      // The response carries the new status: editing the handle resets a
      // verified account to pending, and the chip must reflect that at once.
      const updated = await api<SocialAccount>(`/profiles/${userId}/social-accounts/${id}`, {
        method: "PUT", token,
        body: {
          handle: editHandle,
          follower_count: withAudience && editFollowers ? Number(editFollowers) : null
        }
      });
      setAccounts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      setEditingId(null);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("profile.socialDeleteConfirm"))) return;
    await api(`/profiles/${userId}/social-accounts/${id}`, { method: "DELETE", token }).catch(() => undefined);
    load();
  }

  async function add(handle: string) {
    if (!adding) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/profiles/${userId}/social-accounts`, {
        method: "POST", token,
        body: { platform: adding.id, handle, method: "manual", proof_url: `https://${adding.prefix}${handle}` }
      });
      setAdding(null);
      setNewHandle("");
      load();
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  /* Hand the browser to the platform's own consent screen.

     `redirect_to` IS WHAT MAKES THE ROUND TRIP END BACK HERE, and getting it
     wrong fails silently. The backend checks it against an allowlist built
     from the configured web origin and DISCARDS a value that fails rather
     than refusing the request, deliberately, so that a client bug never costs
     a creator their connection (oauth_service._allowlisted_or_discarded). The
     cost of that kindness is that a wrong origin produces no error anywhere:
     the handshake completes and the creator lands on the callback's raw JSON.
     window.location.origin is what keeps it right for local, staging and
     production out of one build, because it is the origin the creator is
     actually on rather than one compiled in.

     window.location.href rather than the router, and it is not a shortcut:
     authorize_url is on facebook.com, which is not a route this app has or
     could ever have. */
  async function startConnect(platform: string) {
    setConnecting(platform);
    setError(null);
    setNotice(null);
    try {
      const started = await api<OAuthStartOut>(`/profiles/oauth/${platform}/start`, {
        method: "POST", token,
        body: { redirect_to: `${window.location.origin}/profile` }
      });
      /* `connecting` is deliberately not cleared here. The browser is leaving;
         putting the button back to its resting label for the moment that takes
         would read as though the click had done nothing. */
      window.location.href = started.authorize_url;
    } catch (err) {
      setError(errorText(err, t));
      setConnecting(null);
    }
  }

  const connected = new Set(accounts.map((a) => a.platform));

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("profile.socialTitle")}</h3>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {accounts.length === 0 ? (
        <p className="muted" style={{ fontSize: 13.5 }}>{t("profile.socialEmpty")}</p>
      ) : (
        <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
          {accounts.map((a) => {
            const withAudience = platformHasAudience(a.platform);
            return editingId === a.id ? (
              <div key={a.id} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px" }}>
                <strong style={{ fontSize: 14 }}>{PLATFORM_LABELS[a.platform] ?? a.platform}</strong>
                <div style={{ display: "grid", gridTemplateColumns: withAudience ? "1fr 1fr" : "1fr", gap: 8, marginTop: 8 }}>
                  <input className="input" aria-label={t("onb.yourHandle")} value={editHandle}
                    onChange={(e) => setEditHandle(e.target.value.replace(/^@/, "").trim())} />
                  {withAudience && (
                    <input className="input" aria-label={t("profile.followers")} inputMode="numeric" placeholder={t("profile.followers")}
                      value={editFollowers} onChange={(e) => setEditFollowers(e.target.value.replace(/\D/g, ""))} />
                  )}
                </div>
                {/* Said rather than left to be noticed. A creator who counts on
                    their WhatsApp audience will see the missing box and assume
                    something broke. */}
                {!withAudience && <div className="hint">{t("profile.noAudienceHint")}</div>}
                <div className="hint">{t("profile.socialEditHint")}</div>
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  <button type="button" className="btn btn-primary" style={{ padding: "7px 14px", fontSize: 13 }} disabled={busy || !editHandle} onClick={() => saveEdit(a.id)}>
                    {busy ? t("auth.working") : t("profile.save")}
                  </button>
                  <button type="button" className="btn btn-ghost" style={{ padding: "7px 14px", fontSize: 13 }} onClick={() => setEditingId(null)}>{t("onb.cancel")}</button>
                </div>
              </div>
            ) : (
              <div key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px" }}>
                <div style={{ minWidth: 0 }}>
                  <strong style={{ fontSize: 14 }}>{PLATFORM_LABELS[a.platform] ?? a.platform}</strong>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {/* The audience half only renders on a non-null count,
                        which is what keeps a WhatsApp row from showing an
                        empty chip: the server never stores one for it. */}
                    @{a.handle}{a.follower_count !== null && ` · ${a.follower_count.toLocaleString()} ${t("public.audienceUnit")}`}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999,
                    background: a.status === "verified" ? "#e7f6f0" : "var(--surface-2)",
                    color: a.status === "verified" ? "var(--success)" : "var(--muted)"
                  }}>
                    {a.status === "verified" ? t("profile.socialVerified") : t("profile.socialPending")}
                  </span>
                  <button type="button" className="btn btn-ghost" style={{ padding: "5px 10px", fontSize: 13 }} onClick={() => startEdit(a)}>{t("profile.socialEdit")}</button>
                  <button type="button" className="btn btn-ghost" style={{ padding: "5px 10px", fontSize: 13 }} onClick={() => remove(a.id)}>{t("profile.socialDelete")}</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* THE CONNECT PATH, AND IT SITS ABOVE THE TILES ON PURPOSE. Typing a
          handle CLAIMS an account; connecting PROVES it, and the follower
          count that comes back with it is the platform's own answer about its
          own Page rather than a number somebody typed into a box. Facebook is
          the only platform that can do this today, and it is also the one
          where typing was never going to be enough: the Graph API will not
          answer questions about a Page this app does not administer, so a
          Facebook handle in a box buys the link and nothing else.

          THE TILES BELOW STAY, and that is a product decision rather than an
          omission. A creator who declines the consent screen, who runs no
          Page, or who simply will not hand an app permissions must still be
          able to say where they are; the follower provenance model already
          tells a typed number from a platform-stated one, so the two paths do
          not have to pretend to be worth the same. Removing the typed path to
          make room for this one would take a working feature away from every
          platform that has no provider, which is all of them but one. */}
      {CONNECTABLE_PLATFORMS.map((p) => (
        <div key={p.id} style={{ marginBottom: 14 }}>
          <button type="button" className="btn btn-primary" disabled={connecting !== null}
            onClick={() => startConnect(p.id)}>
            {connecting === p.id ? t("auth.working") : t("profile.socialConnectWith", { platform: p.label })}
          </button>
          <div className="hint">{t("profile.socialConnectHint", { platform: p.label })}</div>
        </div>
      ))}

      <span className="label">{t("profile.socialAdd")}</span>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10, marginTop: 8 }}>
        {SOCIAL_PLATFORMS.map((p) => {
          const isOn = connected.has(p.id);
          return (
            <button key={p.id} type="button" className="btn btn-ghost"
              style={{ flexDirection: "column", padding: "14px 10px", borderColor: isOn ? "var(--teal)" : undefined, background: isOn ? "#e7f7f5" : undefined }}
              onClick={() => !isOn && setAdding({ id: p.id, label: p.label, prefix: p.prefix })}>
              <span style={{ fontWeight: 600 }}>{p.label}</span>
              {isOn && <span style={{ fontSize: 11.5, color: "var(--teal-600)" }}>{t("onb.added")}</span>}
            </button>
          );
        })}
      </div>

      {adding && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(21,24,36,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 20 }}
          onClick={() => { setAdding(null); setNewHandle(""); }}>
          <div className="card" style={{ maxWidth: 460, width: "100%" }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>{t("onb.handleQuestion", { platform: adding.label })}</h3>
            <div style={{ display: "flex", alignItems: "stretch", marginTop: 12 }}>
              <span style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRight: "none", borderRadius: "8px 0 0 8px", padding: "11px 12px", fontSize: 14, color: "var(--muted)", whiteSpace: "nowrap" }}>
                {adding.prefix}
              </span>
              <input className="input" autoFocus style={{ borderRadius: "0 8px 8px 0" }} placeholder={t("onb.yourHandle")}
                value={newHandle} onChange={(e) => setNewHandle(e.target.value.replace(/^@/, "").trim())}
                onKeyDown={(e) => { if (e.key === "Enter" && newHandle) add(newHandle); }} />
            </div>
            {/* Nothing about an audience is asked for here on any platform —
                the add flow only takes a handle — but the hint belongs on the
                platforms where it will never be asked for at all, so a
                creator knows before connecting rather than after. */}
            {!platformHasAudience(adding.id) && <div className="hint">{t("profile.noAudienceHint")}</div>}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 18 }}>
              <button className="btn btn-ghost" onClick={() => { setAdding(null); setNewHandle(""); }}>{t("onb.cancel")}</button>
              <button className="btn btn-primary" disabled={!newHandle || busy} onClick={() => add(newHandle)}>
                {busy ? t("auth.working") : t("onb.addToProfile")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const emptyPkg = { platform: "instagram", deliverable_type: "post", title: "", price: "", currency: "XOF", description: "", quantity: "1", durationValue: "", durationUnit: "" };

function PackagesSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [packages, setPackages] = useState<Package[]>([]);
  const [form, setForm] = useState({ ...emptyPkg });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Platforms of the connected social accounts; null while loading.
  const [socialPlatforms, setSocialPlatforms] = useState<Set<string> | null>(null);

  function load() {
    api<Package[]>(`/profiles/${userId}/packages`).then(setPackages).catch(() => undefined);
  }
  useEffect(load, [userId]);

  useEffect(() => {
    api<SocialAccount[]>(`/profiles/${userId}/social-accounts`)
      .then((list) => setSocialPlatforms(new Set(list.map((a) => a.platform))))
      .catch(() => setSocialPlatforms(new Set()));
  }, [userId]);

  // Product rule: a creator sells only where they exist, so the platform
  // options come from the connected accounts. UGC is always offered because
  // it is delivered to the brand, never posted on the creator's own account.
  const platformOptions = SELLABLE_PLATFORMS.filter((p) => p.id === "ugc" || (socialPlatforms?.has(p.id) ?? false));

  // The default ("instagram") may not be sellable for this creator; once the
  // accounts arrive, snap the selection back to the first allowed platform.
  useEffect(() => {
    if (socialPlatforms === null) return;
    setForm((f) => {
      if (f.platform === "ugc" || socialPlatforms.has(f.platform)) return f;
      const first = SELLABLE_PLATFORMS.find((p) => p.id === "ugc" || socialPlatforms.has(p.id));
      return first ? { ...f, platform: first.id, deliverable_type: deliverablesFor(first.id)[0] || "" } : f;
    });
  }, [socialPlatforms]);

  const floor = minPrice(form.currency);
  const belowFloor = form.price !== "" && Number(form.price) < floor;
  const qty = Number(form.quantity);
  const qtyInvalid = !Number.isInteger(qty) || qty < 1 || qty > 100;
  // Mirror of the server rule: a duration value and its unit travel together
  // or not at all. Checking here keeps the error inline instead of a 422.
  const durationMismatch = (form.durationValue !== "") !== (form.durationUnit !== "");

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!form.title || !form.price || belowFloor || qtyInvalid || durationMismatch) return;
    setBusy(true);
    setError(null);
    try {
      // The backend re-checks the price floor and the duration pairing if
      // the form checks are ever bypassed; its refusal carries a code, and
      // the sentence errorText picks for it lands in the banner above.
      await api(`/profiles/${userId}/packages`, {
        method: "POST",
        token,
        body: {
          platform: form.platform,
          deliverable_type: form.deliverable_type,
          title: form.title,
          description: form.description || null,
          quantity: qty,
          duration_value: form.durationValue ? Number(form.durationValue) : null,
          duration_unit: form.durationUnit || null,
          price_amount: Number(form.price),
          currency: form.currency
        }
      });
      setForm({ ...emptyPkg, platform: form.platform, deliverable_type: form.deliverable_type, currency: form.currency });
      load();
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await api(`/profiles/${userId}/packages/${id}`, { method: "DELETE", token }).catch(() => undefined);
    load();
  }

  /* What a buyer can currently order — the same figure onboarding-status
     reports as active_package_count, counted from the list already on screen
     so the warning cannot lag a round trip behind the box that changes it. */
  const activeCount = packages.filter((p) => p.is_active).length;

  /* The Active box. Turning a package off is NOT deleting it: the row keeps
     its title, its price and its place in this list, stays editable, and is
     orderable again the moment it goes back on. It only leaves the public
     page and the buyer-facing search.

     That second half is the dangerous one. Below MIN_LIVE_PACKAGES the
     creator drops out of discovery entirely and NOTHING SAYS SO — the API
     does not refuse, the profile simply stops being returned. So the one
     click that crosses that line states the consequence first, with the
     threshold interpolated rather than written into the sentence. It states
     it and does not prevent it: hiding a package is a legitimate thing to
     want, and cancelling leaves the package exactly as it was. */
  async function setActive(pkg: Package, isActive: boolean) {
    if (
      !isActive && deactivationHidesProfile(activeCount) &&
      !window.confirm(t("profile.packageDeactivateWarning", { min: MIN_LIVE_PACKAGES }))
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      /* PUT /packages/{id} takes a whole PackageIn rather than a patch, so
         every field travels as it stands with the one flag flipped: a key left
         out would be read as a cleared value, not as an unchanged one. */
      const updated = await api<Package>(`/profiles/${userId}/packages/${pkg.id}`, {
        method: "PUT",
        token,
        body: {
          platform: pkg.platform,
          deliverable_type: pkg.deliverable_type,
          title: pkg.title,
          description: pkg.description,
          quantity: pkg.quantity ?? 1,
          duration_value: pkg.duration_value,
          duration_unit: pkg.duration_unit,
          price_amount: pkg.price_amount,
          currency: pkg.currency,
          is_active: isActive
        }
      });
      setPackages((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("profile.packages")}</h3>
      <p className="muted" style={{ marginTop: -6, fontSize: 13 }}>{t("profile.packagesHint")}</p>
      {error && <div className="alert alert-error">{error}</div>}

      {packages.length > 0 && (
        <div style={{ display: "grid", gap: 8, marginBottom: 14 }}>
          {packages.map((p) => (
            <div key={p.id} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px",
              // An inactive package still belongs here, so it is greyed rather
              // than moved, hidden or struck through.
              background: p.is_active ? undefined : "var(--surface-2)"
            }}>
              <div style={{ opacity: p.is_active ? 1 : 0.6 }}>
                <strong style={{ fontSize: 14 }}>{p.title}</strong>
                <div className="muted" style={{ fontSize: 12 }}>{p.platform} - {t(`deliverable.${p.deliverable_type}`, p.deliverable_type)}</div>
                {(!p.is_active || (p.quantity ?? 1) > 1 || (p.duration_value != null && p.duration_unit)) && (
                  <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                    {/* Named as well as greyed. A dimmed row on its own reads
                        as a rendering glitch; the word says which state it is
                        in, and that the state was chosen. */}
                    {!p.is_active && <span style={inactiveChipStyle}>{t("profile.packageInactive")}</span>}
                    {(p.quantity ?? 1) > 1 && <span style={pkgChipStyle}>{t("pkg.qty", { n: p.quantity })}</span>}
                    {p.duration_value != null && p.duration_unit && (
                      <span style={pkgChipStyle}>{t(`pkg.duration_${p.duration_unit}`, { n: p.duration_value })}</span>
                    )}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, cursor: "pointer", whiteSpace: "nowrap" }}>
                  <input type="checkbox" checked={p.is_active} disabled={busy}
                    onChange={(e) => setActive(p, e.target.checked)} />
                  {t("profile.packageActive")}
                </label>
                <strong>{p.price_amount} {p.currency}</strong>
                <button type="button" className="btn btn-ghost" style={{ padding: "5px 9px" }} onClick={() => remove(p.id)}>x</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={add}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <select className="select" value={form.platform}
            onChange={(e) => {
              const platform = e.target.value;
              // The old deliverable may not exist on the new platform, so reset it.
              setForm({ ...form, platform, deliverable_type: deliverablesFor(platform)[0] || "" });
            }}>
            {platformOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <select className="select" value={form.deliverable_type} onChange={(e) => setForm({ ...form, deliverable_type: e.target.value })}>
            {deliverablesFor(form.platform).map((d) => <option key={d} value={d}>{t(`deliverable.${d}`, d)}</option>)}
          </select>
        </div>
        {socialPlatforms !== null && socialPlatforms.size === 0 && (
          <div className="hint">{t("profile.connectSocialHint")}</div>
        )}
        <input className="input" style={{ marginTop: 8 }} placeholder={t("profile.packageTitle")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <textarea className="input" style={{ marginTop: 8 }} rows={2} maxLength={2000} placeholder={t("profile.description")}
          value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 8, marginTop: 8 }}>
          <input className="input" inputMode="numeric" placeholder="50000" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value.replace(/\D/g, "") })} />
          <select className="select" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        {floor > 0 && (
          <div className="hint" style={{ color: belowFloor ? "var(--danger)" : undefined }}>
            {t("profile.minPrice", { n: floor, currency: form.currency })}
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 8, marginTop: 8 }}>
          <div>
            <span className="label">{t("profile.packageQuantity")}</span>
            <input className="input" type="number" min={1} max={100} aria-label={t("profile.packageQuantity")}
              value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </div>
          <div>
            <span className="label">{t("profile.packageDuration")}</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <input className="input" inputMode="numeric" placeholder="30" aria-label={t("profile.packageDuration")}
                value={form.durationValue} onChange={(e) => setForm({ ...form, durationValue: e.target.value.replace(/\D/g, "") })} />
              <select className="select" aria-label={t("profile.packageDuration")} value={form.durationUnit}
                onChange={(e) => setForm({ ...form, durationUnit: e.target.value })}>
                <option value="">{t("profile.durationUnitNone")}</option>
                <option value="seconds">{t("profile.durationUnitSeconds")}</option>
                <option value="minutes">{t("profile.durationUnitMinutes")}</option>
                <option value="hours">{t("profile.durationUnitHours")}</option>
              </select>
            </div>
          </div>
        </div>
        {durationMismatch && (
          <div className="hint" style={{ color: "var(--danger)" }}>{t("profile.durationTogether")}</div>
        )}
        <button className="btn btn-ghost" type="submit" style={{ marginTop: 10 }}
          disabled={busy || !form.title || !form.price || belowFloor || qtyInvalid || durationMismatch}>
          + {t("profile.addPackage")}
        </button>
      </form>
    </div>
  );
}

export default function ProfileSetup() {
  const { t } = useTranslation();
  const { userId, token, isAuthenticated } = useAuth();
  /* The account role decides which profile exists on the backend, so the
     stored role is read once and only that form renders. Agencies resolve to
     the business form through isBusinessLike: they buy creator services the
     way businesses do, and get the business UX until agency specific tooling
     exists. */
  const [kind] = useState<Kind>(isBusinessLike(getStoredRole()) ? "business" : "influencer");

  // Influencer fields
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  // Country + city compose into the backend's single `location` string on
  // save; see joinLocation/splitLocation in lib/countries.
  const [locCountry, setLocCountry] = useState("");
  const [locCity, setLocCity] = useState("");
  const [cityOther, setCityOther] = useState(false);
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [followers, setFollowers] = useState("");
  const [rate, setRate] = useState("");
  const [avatarMediaId, setAvatarMediaId] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  // Identity: never shown publicly except languages; see lib/types.
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState("");
  const [languages, setLanguages] = useState<string[]>([]);
  // FAQ answers to the two fixed profile questions.
  const [faqAudience, setFaqAudience] = useState("");
  const [faqBrands, setFaqBrands] = useState("");
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
        const loc = splitLocation(p.location);
        setLocCity(loc.city);
        setLocCountry(loc.country);
        setBio(p.bio ?? "");
        setCategories(p.categories ?? []);
        setFollowers(p.follower_count ? String(p.follower_count) : "");
        setRate(p.rate_card && p.rate_card.post ? String(p.rate_card.post) : "");
        setAvatarMediaId(p.avatar_media_id ?? null);
        setAvatarUrl(p.avatar_url ?? null);
        setBirthDate(p.birth_date ?? "");
        setGender(p.gender ?? "");
        setLanguages(p.languages ?? []);
        setFaqAudience(p.faq?.audience ?? "");
        setFaqBrands(p.faq?.brands ?? "");
      })
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 404)) {
          setError(errorText(err, t));
        }
      });
  }, [userId, t]);

  // Load the existing business profile to prefill the form. The GET endpoint
  // arrived with this branch; before it, saving worked but every visit came up
  // blank. A 404 just means "no profile yet" and is ignored, mirroring the
  // influencer prefill above.
  useEffect(() => {
    if (!userId || kind !== "business") return;
    api<BusinessProfileOut>(`/profiles/business/${userId}`)
      .then((p) => {
        setCompany(p.company_name ?? "");
        setIndustry(p.industry ?? "");
        setDescription(p.description ?? "");
      })
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 404)) {
          setError(errorText(err, t));
        }
      });
  }, [userId, kind, t]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function toggleCategory(c: string) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  function toggleLanguage(code: string) {
    setLanguages((prev) => (prev.includes(code) ? prev.filter((x) => x !== code) : [...prev, code]));
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
            location: joinLocation(locCity, locCountry),
            avatar_media_id: avatarMediaId,
            bio: bio || null,
            categories,
            rate_card: rate ? { post: Number(rate) } : {},
            follower_count: followers ? Number(followers) : null,
            // birth_date goes null when cleared; the API enforces 18+ and the
            // sentence errorText picks for its refusal code lands in the
            // error banner above.
            birth_date: birthDate || null,
            gender: gender || null,
            languages,
            // Only the two fixed answers travel; the questions themselves are
            // product copy that lives in i18n, not user data.
            faq: {
              ...(faqAudience.trim() ? { audience: faqAudience.trim() } : {}),
              ...(faqBrands.trim() ? { brands: faqBrands.trim() } : {})
            }
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
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  const cityList = CITIES[locCountry] ?? [];
  // The droplist covers major cities only. "Other…" flips back to free text so
  // an unusual or missing city never blocks saving, and a saved city outside
  // the list also renders as free text instead of being silently dropped.
  const cityIsFree = cityList.length === 0 || cityOther || (locCity !== "" && !cityList.includes(locCity));

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ margin: 0 }}>{t("profile.title")}</h1>
          <div style={{ display: "flex", gap: 8 }}>
            {/* Profile setup is a leaf page: both roles get an explicit way
                back into the app next to the public-page link. */}
            <Link className="btn btn-ghost" to="/dashboard">{t("nav.dashboard")}</Link>
            {/* Where the settings that are not about the marketplace now live.
                This page is how the market sees you; /account is how you sign
                in — and it is where the delete-account block moved to, so
                anybody who remembers it at the bottom of this form has a way
                to find it. */}
            <Link className="btn btn-ghost" to="/account">{t("nav.account")}</Link>
            {kind === "influencer" && userId && (
              <Link className="btn btn-ghost" to={`/u/${userId}`}>{t("profile.viewPublic")}</Link>
            )}
          </div>
        </div>
        <p className="muted">{t("profile.sub")}</p>

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
                  <label className="label" htmlFor="bd">{t("profile.birthDate")}</label>
                  <input id="bd" type="date" className="input" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
                  <div className="hint">{t("profile.birthDateHint")}</div>
                </div>
                <div className="field">
                  <label className="label" htmlFor="gender">{t("profile.gender")}</label>
                  <select id="gender" className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
                    <option value="">{t("profile.genderNone")}</option>
                    <option value="female">{t("profile.genderFemale")}</option>
                    <option value="male">{t("profile.genderMale")}</option>
                    <option value="other">{t("profile.genderOther")}</option>
                    <option value="prefer_not_to_say">{t("profile.genderNoSay")}</option>
                  </select>
                </div>
                <div className="field">
                  <span className="label">{t("profile.languages")}</span>
                  <div style={{ display: "flex", gap: 18 }}>
                    {/* Language names are written in their own language, so the
                        labels are identical in both locales and stay out of i18n. */}
                    {[{ code: "fr", label: "Français" }, { code: "en", label: "English" }].map((l) => (
                      <label key={l.code} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 14, cursor: "pointer" }}>
                        <input type="checkbox" checked={languages.includes(l.code)} onChange={() => toggleLanguage(l.code)} />
                        {l.label}
                      </label>
                    ))}
                  </div>
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

        {/* Two fixed product questions with free-text answers, saved with the
            main Save button above (the textareas share state with the PUT).
            The FAQ lives in profile setup only: onboarding deliberately stays
            lean, so no FAQ step was added there. */}
        {kind === "influencer" && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3 style={{ marginTop: 0 }}>{t("profile.faqTitle")}</h3>
            <p className="muted" style={{ marginTop: -6, fontSize: 13 }}>{t("profile.faqHint")}</p>
            <div className="field">
              <label className="label" htmlFor="faq-audience">{t("profile.faqAudience")}</label>
              <textarea id="faq-audience" className="input" rows={3} value={faqAudience} onChange={(e) => setFaqAudience(e.target.value)} />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label className="label" htmlFor="faq-brands">{t("profile.faqBrands")}</label>
              <textarea id="faq-brands" className="input" rows={3} value={faqBrands} onChange={(e) => setFaqBrands(e.target.value)} />
            </div>
          </div>
        )}

        {kind === "influencer" && userId && (
          <>
            <SocialSection userId={userId} token={token} />
            <PortfolioSection userId={userId} token={token} />
            <PackagesSection userId={userId} token={token} />
          </>
        )}
      </div>
    </Layout>
  );
}
