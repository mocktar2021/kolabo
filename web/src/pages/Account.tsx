import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PasswordInput } from "../components/PasswordInput";
import { Layout } from "../components/Layout";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { googleConfigured } from "../lib/googleSignIn";

/* Mirrors MIN_PASSWORD_LENGTH in backend/app/modules/auth/schemas.py. Checked
   here as well so a short password is met as a hint under the field rather
   than as a 422 after the form has been filled in twice. */
const MIN_PASSWORD_LENGTH = 8;

/* What GET /auth/me answers (MeOut in backend/app/modules/auth/schemas.py).
   Declared on the page rather than in lib/types.ts because exactly one screen
   reads it — the same call ProfileSetup makes for its own BusinessProfileOut.

   The email address and the phone number are both on this payload, and this
   is the ONE place in the system where that is true: everywhere else contact
   details are deliberately withheld, because handing them to the other side
   of a deal is how a negotiation leaves the platform. Here the reader IS the
   subject, and a settings screen that cannot show you which address you sign
   in with is a settings screen you cannot use.

   `phone` IS NULLABLE. users.phone is nullable and signup no longer collects
   it, so an account that has never added one answers null. Every reader below
   has to say so rather than print an empty box. */
type AccountOut = {
  id: string;
  email: string;
  phone: string | null;
  role: string;
  country_code: string;
  is_verified: boolean;
  /* WHETHER A GOOGLE ACCOUNT REACHES THIS ONE, and deliberately not which.
     MeOut carries a boolean because Google's `sub` is a stable identifier for
     a person across every site that has ever seen one of their tokens, and no
     client has a use for the value.

     WHAT IT DOES NOT SAY, which is the whole difficulty on this screen: it
     does not say whether the account ALSO has a usable password. An account
     created through Google has a password hash of a secret nobody has ever
     seen, and an account that registered with a password and later signed in
     with Google has both doors. Both answer true here, nothing on /auth/me
     tells them apart, and the settings screen has to be right for both. See
     ProofField below for what that argument settles. */
  google_linked: boolean;
  created_at: string;
};

type Tab = "details" | "payment" | "notifications" | "account";

/* PROOF THAT THE CALLER OWNS THIS ACCOUNT, in whichever of the two forms it
   has. The backend calls this re-authentication and states the rule once, in
   auth.account.require_reauth: a current password, or a freshly verified
   Google ID token for this account's own address, and EXACTLY ONE of the two.
   A bearer token is not enough on its own, because it says a session exists
   and cannot tell an owner from whoever picked the handset up. */
type Proof = { kind: "password"; secret: string } | { kind: "google"; secret: string };

/* THE TWO ENDPOINTS SPELL THE PASSWORD FIELD DIFFERENTLY, and nothing in the
   type system says so. PATCH /auth/me takes `current_password` (AccountPatch)
   and DELETE /auth/me takes `password` (DeleteAccountRequest). Sending the
   wrong one is not a 422 either: pydantic drops the unknown key, the request
   arrives carrying no proof at all, and require_reauth answers 403
   auth_reauth_required, which reads like a rejected password. Both spellings
   live here so there is one place to be wrong in. */
function patchProof(proof: Proof): Record<string, string> {
  return proof.kind === "password"
    ? { current_password: proof.secret }
    : { google_token: proof.secret };
}

function deleteProof(proof: Proof): Record<string, string> {
  return proof.kind === "password" ? { password: proof.secret } : { google_token: proof.secret };
}

