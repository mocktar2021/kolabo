import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { ApiError } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { formatAmount } from "../lib/money";
import { useAuth } from "../lib/auth";
import {
  paymentConfig,
  readCheckout,
  startCheckout,
  type PaymentConfig,
  type PaymentIntent,
} from "../lib/checkout";
/* Side-effect import: registers the pay.* copy on the i18n instance. See the
   header of that file for why this feature's strings are a runtime bundle
   instead of forty more keys in the 55 KB strings.ts. */
import "../lib/paymentStrings";
import {
  Banner,
  Card,
  GhostButton,
  Hint,
  PrimaryButton,
  Screen,
  SectionTitle,
  Subtitle,
} from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const POLL_MS = 3000;
/* Four minutes, the same ceiling the web screen uses. Long enough for someone
   on a slow network to find their phone, read the USSD prompt and type a PIN;
   short enough that a screen left open in the background is not hitting the
   API every three seconds until the battery dies. Stopping cancels nothing —
   the payment is still live at the gateway and the webhook still settles it —
   so what we show afterwards is a manual re-check, not a failure. */
const POLL_LIMIT_MS = 4 * 60 * 1000;

/* kolabo://payment-return once this is a real build (an exp:// URL under Expo
   Go). Handed to the gateway as the return url AND to openAuthSessionAsync as
   the scheme to watch for — the pair is what gets the payer back inside the
   app rather than stranded on a gateway page. */
const RETURN_URL = Linking.createURL("payment-return");

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

/* The hosted checkout screen: the brand pressed Fund on a signed contract and
   everything from "here is what you owe" to "here is what happened" occurs
   here.

   WHY IT POLLS. A mobile money payment finishes on the payer's handset, not in
   this process. GET /payments/checkout/{id} re-reads the gateway and creates
   the escrow when the money is confirmed, so polling it is not a status
   refresh — it is the fastest path to a funded contract. */
