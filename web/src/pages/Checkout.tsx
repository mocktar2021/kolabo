import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import {
  collectionNetworkLabel,
  collectionNetworks,
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
   for the payer who pays and then closes the browser.

   TWO WAYS TO START, AND THE SERVER DECIDES WHICH. Until now this screen
   started a checkout the moment it mounted and sent the browser to whatever
   url came back. That only works for a gateway with a hosted page, and the
   method most brands in the launch markets use does not have one: FeexPay's
   mobile money endpoint pushes a payment request to a handset and returns
   nothing to open. So the screen now asks GET /payments/collection-networks
   first:

     []        no picker. Start immediately and redirect, exactly as before.
     non-empty ask for a network and a number FIRST, then start. There is
               nowhere to send the browser, so the payer never leaves.

   THE LIST COMES FROM THE SERVER, not from a constant here, because it is
   the routed gateway's own closed set. A hardcoded copy drifts the first
   time a provider adds an operator, and the failure is a brand unable to
   pick the wallet they actually hold. */

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
  /* null while unknown, [] for a gateway that needs no picker. The three
     states are distinct on purpose: rendering a form from a list we have not
     loaded yet would flash an empty dropdown on every mount. */
  const [networks, setNetworks] = useState<string[] | null>(null);
  const [network, setNetwork] = useState("");
  const [phone, setPhone] = useState("");
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
          /* ASKED BEFORE ANYTHING IS STARTED, which is the whole point. A
             gateway that needs a network cannot be given one after the
             request has gone. A failure here is treated as "no picker"
             rather than as a dead screen: the worst case is the old
             behaviour, which is a redirect attempt that the backend refuses
             with a readable sentence. */
          let available: string[] = [];
          try {
            available = await collectionNetworks(token);
          } catch {
            available = [];
          }
          if (cancelled) return;
          setNetworks(available);
          if (available.length > 0) {
            /* Stop here and render the form. Nothing has been started, no
               money is in flight, and the payer has not been sent anywhere. */
            return;
          }
          const created = await startCheckout(contractId, token);
          if (cancelled) return;
          setIntent(created);
          /* Straight to the gateway. Same tab, not a popup: a payer on a
             mid-range Android with a blocker installed never sees a popup, and
             the whole flow is designed to come back here through the return
             url anyway. */
          if (created.checkout_url) window.location.href = created.checkout_url;
        } else if (contractId && cfg.mock_payments) {
          /* No gateway configured, and the backend says this is not
             production — so fund through the original one-step mock path and
             go straight back to the contract.

             THIS EXISTS BECAUSE REPOINTING THE FUND BUTTON HERE BROKE LOCAL
             DEV. A developer with no FedaPay account previously funded an
             escrow instantly through the mock provider; afterwards they landed
             on this screen being told payments were unavailable in their
             country, with no way to reach deliver -> approve -> release at all.

             The backend decides whether this is allowed, not the client:
             mock_payments is false in production, where funding refuses
             instead of quietly holding an escrow against money nobody
             collected. */
          await api("/payments/escrow/fund", {
            method: "POST",
            token,
            body: { contract_id: contractId },
          });
          if (cancelled) return;
          navigate(`/contracts/${contractId}`, { replace: true });
          return;
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
  }, [contractId, returningIntentId, token, refresh, navigate, t]);

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

  /* Send the payment request to a handset. No redirect, because there is
     nowhere to go: what comes back is a pending intent and the payer's phone
     is already asking them to approve it. */
  async function sendPrompt() {
    if (!contractId) return;
    if (!network) {
      setError(t("pay.fundPickNetwork"));
      return;
    }
    if (!phone.trim()) {
      setError(t("pay.fundNeedPhone"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await startCheckout(contractId, token, {
        network,
        phone: phone.trim(),
      });
      setIntent(created);
      startedAt.current = Date.now();
      setTimedOut(false);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!intent) return;
    /* BACK TO THE FORM RATHER THAN STRAIGHT BACK TO THE SAME WALLET. A
       prompt that failed usually failed for a reason the payer can fix, and
       the most common one is the number: a wallet with no balance, or the
       wrong one of the two they hold. Resending to the same number without
       asking repeats the failure and spends another request. */
    if (intent.payer_action === "device_prompt") {
      setIntent(null);
      setTimedOut(false);
      setError(null);
      return;
    }
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

        {config && !config.enabled && !config.mock_payments && !loading && (
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

        {/* The funding form. Shown only when the routed gateway asked for a
            network, and only while nothing has been started: once a request
            is out, the card below takes over and the payer's phone is
            already waiting on them. */}
        {!loading && !intent && networks && networks.length > 0 && (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>{t("pay.fundHow")}</h3>
            <p className="muted">{t("pay.fundHowHint")}</p>

            <label className="label" htmlFor="pay-network">
              {t("pay.fundNetwork")}
            </label>
            <select
              id="pay-network"
              className="input"
              value={network}
              disabled={busy}
              onChange={(e) => setNetwork(e.target.value)}
            >
              <option value="">{t("pay.fundNetworkPlaceholder")}</option>
              {networks.map((code) => (
                <option key={code} value={code}>
                  {collectionNetworkLabel(code)}
                </option>
              ))}
            </select>

            <label className="label" htmlFor="pay-phone" style={{ marginTop: 12 }}>
              {t("pay.fundPhone")}
            </label>
            <input
              id="pay-phone"
              className="input"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={phone}
              disabled={busy}
              onChange={(e) => setPhone(e.target.value)}
            />
            <p className="muted" style={{ marginTop: 6 }}>
              {t("pay.fundPhoneHint")}
            </p>

            <button
              className="btn btn-teal"
              style={{ marginTop: 16 }}
              disabled={busy}
              onClick={sendPrompt}
            >
              {t("pay.fundSubmit")}
            </button>
          </div>
        )}

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

            {/* Pending, and the two shapes read differently on purpose.

                A REDIRECT says "waiting for your payment" and offers the url
                again, because the payer has been somewhere and may have lost
                the tab. A PROMPT says where to look, names the wallet it went
                to, and offers no link, because there is nothing to reopen and
                a dead button on this screen is worse than no button. */}
            {intent.status === "pending" && intent.payer_action === "device_prompt" && (
              <>
                <div className="alert alert-info" style={{ marginTop: 16 }}>
                  <strong>{t("pay.promptSent")}</strong>
                  <div>{t("pay.promptSentHint")}</div>
                  {intent.payer_network && (
                    <div style={{ marginTop: 8 }}>
                      {t("pay.promptSentTo")} {collectionNetworkLabel(intent.payer_network)}
                    </div>
                  )}
                </div>
                {/* Only once polling has given up. Before that the page is
                    still updating itself and a "change the number" button
                    invites somebody to abandon a request that is about to
                    succeed. */}
                {timedOut && (
                  <>
                    <button className="btn btn-ghost" onClick={() => refresh(intent.id)}>
                      {t("pay.reopen")}
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ marginLeft: 8 }}
                      onClick={retry}
                    >
                      {t("pay.promptChange")}
                    </button>
                  </>
                )}
              </>
            )}

            {intent.status === "pending" && intent.payer_action !== "device_prompt" && (
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
