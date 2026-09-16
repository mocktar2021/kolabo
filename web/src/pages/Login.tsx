import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PasswordInput } from "../components/PasswordInput";
import { Layout } from "../components/Layout";
import { GoogleDivider, GoogleSignInButton } from "../components/GoogleSignInButton";
import { api, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { ROLES, useAuth, type Role } from "../lib/auth";
import { COUNTRIES } from "../lib/countries";
import {
  googleConfigured,
  looksLikeWrongPassword,
  needsProfileAnswers,
  signInWithGoogle
} from "../lib/googleSignIn";

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

/* The two things Google cannot tell us, asked only when they are needed.

   WHY THIS EXISTS ON THE LOGIN SCREEN AND NOT ON THE REGISTER ONE. A new
   person can arrive at either. The register form has already collected a role
   and a country by the time its Google button is reachable, so it sends both
   on the first call and this panel never opens there. Nothing on a login form
   asks either question, and nothing should: it is a login form. So the first
   call goes without them, and a Google address that has no Kolabo account
   behind it comes back 400 auth_google_profile_required, which is NOT an
   error. It is the first leg of a two step flow, and this is the second leg.

   THE SAME TOKEN IS SENT AGAIN, not a fresh one. A Google ID token is good for
   about an hour, so there is no need to reopen the chooser, and reopening it
   would make somebody prove who they are twice for one sign up. If it has
   expired anyway, the second call answers auth_google_token_invalid and says
   so here, where the cancel button is.

   THE ROLE AND THE COUNTRY ARE THE REGISTER FORM'S, deliberately: ROLES comes
   from lib/auth and COUNTRIES from lib/countries, which are the same two lists
   Register.tsx draws from. A second set would be a second place for a market
   to open in and a role to be added. */
function GoogleQuestions({
  busy,
  error,
  onSubmit,
  onCancel
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (role: Role, country: string) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [role, setRole] = useState<Role>("influencer");
  const [country, setCountry] = useState("BJ");

  const roleLabel: Record<Role, { t: string; d: string }> = {
    influencer: { t: t("auth.roleInfluencer"), d: t("auth.roleInfluencerD") },
    business: { t: t("auth.roleBusiness"), d: t("auth.roleBusinessD") },
    agency: { t: t("auth.roleAgency"), d: t("auth.roleAgencyD") }
  };

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, fontSize: 20 }}>{t("auth.googleAskTitle")}</h2>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("auth.googleAskIntro")}</p>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="field">
        <span className="label">{t("auth.role")}</span>
        <div className="segment">
          {ROLES.map((r) => (
            <div
              key={r}
              className={`segment-option ${role === r ? "selected" : ""}`}
              onClick={() => setRole(r)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setRole(r); }}
            >
              <div className="t">{roleLabel[r].t}</div>
              <div className="d">{roleLabel[r].d}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="field">
        <label className="label" htmlFor="google-country">{t("auth.country")}</label>
        <select id="google-country" className="select" value={country}
          onChange={(e) => setCountry(e.target.value)}>
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>{c.name}</option>
          ))}
        </select>
      </div>
      <button className="btn btn-primary btn-block" type="button" disabled={busy}
        onClick={() => onSubmit(role, country)}>
        {busy ? t("auth.working") : t("auth.googleAskSubmit")}
      </button>
      <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 10 }}
        onClick={onCancel}>
        {t("auth.googleAskCancel")}
      </button>
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
  /* The token held between the two legs of the Google flow. Non-null means the
     address has no account yet and the panel above is open over the form. */
  const [googleToken, setGoogleToken] = useState<string | null>(null);
  /* Whether the LAST refusal was the vague one. The backend answers
     auth_bad_credentials both for a wrong password and for an account created
     through Google, which has no usable password at all, and it refuses to
     tell them apart on purpose: a distinct code would say which addresses are
     registered here to anybody with a list of them. So the client does not
     guess either. It points at the button, beside the field, and only after an
     attempt has actually failed, so nobody is told about Google who did not
     need telling. */
  const [maybeGoogleOnly, setMaybeGoogleOnly] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMaybeGoogleOnly(false);
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
      // See maybeGoogleOnly above for why this is a hint and not a sentence
      // the server sent.
      setMaybeGoogleOnly(looksLikeWrongPassword(err) && googleConfigured());
    } finally {
      setBusy(false);
    }
  }

  /* ONE ENDPOINT FOR SIGNING IN AND SIGNING UP, because the client cannot know
     which it is doing: whether a Google address already has a Kolabo account
     is a question only the server can answer, and asking it separately would
     also be an "is this person on Kolabo" oracle for anyone with a list of
     addresses.

     So there are exactly three outcomes worth handling. A token and a role,
     which is a sign in. auth_google_profile_required, which is not an error
     and opens the panel. Anything else, which errorText already has a sentence
     for in both languages. */
  async function signIn(credential: string, role?: Role, country?: string) {
    setError(null);
    setMaybeGoogleOnly(false);
    setBusy(true);
    try {
      const res = await signInWithGoogle(
        credential,
        role && country ? { role, country_code: country } : undefined
      );
      login(res.access_token, res.role);
      navigate("/dashboard");
    } catch (err) {
      if (needsProfileAnswers(err)) {
        // Held so the second call can send the SAME token. See GoogleQuestions.
        setGoogleToken(credential);
        setError(null);
        return;
      }
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
          ) : googleToken ? (
            /* Over the form rather than beside it, like the reset flow above
               and for the same reason: there is exactly one thing to do next
               and a form underneath it would be two. */
            <GoogleQuestions
              busy={busy}
              error={error}
              onSubmit={(role, country) => { void signIn(googleToken, role, country); }}
              onCancel={() => { setGoogleToken(null); setError(null); }}
            />
          ) : (
            <div className="card">
              {resetDone && <div className="alert alert-success">{t("reset.success")}</div>}
              {error && <div className="alert alert-error">{error}</div>}
              {/* FIRST IN THE CARD, unlike the register screen, where it is
                  last. Nothing on this form feeds it: the first call carries
                  the token and nothing else, and the two questions are asked
                  afterwards and only if the address turns out to be new. Both
                  of these draw nothing when VITE_GOOGLE_CLIENT_ID is unset. */}
              <GoogleSignInButton onCredential={(credential) => { void signIn(credential); }} />
              <GoogleDivider />
              <form onSubmit={onSubmit}>
                <div className="field">
                  <label className="label" htmlFor="email">{t("auth.email")}</label>
                  <input id="email" className="input" type="email" autoComplete="email" inputMode="email"
                    value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
                <div className="field">
                  <label className="label" htmlFor="password">{t("auth.password")}</label>
                  <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                  {/* Beside the field that just failed, which is where
                      somebody is already looking, and only after it has
                      failed. See maybeGoogleOnly. */}
                  {maybeGoogleOnly && <div className="hint">{t("auth.googleWrongPassword")}</div>}
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