export default function CheckoutScreen({ navigation, route }: AppScreenProps<"Checkout">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const { contractId } = route.params;

  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef(Date.now());

  /* The intent is kept in a ref as well as in state because the two events
     that most want to re-read it — the browser session resolving and the app
     returning to the foreground — fire outside the render that registered
     them, and a closure over the state value would poll a stale id (or none at
     all, on the first pass). */
  const current = useRef<PaymentIntent | null>(null);
  const apply = useCallback((next: PaymentIntent) => {
    current.current = next;
    setIntent(next);
  }, []);

  const refresh = useCallback(
    async (id: string) => {
      try {
        apply(await readCheckout(id, token));
      } catch (e) {
        /* A poll that fails is not a payment that failed. The gateway may be
           slow, we may be mid-deploy, the handset may be on 2G. Keep the last
           known state on screen and try again rather than turning our own
           outage into a message about the user's money. Only a refusal that
           will never resolve itself is worth showing. */
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) {
          setError(errorText(e, t));
        }
      }
    },
    [apply, token, t]
  );

  const openCheckout = useCallback(
    async (url: string) => {
      /* openAuthSessionAsync rather than openBrowserAsync: it watches for our
         own scheme and dismisses itself the moment the gateway redirects to
         it, so the payer lands back on this screen instead of hunting for a
         way out of a browser tab. */
      await WebBrowser.openAuthSessionAsync(url, RETURN_URL);
      /* However the session ended — redirected, dismissed, cancelled — the
         payer is looking at this screen again and the money may have moved
         while they were away. Read once now instead of making them watch a
         spinner until the next tick. */
      const cur = current.current;
      if (cur) await refresh(cur.id);
    },
    [refresh]
  );

  /* ONE CHECKOUT PER VISIT, enforced outside React's state. The effect below
     closes over `t` and over memoised callbacks, and a language change
     re-creates all of them; without this guard that re-run would POST a second
     payment intent for a contract that is already being paid for, and the
     payer would be looking at a checkout url the app has stopped polling. */
  const startedFor = useRef<string | null>(null);

  useEffect(() => {
    if (startedFor.current === contractId) return;
    startedFor.current = contractId;
    let cancelled = false;
    void (async () => {
      try {
        const cfg = await paymentConfig();
        if (cancelled) return;
        setConfig(cfg);
        /* No gateway, no checkout. Starting one would 400 and the honest
           answer is the unavailable card below. */
        if (!cfg.enabled) return;
        const created = await startCheckout(contractId, token, { returnUrl: RETURN_URL });
        if (cancelled) return;
        apply(created);
        /* Out of the loading state BEFORE the browser opens: the await below
           lasts as long as the payer is on the gateway, and coming back to a
           spinner would hide the state we spent that time collecting. */
        setLoading(false);
        if (created.checkout_url) await openCheckout(created.checkout_url);
      } catch (e) {
        if (!cancelled) setError(errorText(e, t));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contractId, token, t, apply, openCheckout]);

  const terminal = !!intent && intent.status !== "pending";

  useEffect(() => {
    if (!intent || terminal) return;
    const id = setInterval(() => {
      if (Date.now() - startedAt.current > POLL_LIMIT_MS) {
        setTimedOut(true);
        clearInterval(id);
        return;
      }
      void refresh(intent.id);
    }, POLL_MS);
    return () => clearInterval(id);
  }, [intent, terminal, refresh]);

  useEffect(() => {
    /* A payer switches to their mobile money app to approve the debit and
       comes straight back. Reading on "active" means they see the outcome the
       instant they return rather than up to three seconds later, which on this
       screen is the difference between "it worked" and "did it work?". */
    const sub = AppState.addEventListener("change", (state) => {
      const cur = current.current;
      if (state === "active" && cur && cur.status === "pending") void refresh(cur.id);
    });
    return () => sub.remove();
  }, [refresh]);

  async function retry() {
    const cur = current.current;
    if (!cur) return;
    setBusy(true);
    setError(null);
    try {
      const created = await startCheckout(cur.contract_id, token, { returnUrl: RETURN_URL });
      apply(created);
      startedAt.current = Date.now();
      setTimedOut(false);
      if (created.checkout_url) await openCheckout(created.checkout_url);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* A payment is DONE when the escrow exists, not when the status says
     succeeded. The two differ in exactly one case and it is the one that
     matters: the gateway reports money that does not match the contract, the
     backend refuses to fund, and a success screen there would tell a brand
     their collaboration is paid for when it is not. */
  const settled = !!intent?.escrow_id;
  /* The second half catches the mirror case — gateway says succeeded, no
     escrow was created. Same message, same remedy. */
  const mismatch =
    !!intent &&
    (intent.failure_reason === "amount_mismatch" ||
      (intent.status === "succeeded" && !settled));
  const checkoutUrl = intent?.checkout_url ?? null;

  return (
    <Screen loading={loading}>
      <Subtitle>{t("pay.subtitle")}</Subtitle>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {config && !config.enabled ? (
        <Card>
          <SectionTitle>{t("pay.unavailable")}</SectionTitle>
          <Hint>{t("pay.unavailableHint")}</Hint>
        </Card>
      ) : null}

      {config?.enabled && config.sandbox ? <Banner kind="info">{t("pay.sandbox")}</Banner> : null}

      {intent ? (
        <Card>
          <Row
            label={t("pay.amount")}
            value={formatAmount(intent.amount, intent.currency, i18n.language)}
          />
          <Row label={t("pay.contract")} value={intent.contract_id.slice(0, 8)} />
          <View style={{ height: space(3) }} />

          {settled ? (
            <>
              <Banner kind="success">
                <Text style={styles.strong}>{t("pay.succeeded")}</Text>
                {"\n"}
                {t("pay.succeededHint")}
              </Banner>
              <PrimaryButton
                title={t("pay.backToContract")}
                onPress={() => navigation.navigate("ContractDetail", { id: intent.contract_id })}
              />
            </>
          ) : null}

          {mismatch ? (
            <>
              <Banner kind="error">
                <Text style={styles.strong}>{t("pay.mismatch")}</Text>
                {"\n"}
                {t("pay.mismatchHint")}
              </Banner>
              {/* Selectable because this string is the only thing a support
                  agent can act on, and re-typing a UUID off a phone screen
                  into a chat is how it arrives wrong. */}
              <Text style={styles.reference} selectable>
                {t("pay.reference")}: {intent.id}
              </Text>
            </>
          ) : null}

          {intent.status === "pending" ? (
            <>
              <Banner kind="info">
                <Text style={styles.strong}>{t("pay.waiting")}</Text>
                {"\n"}
                {t("pay.waitingHint")}
              </Banner>
              {checkoutUrl ? (
                <GhostButton title={t("pay.reopen")} onPress={() => void openCheckout(checkoutUrl)} />
              ) : null}
              {/* The poll gave up, the payment did not. A manual re-check is
                  the honest offer here — the gateway may still confirm, and
                  the webhook settles it either way. */}
              {timedOut ? (
                <View style={{ marginTop: space(2) }}>
                  <GhostButton title={t("common.retry")} onPress={() => void refresh(intent.id)} />
                </View>
              ) : null}
            </>
          ) : null}

          {(intent.status === "failed" || intent.status === "canceled") && !mismatch ? (
            <>
              <Banner kind="error">
                <Text style={styles.strong}>
                  {intent.status === "canceled" ? t("pay.canceled") : t("pay.failed")}
                </Text>
                {"\n"}
                {t("pay.failedHint")}
              </Banner>
              <PrimaryButton title={t("pay.retry")} onPress={() => void retry()} loading={busy} />
            </>
          ) : null}
        </Card>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 },
  rowLabel: {
    flex: 1,
    paddingRight: space(2),
    fontFamily: family.body,
    fontSize: font.small,
    color: colors.muted,
  },
  rowValue: {
    flexShrink: 0,
    fontFamily: family.bodySemi,
    fontSize: font.small,
    color: colors.ink,
  },
  strong: { fontFamily: family.bodySemi },
  reference: {
    marginTop: space(2),
    fontFamily: family.body,
    fontSize: font.small,
    color: colors.ink,
    backgroundColor: colors.surface,
    padding: space(3),
    borderRadius: 8,
  },
});
