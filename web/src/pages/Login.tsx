import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PasswordInput } from "../components/PasswordInput";
import { Layout } from "../components/Layout";
import { api, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";

/* Mirrors MIN_PASSWORD_LENGTH in backend/app/modules/auth/schemas.py. The
   reset endpoint enforces the same floor registration does, deliberately: a
   reset that accepted a weaker password would be a way to walk an account
   DOWN to four characters, which is not a recovery flow. */
const MIN_PASSWORD_LENGTH = 8;

/* Getting back in, inline on the login page and in two steps.

   WHY IT LIVES HERE rather than on a route of its own: the person who needs
   it is already looking at a password field that is not working. A separate
   page would mean leaving the screen, and coming back to it is the part
   people do not do.

   THE ONE THING THIS FLOW MUST NOT DO. POST /auth/password-reset/request
   answers exactly the same 202 with exactly the same body whether or not the
   address is registered, and that is the entire security property of the
   endpoint rather than an implementation detail. Two answers would turn it
   into a free "is this person on Kolabo?" lookup for anyone holding a list of
   addresses — which in these markets discloses who is earning on the platform
   to whoever asks, including the people a user is specifically trying not to
   be found by. So the confirmation below says "if that address is registered"
   and never "a code has been sent": the client genuinely does not know, and
   writing copy that implies it does would leak through the UI what the API
   refuses to leak.

   The confirm step is not skipped when the request "succeeds" for the same
   reason: there is nothing to skip on. Every failure of the confirm step —
   unknown address, wrong code, expired code, already-spent code — comes back
   as the same 400, so it gets one sentence too. */
function PasswordReset({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = password !== "" && password.length < MIN_PASSWORD_LENGTH;
  const mismatch = confirm !== "" && confirm !== password;
  const ready = code.length === 6 && password.length >= MIN_PASSWORD_LENGTH && confirm === password;

  async function request(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/request", { method: "POST", body: { email: email.trim() } });
      setStep("code");
    } catch (err) {
      /* 429 is the ONE case this endpoint is not silent about, and the
         backend says why: every request sends an email that costs something,
         and swallowing the limit behind a 202 would leave a genuinely
         rate-limited user waiting for a message that is never coming.
         It arrives as auth_reset_too_many now, so errorText says it in the
         reader's language without this screen having to know the status. */
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        body: { email: email.trim(), code, new_password: password }
      });
      onDone();
    } catch (err) {
      // One sentence for all four ways this fails, and the backend keeps it
      // that way: every one of them raises auth_reset_code_invalid. Telling
      // them apart — here or there — would hand back the fact the request
      // step refuses to disclose.
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: 20 }}>{t("reset.title")}</h2>
      {error && <div className="alert alert-error">{error}</div>}

      {step === "email" ? (
        <form onSubmit={request}>
          <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("reset.intro")}</p>
          <div className="field">
            <label className="label" htmlFor="reset-email">{t("reset.phoneLabel")}</label>
            <input id="reset-email" className="input" type="email" autoComplete="email" inputMode="email"
              value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || !email.trim()}>
            {busy ? t("auth.working") : t("reset.request")}
          </button>
          <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 10 }} onClick={onCancel}>
            {t("reset.back")}
          </button>
        </form>
      ) : (
        <form onSubmit={submit}>
          {/* Conditional, not affirmative. See the note above the component. */}
          <div className="alert alert-info">{t("reset.sent")}</div>
          <p className="muted" style={{ fontSize: 13, marginTop: -6 }}>{t("reset.sentHint")}</p>
          <div className="field">
            <label className="label" htmlFor="reset-code">{t("reset.codeLabel")}</label>
            <input id="reset-code" className="input" inputMode="numeric" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required />
          </div>
          <div className="field">
            <label className="label" htmlFor="reset-password">{t("reset.newPassword")}</label>
            <PasswordInput id="reset-password" value={password}
              onChange={(e) => setPassword(e.target.value)} required />
            {tooShort && <div className="hint" style={{ color: "var(--danger)" }}>{t("reset.tooShort", { n: MIN_PASSWORD_LENGTH })}</div>}
          </div>
          <div className="field">
            <label className="label" htmlFor="reset-confirm">{t("reset.confirmPassword")}</label>
            <PasswordInput id="reset-confirm" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} required />
            {mismatch && <div className="hint" style={{ color: "var(--danger)" }}>{t("reset.mismatch")}</div>}
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || !ready}>
            {busy ? t("auth.working") : t("reset.confirm")}
          </button>
          <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 10 }}
            onClick={() => { setStep("email"); setError(null); }}>
            {t("reset.changePhone")}
          </button>
        </form>
      )}
    </div>
  );
}

export default function Login() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState(false);
  // Set by a completed reset, cleared by nothing: the person is about to sign
  // in with the password they just chose, and the line above the form is what
  // tells them it worked.
  const [resetDone, setResetDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
      // The response carries the stored role; login persists it so the app
      // renders the right experience even after a logout wiped nothing but
      // the token.
      login(res.access_token, res.role);
      navigate("/dashboard");
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="auth-wrap">
        <div className="container-narrow auth-card">
          <div className="auth-head">
            <h1>{t("auth.loginTitle")}</h1>
            <p className="muted">{t("auth.loginSub")}</p>
          </div>
          {resetting ? (
            <PasswordReset
              onCancel={() => setResetting(false)}
              /* Back to the login form with the success line above it, rather
                 than signing them in silently. The reset endpoint returns no
                 token — on purpose: proving you hold the address is how you
                 get a new password, not how you get a session — and typing it
                 once is also the confirmation that it is the one they
                 meant. */
              onDone={() => { setResetting(false); setResetDone(true); setPassword(""); }}
            />
          ) : (
            <div className="card">
              {resetDone && <div className="alert alert-success">{t("reset.success")}</div>}
              {error && <div className="alert alert-error">{error}</div>}
              <form onSubmit={onSubmit}>
                <div className="field">
                  <label className="label" htmlFor="email">{t("auth.email")}</label>
                  <input id="email" className="input" type="email" autoComplete="email" inputMode="email"
                    value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
                <div className="field">
                  <label className="label" htmlFor="password">{t("auth.password")}</label>
                  <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                </div>
                <button className="btn btn-primary btn-block btn-lg" disabled={busy} type="submit">
                  {busy ? t("auth.working") : t("auth.submitLogin")}
                </button>
              </form>
              {/* Under the button and not beside the password field: it is the
                  second thing to try, and putting it next to the input invites
                  the click before the attempt. */}
              <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 10 }}
                onClick={() => { setResetting(true); setError(null); setResetDone(false); }}>
                {t("reset.forgot")}
              </button>
            </div>
          )}
          <p className="text-center muted" style={{ marginTop: 18 }}>
            {t("auth.needAccount")} <Link to="/register">{t("auth.signupLink")}</Link>
          </p>
        </div>
      </div>
    </Layout>
  );
}
