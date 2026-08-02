import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";

/* Mirrors MIN_PASSWORD_LENGTH in backend/app/modules/auth/schemas.py. Checked
   here as well so a short password is met as a hint under the field rather
   than as a 422 after the form has been filled in twice. */
const MIN_PASSWORD_LENGTH = 8;

/* What GET /auth/me answers (MeOut in backend/app/modules/auth/schemas.py).
   Declared on the page rather than in lib/types.ts because exactly one screen
   reads it — the same call ProfileSetup makes for its own BusinessProfileOut.

   The phone is on this payload, and it is the ONE place in the system where
   that is true: everywhere else a phone number is deliberately withheld,
   because handing it to the other side of a deal is how a negotiation leaves
   the platform. Here the reader IS the subject, and a settings screen that
   cannot show you which number you sign in with is a settings screen you
   cannot use. */
type AccountOut = {
  id: string;
  phone: string;
  role: string;
  country_code: string;
  is_verified: boolean;
  created_at: string;
};

type Tab = "details" | "payment" | "notifications" | "account";

/* Errors mapped by STATUS CODE and never by matching the detail string. The
   API's sentences are written in English for the API and can be reworded at
   any time; a French UI that matched on their text would go silent the day
   they are. The same rule the campaign actions and the delete block follow.

   The three codes PATCH /auth/me can answer that this screen has a sentence
   for:

     409  the new phone belongs to another account — the only thing that code
          means on this endpoint.
     403  the current password is wrong. Not 400 and not 401: account.py
          raises HTTP_403_FORBIDDEN for a failed verify_password, exactly as
          DELETE /auth/me does, and the delete block below has always mapped
          it that way.
     401  neither of those. It means the bearer token itself is gone or
          expired, which is a different problem, and saying "wrong password"
          to somebody whose session lapsed would send them hunting for a
          mistake they did not make.

   400 is left to the fallback on purpose: on this endpoint it means "you sent
   neither a phone nor a password", which both forms below already prevent, so
   inventing a French sentence for it would be inventing a state. */
function accountErrorKey(status: number): string | null {
  if (status === 409) return "account.errPhoneTaken";
  if (status === 403) return "account.errWrongPassword";
  if (status === 401) return "account.errSession";
  return null;
}

/* Changing the number you sign in with.

   Phone numbers really do change here — a better tariff, a lost handset, a
   move between countries — so this has to be self-service rather than a
   support ticket. What it must never become is a way to take somebody else's
   number, which is the whole reason the current password is on the form. */
function PhoneForm({ me, onChanged }: { me: AccountOut; onChanged: (next: AccountOut) => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [phone, setPhone] = useState(me.phone);
  const [currentPassword, setCurrentPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const next = phone.trim();
  const changed = next !== "" && next !== me.phone;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!changed || !currentPassword) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      // The response is the account as it now stands, so the page takes it
      // rather than refetching: a screen that shows the old number for one
      // more render is a screen somebody presses save on twice.
      const updated = await api<AccountOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { current_password: currentPassword, phone: next }
      });
      onChanged(updated);
      setCurrentPassword("");
      setDone(true);
    } catch (err) {
      const key = err instanceof ApiError ? accountErrorKey(err.status) : null;
      setError(key ? t(key) : err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t("account.phoneTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("account.phoneWhyPassword")}</p>
      {error && <div className="alert alert-error">{error}</div>}
      {done && <div className="alert alert-success">{t("account.phoneSaved")}</div>}
      <form onSubmit={submit}>
        <div className="field">
          <label className="label" htmlFor="acc-phone-current">{t("account.phoneCurrent")}</label>
          <input id="acc-phone-current" className="input" value={me.phone} readOnly disabled />
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-phone-new">{t("account.phoneNew")}</label>
          <input id="acc-phone-new" className="input" value={phone} placeholder="+229 ..."
            onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-phone-password">{t("account.passwordCurrent")}</label>
          <input id="acc-phone-password" className="input" type="password" value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)} />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy || !changed || !currentPassword}>
          {busy ? t("auth.working") : t("account.phoneSave")}
        </button>
      </form>
    </div>
  );
}