/* The proof control, and the decision this screen turns on.

   THE RULE. An account that is NOT linked to Google sees exactly what it saw
   before: a password field, and nothing else. An account that IS linked is
   offered GOOGLE FIRST, with the password reachable behind one plain button
   that says so.

   WHY THAT ORDER RATHER THAN SHOWING BOTH. google_linked cannot distinguish an
   account created through Google, which has no usable password at all, from
   one that registered with a password and later signed in with Google, which
   has two ways in. Defaulting to the password would put a field in front of
   the first of those that it can never fill, which is the one thing the
   backend work shipped to prevent: before AccountPatch and
   DeleteAccountRequest learned to take a Google token, such an account could
   not change its own address or close itself at all. Defaulting to Google is
   the choice that always works for a linked account, and the second button is
   what keeps the account that genuinely has a password from losing it.

   WHY THE UNLINKED ACCOUNT IS NOT OFFERED GOOGLE. require_reauth would in fact
   accept a Google token for any account whose address matches, linked or not.
   But this client has no way to know whether the person holds a Google account
   at that address, so the button would be a coin flip: most would open a
   chooser, pick the only address they have, and be refused for a reason the
   screen cannot explain. A control that usually fails is worse than no control.

   TWO STEPS ON THE GOOGLE BRANCH, ON PURPOSE. The credential arrives and is
   held; the form is submitted afterwards by its own button. Signing in with
   Google must not be the gesture that deletes an account. */
function ProofField({
  id,
  me,
  passwordLabel,
  value,
  onChange
}: {
  id: string;
  me: AccountOut;
  passwordLabel: string;
  value: Proof | null;
  onChange: (next: Proof | null) => void;
}) {
  const { t } = useTranslation();
  /* Both halves are required. The link can be real while this build carries no
     client id, in which case Google is not on offer here any more than it is
     on the login screen, and the password is the only door left. */
  const canUseGoogle = me.google_linked && googleConfigured();
  const [usePassword, setUsePassword] = useState(!canUseGoogle);

  if (usePassword) {
    return (
      <div className="field">
        <label className="label" htmlFor={id}>{passwordLabel}</label>
        <PasswordInput
          id={id}
          value={value?.kind === "password" ? value.secret : ""}
          onChange={(e) => onChange(e.target.value ? { kind: "password", secret: e.target.value } : null)}
        />
        {canUseGoogle && (
          <button type="button" className="btn btn-ghost" style={{ marginTop: 8, padding: "6px 12px", fontSize: 13 }}
            onClick={() => { onChange(null); setUsePassword(false); }}>
            {t("account.proofUseGoogle")}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="field">
      <span className="label">{t("account.proofLabel")}</span>
      {value?.kind === "google" ? (
        <>
          <div className="alert alert-success">{t("account.proofGoogleReady")}</div>
          <button type="button" className="btn btn-ghost" style={{ padding: "6px 12px", fontSize: 13 }}
            onClick={() => onChange(null)}>
            {t("account.proofGoogleRedo")}
          </button>
        </>
      ) : (
        <GoogleSignInButton
          text="continue_with"
          onCredential={(credential) => onChange({ kind: "google", secret: credential })}
        />
      )}
      <button type="button" className="btn btn-ghost" style={{ marginTop: 8, padding: "6px 12px", fontSize: 13 }}
        onClick={() => { onChange(null); setUsePassword(true); }}>
        {t("account.proofUsePassword")}
      </button>
    </div>
  );
}

/* Whether Google reaches this account, said once and changed nowhere.

   THERE IS NO DISCONNECT BUTTON AND THAT IS NOT AN OVERSIGHT. No endpoint
   clears users.google_sub: not PATCH /auth/me, which cannot carry the column,
   and not anything else. A button here would have to either lie or call
   something that does not exist, so the row is informational and says as much.
   The day the backend grows a way to unlink, the control belongs here. */
function GooglePanel({ me }: { me: AccountOut }) {
  const { t } = useTranslation();
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("account.googleTitle")}</h3>
      <p style={{ fontSize: 14.5, marginTop: -4 }}>
        {me.google_linked ? t("account.googleLinkedYes") : t("account.googleLinkedNo")}
      </p>
      {me.google_linked && (
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>{t("account.googleNoDisconnect")}</p>
      )}
    </div>
  );
}

/* Changing the address you sign in with.

   Email addresses really do change — a work address left behind with a job, a
   provider abandoned — so this has to be self-service rather than a support
   ticket. What it must never become is a way to take somebody else's account,
   which is the whole reason the current password is on the form. */
function EmailForm({ me, onChanged }: { me: AccountOut; onChanged: (next: AccountOut) => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [email, setEmail] = useState(me.email);
  const [proof, setProof] = useState<Proof | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const next = email.trim();
  const changed = next !== "" && next !== me.email;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!changed || !proof) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      // The response is the account as it now stands, so the page takes it
      // rather than refetching: a screen that shows the old address for one
      // more render is a screen somebody presses save on twice.
      const updated = await api<AccountOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { ...patchProof(proof), email: next }
      });
      onChanged(updated);
      setProof(null);
      setDone(true);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{t("account.emailTitle")}</h3>
      {/* The same argument either way. The variant names what this account can
          actually pay with, so a person who has no password is not told that
          one is the price. */}
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>
        {me.google_linked && googleConfigured()
          ? t("account.emailWhyProof")
          : t("account.emailWhyPassword")}
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {done && <div className="alert alert-success">{t("account.emailSaved")}</div>}
      <form onSubmit={submit}>
        <div className="field">
          <label className="label" htmlFor="acc-email-current">{t("account.emailCurrent")}</label>
          <input id="acc-email-current" className="input" value={me.email} readOnly disabled />
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-email-new">{t("account.emailNew")}</label>
          <input id="acc-email-new" className="input" type="email" autoComplete="email" inputMode="email"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <ProofField id="acc-email-password" me={me} passwordLabel={t("account.passwordCurrent")}
          value={proof} onChange={setProof} />
        <button className="btn btn-primary" type="submit" disabled={busy || !changed || !proof}>
          {busy ? t("auth.working") : t("account.emailSave")}
        </button>
      </form>
    </div>
  );
}

