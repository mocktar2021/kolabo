import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import {
  paymentConfig,
  readCheckout,
  startCheckout,
  type PaymentConfig,
  type PaymentIntent,
} from "../lib/checkout";

/* The hosted checkout screen. Reached two ways and it has to handle both:

     /checkout/:contractId          the brand pressed Fund on the contract
     /checkout/return?intent=<id>   FedaPay sent the payer back here

   ONE SCREEN RATHER THAN TWO, because they are the same conversation: "here is
   what you owe" and "here is what happened" are the start and the end of one
   payment, and a separate return page would have to duplicate the polling, the
   error rendering and every terminal state. The route param decides which end
   we are at.

   WHY IT POLLS. A mobile money payment finishes on the payer's handset, not in
   this tab. GET /payments/checkout/{id} re-reads the gateway and creates the
   escrow when the money is confirmed, so polling it is not a status refresh —
   it is the fastest path to a funded contract. The webhook is the safety net
   for the payer who pays and then closes the browser. */

const POLL_MS = 3000;
/* Four minutes. Long enough for someone on a slow network to find their phone,
   read the USSD prompt and type a PIN; short enough that a tab left open
   overnight is not hitting the API every three seconds until the laptop dies.
   Stopping does not cancel anything — the payment is still live at the gateway
   and the webhook still settles it — so the honest thing to show afterwards is
   a manual refresh, not a failure. */
const POLL_LIMIT_MS = 4 * 60 * 1000;

function amount(value: number, currency: string, locale: string): string {
  return `${value.toLocaleString(locale)} ${currency}`;
}

export default function CheckoutPage() {
  const { t, i18n } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const { contractId } = useParams();
  const [params] = useSearchParams();
  const returningIntentId = params.get("intent");

  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef<number>(Date.now());
  const locale = i18n.language.startsWith("en") ? "en-US" : "fr-FR";

  /* A payment is DONE when the escrow exists, not when the status says
     succeeded. The two differ in exactly one case and it is the one that
     matters: the gateway reports money that does not match the contract, the
     backend refuses to fund, and showing a success screen there would tell a
     brand their collaboration is paid for when it is not. */
  const settled = !!intent?.escrow_id;
  const terminal = !!intent && intent.status !== "pending";

  const refresh = useCallback(
    async (id: string) => {
      try {
        setIntent(await readCheckout(id, token));
      } catch (e) {
        /* A poll that fails is not a payment that failed. The gateway may be
           slow, we may be mid-deploy, the phone may be on 2G. Keep the last
           known state on screen and try again rather than turning our own
           outage into a message about the user's money. */
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
          setError(errorText(e, t));
        }
      }
    },
    [token, t]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await paymentConfig();
        if (cancelled) return;
        setConfig(cfg);
        if (returningIntentId) {
          await refresh(returningIntentId);
        } else if (contractId && cfg.enabled) {
          const created = await startCheckout(contractId, token);
          if (cancelled) return;
          setIntent(created);
          /* Straight to the gateway. Same tab, not a popup: a payer on a
             mid-range Android with a blocker installed never sees a popup, and
             the whole flow is designed to come back here through the return
             url anyway. */
          if (created.checkout_url) window.location.href = created.checkout_url;
        }
      } catch (e) {
        if (!cancelled) setError(errorText(e, t));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contractId, returningIntentId, token, refresh, t]);

  useEffect(() => {
    if (!intent || terminal) return;
    const id = window.setInterval(() => {
      if (Date.now() - startedAt.current > POLL_LIMIT_MS) {
        setTimedOut(true);
        window.clearInterval(id);
        return;
      }
      refresh(intent.id);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [intent, terminal, refresh]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  async function retry() {
    if (!intent) return;
    setBusy(true);
    setError(null);
    try {
      const created = await startCheckout(intent.contract_id, token);
      setIntent(created);
      startedAt.current = Date.now();
      setTimedOut(false);
      if (created.checkout_url) window.location.href = created.checkout_url;
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="container page">
        <h1>{t("pay.title")}</h1>
        <p className="muted">{t("pay.subtitle")}</p>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        {config && !config.enabled && !loading && (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>{t("pay.unavailable")}</h3>
            <p className="muted">{t("pay.unavailableHint")}</p>
          </div>
        )}

        {config?.sandbox && config.enabled && (
          <div className="alert alert-info" style={{ marginBottom: 16 }}>
            {t("pay.sandbox")}
          </div>
        )}

        {loading && <p className="muted">{t("pay.opening")}</p>}

        {intent && (
          <div className="card">
            <Row label={t("pay.amount")} value={amount(intent.amount, intent.currency, locale)} />
            <Row label={t("pay.contract")} value={intent.contract_id.slice(0, 8)} />

            {/* Settled. The only screen with a way forward on it. */}
            {settled && (
              <>
                <div className="alert alert-success" style={{ marginTop: 16 }}>
                  <strong>{t("pay.succeeded")}</strong>
                  <div>{t("pay.succeededHint")}</div>
                </div>
                <button
                  className="btn btn-teal"
                  onClick={() => navigate(`/contracts/${intent.contract_id}`)}
                >
                  {t("pay.backToContract")}
                </button>
              </>
            )}

            {/* The gateway took money that does not match the contract, so the
                backend refused to fund and marked the intent failed with this
                reason. Never rendered as an ordinary failure — "nothing was
                charged" would be a lie, money may really have moved — and never
                as a success. It is the one state that hands the payer a
                reference and points them at a human.

                The second half of the condition catches the mirror case: the
                gateway says succeeded but no escrow was created. Same message,
                same remedy. */}
            {(intent.failure_reason === "amount_mismatch" ||
              (intent.status === "succeeded" && !settled)) && (
              <div className="alert alert-error" style={{ marginTop: 16 }}>
                <strong>{t("pay.mismatch")}</strong>
                <div>{t("pay.mismatchHint")}</div>
                <div style={{ marginTop: 8, fontFamily: "monospace" }}>
                  {t("pay.reference")}: {intent.id}
                </div>
              </div>
            )}

            {intent.status === "pending" && (
              <>
                <div className="alert alert-info" style={{ marginTop: 16 }}>
                  <strong>{t("pay.waiting")}</strong>
                  <div>{t("pay.waitingHint")}</div>
                </div>
                {intent.checkout_url && (
                  <a className="btn btn-ghost" href={intent.checkout_url}>
                    {t("pay.reopen")}
                  </a>
                )}
                {timedOut && (
                  <button
                    className="btn btn-ghost"
                    style={{ marginLeft: 8 }}
                    onClick={() => refresh(intent.id)}
                  >
                    {t("pay.reopen")}
                  </button>
                )}
              </>
            )}

            {(intent.status === "failed" || intent.status === "canceled") &&
              intent.failure_reason !== "amount_mismatch" && (
                <>
                  <div className="alert alert-error" style={{ marginTop: 16 }}>
                    <strong>
                      {intent.status === "canceled" ? t("pay.canceled") : t("pay.failed")}
                    </strong>
                    <div>{t("pay.failedHint")}</div>
                  </div>
                  <button className="btn btn-teal" disabled={busy} onClick={retry}>
                    {t("pay.retry")}
                  </button>
                </>
              )}
          </div>
        )}
      </div>
    </Layout>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