/* Changing the password, from the inside. The current password is required
   for the same reason it is on the phone form and for a second one: this is
   the change a stolen session would make first. */
function PasswordForm() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const tooShort = password !== "" && password.length < MIN_PASSWORD_LENGTH;
  const mismatch = confirm !== "" && confirm !== password;
  const ready = currentPassword !== "" && password.length >= MIN_PASSWORD_LENGTH && confirm === password;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api<AccountOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { current_password: currentPassword, new_password: password }
      });
      setCurrentPassword("");
      setPassword("");
      setConfirm("");
      setDone(true);
    } catch (err) {
      const key = err instanceof ApiError ? accountErrorKey(err.status) : null;
      setError(key ? t(key) : err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("account.passwordTitle")}</h3>
      {error && <div className="alert alert-error">{error}</div>}
      {done && <div className="alert alert-success">{t("account.passwordSaved")}</div>}
      <form onSubmit={submit}>
        <div className="field">
          <label className="label" htmlFor="acc-pass-current">{t("account.passwordCurrent")}</label>
          <input id="acc-pass-current" className="input" type="password" value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-pass-new">{t("account.passwordNew")}</label>
          <input id="acc-pass-new" className="input" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} />
          {tooShort && <div className="hint" style={{ color: "var(--danger)" }}>{t("account.passwordTooShort", { n: MIN_PASSWORD_LENGTH })}</div>}
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-pass-confirm">{t("account.passwordConfirm")}</label>
          <input id="acc-pass-confirm" className="input" type="password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} />
          {mismatch && <div className="hint" style={{ color: "var(--danger)" }}>{t("account.passwordMismatch")}</div>}
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy || !ready}>
          {busy ? t("auth.working") : t("account.passwordSave")}
        </button>
      </form>
    </div>
  );
}

/* Payment, explained rather than collected.

   THERE IS DELIBERATELY NO FORM HERE, and no card fields either. Nothing in
   this system stores a payment instrument: money moves by Mobile Money
   through the escrow the buyer funds, and there is no endpoint that accepts a
   payout destination. A form would therefore do one of two dishonest things —
   collect details nobody reads, or imply an automatic payout that does not
   exist yet — and the person it would mislead is the one waiting to be paid.
   The panel says what happens today and what is coming; it gets its inputs
   the day the provider integration gives them somewhere to go. */
function PaymentPanel() {
  const { t } = useTranslation();
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t("account.paymentTitle")}</h3>
      <p style={{ fontSize: 14.5 }}>{t("account.paymentBody")}</p>
      <p className="muted" style={{ fontSize: 13.5, margin: 0 }}>{t("account.paymentPending")}</p>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 0 }}>{t("account.paymentMeanwhile")}</p>
    </div>
  );
}

/* What the platform notifies about, listed and READ-ONLY.

   There are no notification preferences server-side — notify() writes a row
   for every event and nothing consults a setting — so this panel has no
   switches. Rendering some anyway would be the worst version of this screen:
   somebody turns one off, the next notification arrives regardless, and they
   stop believing anything the product tells them. The list itself is worth
   showing on its own, because "why did I get an SMS about a contract" is a
   real question with an answer.

   The entries mirror the notify() call sites in the backend modules; they
   become checkboxes the day there is a preferences table to check them
   against. */
function NotificationsPanel() {
  const { t } = useTranslation();
  const items = [
    "account.notifInvitation",
    "account.notifProposal",
    "account.notifContract",
    "account.notifPayment",
    "account.notifDispute",
    "account.notifMessage",
    "account.notifSecurity"
  ];
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t("account.notifTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("account.notifIntro")}</p>
      <ul style={{ margin: "0 0 14px", paddingLeft: 18, fontSize: 14, display: "grid", gap: 6 }}>
        {items.map((key) => <li key={key}>{t(key)}</li>)}
      </ul>
      <p className="muted" style={{ fontSize: 13, margin: 0 }}>{t("account.notifReadOnly")}</p>
    </div>
  );
}