/* Adding or changing the number the money goes to.

   NOT AN IDENTITY FORM ANY MORE, and the copy beside it says so. A number is
   optional here, signup does not ask for one, and the only thing it does is
   receive a Mobile Money payout. The current password is still required, for
   a reason that survived the flip intact: redirecting somebody's payouts is
   worth as much to an attacker as taking their login was. */
function PhoneForm({ me, onChanged }: { me: AccountOut; onChanged: (next: AccountOut) => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [phone, setPhone] = useState(me.phone ?? "");
  const [proof, setProof] = useState<Proof | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const next = phone.trim();
  const changed = next !== "" && next !== (me.phone ?? "");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!changed || !proof) return;
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
        body: { ...patchProof(proof), phone: next }
      });
      onChanged(updated);
      setProof(null);
      setDone(true);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("account.phoneTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>
        {me.google_linked && googleConfigured()
          ? t("account.phoneWhyProof")
          : t("account.phoneWhyPassword")}
      </p>
      {error && <div className="alert alert-error">{error}</div>}
      {done && <div className="alert alert-success">{t("account.phoneSaved")}</div>}
      <form onSubmit={submit}>
        <div className="field">
          <label className="label" htmlFor="acc-phone-current">{t("account.phoneCurrent")}</label>
          <input id="acc-phone-current" className="input" value={me.phone ?? t("account.phoneNone")} readOnly disabled />
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-phone-new">{t("account.phoneNew")}</label>
          <input id="acc-phone-new" className="input" value={phone} placeholder="+229 ..."
            onChange={(e) => setPhone(e.target.value)} />
        </div>
        <ProofField id="acc-phone-password" me={me} passwordLabel={t("account.passwordCurrent")}
          value={proof} onChange={setProof} />
        <button className="btn btn-primary" type="submit" disabled={busy || !changed || !proof}>
          {busy ? t("auth.working") : t("account.phoneSave")}
        </button>
      </form>
    </div>
  );
}

/* Changing the password, from the inside. Proof is required for the same
   reason it is on the two forms above and for a second one: this is the change
   a stolen session would make first.

   AND IT IS THE ONLY WAY A GOOGLE CREATED ACCOUNT EVER ACQUIRES A PASSWORD.
   Such an account has a hash of a secret nobody has ever seen, so the old
   shape of this form, which demanded a current password, was a door with no
   handle on the inside: no password, therefore no way to set one. Sending
   new_password with a Google token is what AccountPatch.google_token exists
   for, and the proof control below is what makes it reachable. */
