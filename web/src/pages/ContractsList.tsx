import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Contract } from "../lib/types";

export default function ContractsList() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Contract[]>("/contracts/mine", { token })
      .then(setContracts)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [token]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page">
        <h1>{t("contract.listTitle")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("contract.listSub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : contracts.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("contract.listEmpty")}</p></div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {contracts.map((c) => (
                <Link key={c.id} to={`/contracts/${c.id}`} className="card" style={{ textDecoration: "none", color: "inherit", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>{c.rate_amount} {c.rate_currency}</strong>
                    <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>{c.timeline_days}d - {c.language.toUpperCase()}</div>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: c.fully_signed ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                    {t(`contract.status_${c.status}`, c.status)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