/* Account deletion, behind an inline confirm (no window.confirm: destroying
   an account deserves friction, and a native dialog cannot be translated or
   say what deletion actually costs). Errors are mapped from the status code,
   never parsed from the English detail: 403 wrong password, 409 transaction
   history.

   MOVED HERE FROM ProfileSetup. Closing an account is not a step in filling
   one in — it sat at the bottom of the profile form purely because that was
   the only settings-shaped page that existed, and a creator scrolling to add
   a package should not pass it. It stays last on this tab for the same
   reason it was last there: it must never compete with the everyday
   actions. */
function DangerZone() {
  const { t } = useTranslation();
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!password) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/me", { method: "DELETE", token, body: { password } });
      // The account is gone; drop the local session through the provider and
      // land on the marketing homepage.
      logout();
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setError(t("danger.wrongPassword"));
      else if (err instanceof ApiError && err.status === 409) setError(t("danger.hasHistory"));
      else setError(err instanceof Error ? err.message : "Error");
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16, borderColor: "var(--danger)" }}>
      <h3 style={{ marginTop: 0, fontSize: 16, color: "var(--danger)" }}>{t("danger.title")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("danger.explain")}</p>
      {error && <div className="alert alert-error">{error}</div>}
      {!confirming ? (
        <button type="button" className="btn btn-ghost" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
          onClick={() => setConfirming(true)}>
          {t("danger.delete")}
        </button>
      ) : (
        <div>
          <div className="field">
            <label className="label" htmlFor="del-pass">{t("danger.confirmPassword")}</label>
            <input id="del-pass" className="input" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn-ghost" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
              disabled={!password || busy} onClick={onDelete}>
              {busy ? t("auth.working") : t("danger.deleteForever")}
            </button>
            <button type="button" className="btn btn-ghost"
              onClick={() => { setConfirming(false); setPassword(""); setError(null); }}>
              {t("onb.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* Signing out, and the one honest thing to say about it: nothing is lost.
   People hesitate over a logout button on a device they share, which is
   exactly the device they most need it on. */
function SessionPanel() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t("account.sessionTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("account.sessionDesc")}</p>
      <button type="button" className="btn btn-ghost" onClick={() => { logout(); navigate("/"); }}>
        {t("account.signOut")}
      </button>
    </div>
  );
}

/* The account, for every role.

   Not asked the creator/brand question anywhere on this page, and that is not
   an oversight: every account signs in with a phone number, has a password,
   is notified about things, and may want to leave. The two sides of the
   market differ in what they DO on Kolabo, not in what an account is. */
export default function AccountPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [tab, setTab] = useState<Tab>("details");
  const [me, setMe] = useState<AccountOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let live = true;
    api<AccountOut>("/auth/me", { token })
      .then((data) => { if (live) setMe(data); })
      .catch(() => { if (live) setError(t("account.loadFailed")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token, t]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const tabs: { id: Tab; label: string }[] = [
    { id: "details", label: t("account.tabDetails") },
    { id: "payment", label: t("account.tabPayment") },
    { id: "notifications", label: t("account.tabNotifications") },
    { id: "account", label: t("account.tabAccount") }
  ];

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <h1 style={{ margin: 0 }}>{t("account.title")}</h1>
        <p className="muted">{t("account.sub")}</p>

        <div role="tablist" style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "18px 0" }}>
          {tabs.map((it) => (
            <button key={it.id} type="button" role="tab" aria-selected={tab === it.id}
              className={`btn ${tab === it.id ? "btn-primary" : "btn-ghost"}`}
              style={{ padding: "7px 14px", fontSize: 13.5 }}
              onClick={() => setTab(it.id)}>
              {it.label}
            </button>
          ))}
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {tab === "details" && (
          loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : !me ? null : (
            <>
              <PhoneForm me={me} onChanged={setMe} />
              <PasswordForm />
            </>
          )
        )}

        {tab === "payment" && <PaymentPanel />}
        {tab === "notifications" && <NotificationsPanel />}

        {tab === "account" && (
          <>
            <SessionPanel />
            <DangerZone />
          </>
        )}
      </div>
    </Layout>
  );
}