function PasswordForm({ me }: { me: AccountOut }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [proof, setProof] = useState<Proof | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const tooShort = password !== "" && password.length < MIN_PASSWORD_LENGTH;
  const mismatch = confirm !== "" && confirm !== password;
  const ready = proof !== null && password.length >= MIN_PASSWORD_LENGTH && confirm === password;

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
        body: { ...patchProof(proof), new_password: password }
      });
      setProof(null);
      setPassword("");
      setConfirm("");
      setDone(true);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("account.passwordTitle")}</h3>
      {/* Says "if", because the server tells us the account is linked and not
          whether it also has a password. See AccountOut.google_linked. */}
      {me.google_linked && googleConfigured() && (
        <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("account.passwordMaybeFirst")}</p>
      )}
      {error && <div className="alert alert-error">{error}</div>}
      {done && <div className="alert alert-success">{t("account.passwordSaved")}</div>}
      <form onSubmit={submit}>
        <ProofField id="acc-pass-current" me={me} passwordLabel={t("account.passwordCurrent")}
          value={proof} onChange={setProof} />
        <div className="field">
          <label className="label" htmlFor="acc-pass-new">{t("account.passwordNew")}</label>
          <PasswordInput id="acc-pass-new" value={password}
            onChange={(e) => setPassword(e.target.value)} />
          {tooShort && <div className="hint" style={{ color: "var(--danger)" }}>{t("account.passwordTooShort", { n: MIN_PASSWORD_LENGTH })}</div>}
        </div>
        <div className="field">
          <label className="label" htmlFor="acc-pass-confirm">{t("account.passwordConfirm")}</label>
          <PasswordInput id="acc-pass-confirm" value={confirm}
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
   showing on its own, because "why did I get an email about a contract" is a
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
   say what deletion actually costs). Its two refusals — a wrong password and
   an account with transaction history — arrive as auth_password_incorrect and
   auth_account_has_history, so errorText names which one it was. This screen
   used to pick a sentence from the status code, which said the same thing in
   more lines and could only ever manage one message per status.

   MOVED HERE FROM ProfileSetup. Closing an account is not a step in filling
   one in — it sat at the bottom of the profile form purely because that was
   the only settings-shaped page that existed, and a creator scrolling to add
   a package should not pass it. It stays last on this tab for the same
   reason it was last there: it must never compete with the everyday
   actions. */
function DangerZone({ me }: { me: AccountOut }) {
  const { t } = useTranslation();
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [proof, setProof] = useState<Proof | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!proof) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/me", { method: "DELETE", token, body: deleteProof(proof) });
      // The account is gone; drop the local session through the provider and
      // land on the marketing homepage.
      logout();
      navigate("/");
    } catch (err) {
      setError(errorText(err, t));
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
          {/* The one place the two endpoints disagree about a field name, which
              deleteProof is there to absorb: DELETE /auth/me reads `password`
              and PATCH reads `current_password`. */}
          <ProofField id="del-pass" me={me} passwordLabel={t("danger.confirmPassword")}
            value={proof} onChange={setProof} />
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn-ghost" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
              disabled={!proof || busy} onClick={onDelete}>
              {busy ? t("auth.working") : t("danger.deleteForever")}
            </button>
            <button type="button" className="btn btn-ghost"
              onClick={() => { setConfirming(false); setProof(null); setError(null); }}>
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
   an oversight: every account signs in with an email address, has a password,
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
              <EmailForm me={me} onChanged={setMe} />
              <PhoneForm me={me} onChanged={setMe} />
              <PasswordForm me={me} />
              {/* Last on the tab, under the two credentials it is about. It is
                  a statement rather than a control, so it must not sit above
                  the things somebody came here to change. */}
              <GooglePanel me={me} />
            </>
          )
        )}

        {tab === "payment" && <PaymentPanel />}
        {tab === "notifications" && <NotificationsPanel />}

        {tab === "account" && (
          <>
            <SessionPanel />
            {/* Waits for /auth/me now, because the delete panel has to know
                whether this account can prove itself with Google before it
                decides what to put in front of somebody. */}
            {loading ? (
              <p className="muted" style={{ marginTop: 16 }}>{t("discover.loading")}</p>
            ) : me ? (
              <DangerZone me={me} />
            ) : null}
          </>
        )}
      </div>
    </Layout>
  );
}
