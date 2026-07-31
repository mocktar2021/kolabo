import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api, type TokenResponse } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/login", { method: "POST", body: { phone, password } });
      // The response carries the stored role; login persists it so the app
      // renders the right experience even after a logout wiped nothing but
      // the token.
      login(res.access_token, res.role);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
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
          <div className="card">
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={onSubmit}>
              <div className="field">
                <label className="label" htmlFor="phone">{t("auth.phone")}</label>
                <input id="phone" className="input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+229 ..." required />
              </div>
              <div className="field">
                <label className="label" htmlFor="password">{t("auth.password")}</label>
                <input id="password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
              <button className="btn btn-primary btn-block btn-lg" disabled={busy} type="submit">
                {busy ? t("auth.working") : t("auth.submitLogin")}
              </button>
            </form>
          </div>
          <p className="text-center muted" style={{ marginTop: 18 }}>
            {t("auth.needAccount")} <Link to="/register">{t("auth.signupLink")}</Link>
          </p>
        </div>
      </div>
    </Layout>
  );
}
