import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type MeOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { countryName, dialFor } from "../lib/countries";
import {
  getPayoutMethod,
  paymentConfig,
  payoutModeLabel,
  payoutModes,
  savePayoutMethod,
  type PaymentConfig,
  type PayoutMethod,
} from "../lib/checkout";
/* Side-effect import: registers the pay.* copy on the i18n instance. */
import "../lib/paymentStrings";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  GhostButton,
  Hint,
  PrimaryButton,
  Screen,
  SectionTitle,
  Subtitle,
  type Choice,
} from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* Where a creator's money goes when an escrow is released. Its own screen
   rather than a section of the profile form: this is the one form on the app
   whose mistakes cost real money, and a wrong wallet is not discovered until a
   payout fails days later. */
export default function PayoutMethodScreen(_props: AppScreenProps<"PayoutMethod">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();

  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [saved, setSaved] = useState<PayoutMethod | null>(null);
  const [country, setCountry] = useState("");
  const [modes, setModes] = useState<string[]>([]);
  const [mode, setMode] = useState("");
  const [phone, setPhone] = useState("");
  const [accountName, setAccountName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [cfg, existing] = await Promise.all([paymentConfig(), getPayoutMethod(token)]);
      setConfig(cfg);
      setSaved(existing);
      if (existing) {
        setMode(existing.mode);
        setAccountName(existing.account_name ?? "");
      }
      /* Prefill by how much each source actually knows about where the money
         should go: the wallet they already saved, then the country on their
         account, then whatever the gateway can pay in at all. */
      let start = existing?.country ?? "";
      if (!start) {
        try {
          const me = await api<MeOut>("/auth/me", { token });
          if (cfg.countries.includes(me.country_code)) start = me.country_code;
        } catch {
          /* The account read is a convenience, not the point of the screen: if
             it fails, the picker below still lets them choose. */
        }
      }
      setCountry(start || cfg.countries[0] || "");
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!country) return;
    let live = true;
    void (async () => {
      try {
        const list = await payoutModes(country);
        if (!live) return;
        setModes(list);
        /* A network the gateway does not serve in the newly picked country
           cannot stay selected: the transfer would be accepted here and fail
           at payout time, long after the creator has left this screen. */
        setMode((cur) => (cur && list.includes(cur) ? cur : list[0] || ""));
      } catch {
        if (live) setModes([]);
      }
    })();
    return () => {
      live = false;
    };
  }, [country]);

  async function save() {
    setBusy(true);
    setError(null);
    setOk(false);
    try {
      setSaved(
        await savePayoutMethod(token, {
          country,
          mode,
          phone: phone.trim(),
          account_name: accountName.trim() || null,
        })
      );
      setOk(true);
      /* The saved wallet is echoed back masked, so the field has done its job.
         Clearing it keeps a full Mobile Money number from sitting on screen on
         a phone that gets handed around. */
      setPhone("");
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const countryOptions: Choice[] = (config?.countries ?? []).map((code) => ({
    value: code,
    label: countryName(code, i18n.language),
  }));
  const modeOptions: Choice[] = modes.map((m) => ({ value: m, label: payoutModeLabel(m) }));

  return (
    <Screen loading={loading}>
      <Subtitle>{t("pay.payoutHint")}</Subtitle>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {ok ? <Banner kind="success">{t("pay.payoutSaved")}</Banner> : null}

      {config && !config.enabled ? (
        <Card>
          <SectionTitle>{t("pay.unavailable")}</SectionTitle>
          <Hint>{t("pay.unavailableHint")}</Hint>
        </Card>
      ) : (
        <>
          {saved ? (
            <Card>
              <SectionTitle>{t("pay.payoutCurrent")}</SectionTitle>
              <Text style={styles.wallet}>
                {payoutModeLabel(saved.mode)} · {saved.phone_masked}
              </Text>
              <Hint>
                {countryName(saved.country, i18n.language)}
                {saved.account_name ? ` · ${saved.account_name}` : ""}
              </Hint>
            </Card>
          ) : (
            <Banner kind="info">{t("pay.payoutMissing")}</Banner>
          )}

          <View style={{ height: space(4) }} />
          <Card>
            <SectionTitle>{t("pay.payoutTitle")}</SectionTitle>

            <View style={{ height: space(2) }} />
            <Text style={styles.label}>{t("pay.payoutCountry")}</Text>
            <ChoiceGroup options={countryOptions} value={country} onChange={setCountry} />

            <View style={{ height: space(3) }} />
            {/* THE NETWORK IS ASKED FOR, NEVER INFERRED FROM THE NUMBER. The
                prefix-to-operator tables everyone reaches for go stale:
                regulators reassign prefixes between operators, and number
                portability moves a subscriber from one network to another
                without a single digit changing. A guess that is wrong is not
                caught here — it is caught at payout, days later, by a transfer
                that fails or lands nowhere. One tap now is cheaper than that. */}
            <Text style={styles.label}>{t("pay.payoutNetwork")}</Text>
            <ChoiceGroup options={modeOptions} value={mode} onChange={setMode} />

            <View style={{ height: space(3) }} />
            <Field
              label={t("pay.payoutPhone")}
              value={phone}
              onChangeText={(v) => setPhone(v.replace(/[^\d+]/g, ""))}
              keyboardType="phone-pad"
              placeholder={dialFor(country)}
            />
            <Field label={t("pay.payoutName")} value={accountName} onChangeText={setAccountName} />

            <PrimaryButton
              title={busy ? t("common.working") : t("pay.payoutSave")}
              onPress={() => void save()}
              loading={busy}
              disabled={!country || !mode || !phone.trim()}
            />
          </Card>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  label: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    marginBottom: space(1.5),
  },
  wallet: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
});
