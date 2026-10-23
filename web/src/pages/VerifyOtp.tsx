import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { isBusinessLike, useAuth } from "../lib/auth";

export default function VerifyOtp() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const email = params.get("email") || "";
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/verify-otp", { method: "POST", body: { email, code } });
      // The response's role is the backend truth; it overwrites whatever
      // registration stored locally.
      login(res.access_token, res.role);
      // Creators go straight into profile setup; business-like accounts
      // (businesses and agencies) go to the dashboard.
      navigate(isBusinessLike(res.role) ? "/dashboard" : "/onboarding");
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
            <h1>{t("auth.otpTitle")}</h1>
            <p className="muted">{t("auth.otpSub")}</p>
          </div>
          <div className="card">
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={onSubmit}>
              <div className="field">
                <label className="label" htmlFor="code">{t("auth.otpCode")}</label>
                <input
                  id="code"
                  className="input"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  placeholder="000000"
                  style={{ letterSpacing: "0.4em", fontSize: 20, textAlign: "center" }}
                  required
                />
              </div>
              <button className="btn btn-teal btn-block btn-lg" disabled={busy || code.length < 6} type="submit">
                {busy ? t("auth.working") : t("auth.otpSubmit")}
              </button>
            </form>
          </div>
        </div>
      </div>
    </Layout>
  );
}
