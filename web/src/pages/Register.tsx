import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api, type RegisterResponse } from "../lib/api";
import { COUNTRIES } from "../lib/countries";

const ROLES = ["influencer", "business", "agency"] as const;
type Role = (typeof ROLES)[number];

export default function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialRole = (params.get("role") as Role) || "influencer";

  const [role, setRole] = useState<Role>(ROLES.includes(initialRole) ? initialRole : "influencer");
  const [country, setCountry] = useState("BJ");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const roleLabel: Record<Role, { t: string; d: string }> = {
    influencer: { t: t("auth.roleInfluencer"), d: t("auth.roleInfluencerD") },
    business: { t: t("auth.roleBusiness"), d: t("auth.roleBusinessD") },
    agency: { t: t("auth.roleAgency"), d: t("auth.roleAgencyD") }
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: { phone, password, country_code: country, role }
      });
      localStorage.setItem("kolabo_role", role);
      navigate(`/verify?phone=${encodeURIComponent(phone)}`);
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
            <h1>{t("auth.registerTitle")}</h1>
            <p className="muted">{t("auth.registerSub")}</p>
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
                <label className="label" htmlFor="phone">{t("auth.phone")}</label>
                <input id="phone" className="input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+229 ..." required />
              </div>
              <div className="field">
                <label className="label" htmlFor="password">{t("auth.password")}</label>
                <input id="password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
                <div className="hint">8+ characters.</div>
              </div>
              <button className="btn btn-primary btn-block btn-lg" disabled={busy} type="submit">
                {busy ? t("auth.working") : t("auth.submitRegister")}
              </button>
            </form>
          </div>
          <p className="text-center muted" style={{ marginTop: 18 }}>
            {t("auth.haveAccount")} <Link to="/login">{t("auth.loginLink")}</Link>
          </p>
        </div>
      </div>
    </Layout>
  );
}
