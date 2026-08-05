/* Every case the caller is party to (GET /payments/disputes/mine).

   One row per dispute rather than per escrow: an escrow can carry several
   over its life now — one withdrawn when two parties talked a
   misunderstanding out, another raised when the work later failed — and
   collapsing them would hide the history that explains the live one.

   The countdown is shown only while the window is still open, because that is
   the only span of time on this screen that anybody can act inside. Once the
   case has queued, the clock has stopped meaning anything and what matters is
   the status chip. */
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { counterpartyNamesByContract, respondTimeLeft } from "../lib/disputes";
import { parseApiDate } from "../lib/orders";
import type { Dispute } from "../lib/types";

export function StatusChip({ status }: { status: Dispute["status"] }) {
  const { t } = useTranslation();
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap" }}>
      {t(`dispute.status_${status}`)}
    </span>
  );
}

/* The window, as the person who has to act on it reads it. Null once it has
   closed, which reads as "délai dépassé" rather than as a negative number. */
export function RespondBy({ respondBy }: { respondBy: string }) {
  const { t } = useTranslation();
  const left = respondTimeLeft(respondBy);
  return (
    <span className="muted" style={{ fontSize: 13 }}>
      {left === null
        ? t("dispute.respondOverdue")
        : left.unit === "hours"
          ? t("dispute.respondInHours", { n: left.n })
          : t("dispute.respondInMinutes", { n: left.n })}
    </span>
  );
}

export default function DisputesPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setDisputes(await api<Dispute[]>("/payments/disputes/mine", { token }));
      // Names are decoration on a list that is readable without them, so a
      // failure here leaves the generic label rather than an error page.
      try {
        setNames(await counterpartyNamesByContract(token));
      } catch {
        setNames({});
      }
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { load(); }, [load]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 820 }}>
        <h1 style={{ marginBottom: 4 }}>{t("dispute.listTitle")}</h1>
        <p className="muted" style={{ marginTop: 0 }}>{t("dispute.listSub")}</p>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : disputes.length === 0 ? (
          <p className="muted">{t("dispute.listEmpty")}</p>
        ) : (
          disputes.map((d) => {
            const name = d.escrow ? names[d.escrow.contract_id] : undefined;
            return (
              <Link
                key={d.id}
                to={`/disputes/${d.id}`}
                className="card"
                style={{ display: "block", marginTop: 12, textDecoration: "none", color: "inherit" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                  <strong>{name || t("dispute.unknownParty")}</strong>
                  <StatusChip status={d.status} />
                </div>
                <div className="muted" style={{ fontSize: 14, marginTop: 6 }}>
                  {t(`dispute.reason_${d.reason}`)}
                  {d.escrow && ` · ${d.escrow.amount} ${d.escrow.currency}`}
                </div>
                <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                  {t("dispute.openedOn", {
                    date: new Date(parseApiDate(d.created_at)).toLocaleDateString()
                  })}
                </div>
                {d.status === "awaiting_response" && (
                  <div style={{ marginTop: 6 }}>
                    <RespondBy respondBy={d.respond_by} />
                  </div>
                )}
              </Link>
            );
          })
        )}
      </div>
    </Layout>
  );
}
