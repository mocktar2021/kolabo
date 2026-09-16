import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PasswordInput } from "../components/PasswordInput";
import { Layout } from "../components/Layout";
import { GoogleDivider, GoogleSignInButton } from "../components/GoogleSignInButton";
import { api, type RegisterResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { COUNTRIES } from "../lib/countries";
import { ROLES, useAuth, type Role } from "../lib/auth";
import { googleConfigured, signInWithGoogle } from "../lib/googleSignIn";

export default function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [params] = useSearchParams();
  const initialRole = (params.get("role") as Role) || "influencer";
  /* Referral attribution is best-effort: the code rides along silently and
     the backend ignores anything it does not recognise, so a stale or
     mistyped link never blocks a registration. */
  const referralCode = params.get("ref");

  const [role, setRole] = useState<Role>(ROLES.includes(initialRole) ? initialRole : "influencer");
  const [country, setCountry] = useState("BJ");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const roleLabel: Record<Role, { t: string; d: string }> = {
    influencer: { t: t("auth.roleInfluencer"), d: t("auth.roleInfluencerD") },
    business: { t: t("auth.roleBusiness"), d: t("auth.roleBusinessD") },
    agency: { t: t("auth.roleAgency"), d: t("auth.roleAgencyD") }
  };

  /* THE SAME REGISTRATION, WITHOUT THE PASSWORD AND WITHOUT THE CODE.
     POST /auth/google creates the account and returns a token in one call, so
     there is no /verify step to send anybody to: Google has just proved the
     mailbox that an OTP would have proved, and the backend marks the row
     verified from birth rather than sending a code nothing would read.

     THE TWO ANSWERS RIDE ALONG ON THE FIRST CALL, which is why this screen
     never shows the second step the login screen has to. Role and country are
     already on this form, so sending them saves a round trip and a question
     the person has just answered. auth_google_profile_required is therefore
     not reachable from here, and is not handled: if it ever were, it would
     mean these two fields had stopped being sent, and a silent recovery would
     hide that.

     Attribution rides along too. A creator who brought somebody in should not
     lose the credit because that person tapped the Google button instead of
     filling in the form. */
  async function onGoogle(credential: string) {
    setError(null);
    setBusy(true);
    try {
      const res = await signInWithGoogle(
        credential,
        { role, country_code: country },
        referralCode
      );
      login(res.access_token, res.role);
      navigate("/dashboard");
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: {
          email,
          password,
          country_code: country,
          role,
          ...(referralCode ? { referral_code: referralCode } : {})
        }
      });
      localStorage.setItem("kolabo_role", role);
      navigate(`/verify?email=${encodeURIComponent(email)}`);
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
            <h1>{t("auth.registerTitle")}</h1>
            <p className="muted">{t("auth.registerSub")}</p>
            {referralCode && <p className="hint">{t("auth.referredHint")}</p>}
          </div>
          <div className="card">
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={onSubmit}>
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
                <label className="label" htmlFor="country">{t("auth.country")}</label>
                <select id="country" className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label" htmlFor="email">{t("auth.email")}</label>
                <input id="email" className="input" type="email" autoComplete="email" inputMode="email"
                  value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <div className="field">
                <label className="label" htmlFor="password">{t("auth.password")}</label>
                <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
                <div className="hint">8+ characters.</div>
              </div>
              <button className="btn btn-primary btn-block btn-lg" disabled={busy} type="submit">
                {busy ? t("auth.working") : t("auth.submitRegister")}
              </button>
            </form>
            {/* UNDER THE FORM RATHER THAN OVER IT, which is the opposite of
                where a sign in button usually goes and is deliberate. The role
                and the country this button sends are collected in the fields
                above it, so a button at the top of the card would sign people
                up as whatever the defaults happen to say. Both draw nothing at
                all when VITE_GOOGLE_CLIENT_ID is unset. */}
            <GoogleDivider />
            <GoogleSignInButton onCredential={onGoogle} text="signup_with" />
            {googleConfigured() && (
              <div className="hint" style={{ textAlign: "center" }}>{t("auth.googleUsesAbove")}</div>
            )}
          </div>
          <p className="text-center muted" style={{ marginTop: 18 }}>
            {t("auth.haveAccount")} <Link to="/login">{t("auth.loginLink")}</Link>
          </p>
        </div>
      </div>
    </Layout>
  );
}
