import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { errorText } from "../lib/errorMessages";
import {
  getPayoutMethod,
  paymentConfig,
  payoutModeLabel,
  payoutModes,
  savePayoutMethod,
  type PaymentConfig,
  type PayoutMethod,
} from "../lib/checkout";

/* Where a creator tells us to send their money.

   THIS SCREEN IS LOAD-BEARING, which is not obvious from how small it is.
   payments/payouts.py cannot send a mobile money payout without a network and
   a number, so a creator with no row here has their release land in
   `awaiting_method`: the escrow still releases, the commission is still taken,
   the money is still owed and visible — but nothing moves until they fill this
   in, and then the retry sweep pays them. Without this page a web-only creator
   has no way to ever reach that state, and every release they earn strands.

   THE NETWORK IS A DROPDOWN, NOT A GUESS. We ask which mobile money network the
   number belongs to instead of inferring it from the prefix, because inference
   is wrong often enough to matter: operator ranges in Benin and Côte d'Ivoire
   have been reassigned more than once, and number portability moves a
   subscriber between networks without changing a digit. A payout sent down the
   wrong network does not bounce cleanly — it fails late, or lands in a wallet
   the recipient does not check. One extra field here is much cheaper than a
   support conversation about money that appears to have vanished.

   The options come from the API rather than from a constant in this file, so
   the closed set the backend validates against and the set the form offers can
   never disagree. */

export default function PayoutMethodPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();

  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [saved, setSaved] = useState<PayoutMethod | null>(null);
  const [country, setCountry] = useState("");
  const [modes, setModes] = useState<string[]>([]);
  const [mode, setMode] = useState("");
  const [phone, setPhone] = useState("");
  const [accountName, setAccountName] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cfg, existing] = await Promise.all([
          paymentConfig(),
          /* A creator who has never set one gets null, not a 404 — so a first
             visit is an empty form rather than an error banner. */
          getPayoutMethod(token),
        ]);
        if (cancelled) return;
        setConfig(cfg);
        setSaved(existing);
        /* Preselect what they already chose; otherwise the first country we
             can actually pay out to. Deliberately NOT read from their profile
             country: the two can legitimately differ — a creator living in
             Cotonou may hold a Togolese wallet — and the wallet is what this
             form is about. */
        const initial = existing?.country || cfg.countries[0] || "";
        setCountry(initial);
        if (existing) setAccountName(existing.account_name || "");
      } catch (e) {
        if (!cancelled) setError(errorText(e, t));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, t]);

  const loadModes = useCallback(
    async (code: string) => {
      if (!code) {
        setModes([]);
        setMode("");
        return;
      }
      try {
        const list = await payoutModes(code);
        setModes(list);
        /* Keep the saved network only if it is valid in the chosen country.
           Carrying `orange_ci` over to a Togo selection would submit a value
           the backend refuses — the form should not be able to build a request
           that cannot succeed. */
        setMode((current) => (list.includes(current) ? current : list[0] || ""));
      } catch (e) {
        setError(errorText(e, t));
      }
    },
    [t]
  );

  useEffect(() => {
    if (!country) return;
    /* Seed from the saved row the first time, so someone reopening this page
       sees their own choice selected rather than the alphabetical first. */
    if (saved && saved.country === country) setMode(saved.mode);
    loadModes(country);
  }, [country, saved, loadModes]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  async function submit() {
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      const updated = await savePayoutMethod(token, {
        country,
        mode,
        phone: phone.trim(),
        account_name: accountName.trim() || null,
      });
      setSaved(updated);
      setDone(true);
      /* Cleared on success. The number is never echoed back by the API — only
         a masked form of it — so leaving the field populated would show a
         value the server does not confirm it stored. */
      setPhone("");
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = !busy && !!country && !!mode && phone.trim().length >= 8;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <h1>{t("pay.payoutTitle")}</h1>
        <p className="muted">{t("pay.payoutHint")}</p>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}
        {done && (
          <div className="alert alert-success" style={{ marginBottom: 16 }}>
            {t("pay.payoutSaved")}
          </div>
        )}

        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : config && !config.enabled ? (
          <div className="card">
            <h3 style={{ marginTop: 0 }}>{t("pay.unavailable")}</h3>
            <p className="muted" style={{ marginBottom: 0 }}>
              {t("pay.unavailableHint")}
            </p>
          </div>
        ) : (
          <>
            {saved && (
              <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span className="muted">{t("pay.payoutCurrent")}</span>
                  <strong>
                    {payoutModeLabel(saved.mode)} · {saved.phone_masked}
                  </strong>
                </div>
              </div>
            )}

            {!saved && (
              <div className="alert alert-info" style={{ marginBottom: 16 }}>
                {t("pay.payoutMissing")}
              </div>
            )}

            <div className="card">
              <label className="label" htmlFor="payout-country">
                {t("pay.payoutCountry")}
              </label>
              <select
                id="payout-country"
                className="input"
                value={country}
                disabled={busy}
                onChange={(e) => setCountry(e.target.value)}
              >
                {(config?.countries || []).map((code) => (
                  <option key={code} value={code}>
                    {t(`country.${code}`, code)}
                  </option>
                ))}
              </select>

              <label className="label" style={{ marginTop: 12 }} htmlFor="payout-mode">
                {t("pay.payoutNetwork")}
              </label>
              <select
                id="payout-mode"
                className="input"
                value={mode}
                disabled={busy || modes.length === 0}
                onChange={(e) => setMode(e.target.value)}
              >
                {modes.map((m) => (
                  <option key={m} value={m}>
                    {payoutModeLabel(m)}
                  </option>
                ))}
              </select>

              <label className="label" style={{ marginTop: 12 }} htmlFor="payout-phone">
                {t("pay.payoutPhone")}
              </label>
              <input
                id="payout-phone"
                className="input"
                inputMode="tel"
                value={phone}
                disabled={busy}
                onChange={(e) => setPhone(e.target.value)}
              />

              <label className="label" style={{ marginTop: 12 }} htmlFor="payout-name">
                {t("pay.payoutName")}
              </label>
              <input
                id="payout-name"
                className="input"
                value={accountName}
                disabled={busy}
                onChange={(e) => setAccountName(e.target.value)}
              />

              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <button className="btn btn-teal" disabled={!canSubmit} onClick={submit}>
                  {t("pay.payoutSave")}
                </button>
                <Link className="btn btn-ghost" to="/earnings">
                  {t("nav.earnings", "Earnings")}
                </Link>
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
