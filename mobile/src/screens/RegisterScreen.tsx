import { useMemo, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type RegisterResponse, type Role } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { COUNTRIES, countryName, dialFor } from "../lib/countries";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  PrimaryButton,
  Screen,
  Select,
  Subtitle,
  Title,
  type Choice,
} from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AuthScreenProps } from "../navigation/types";

const ROLES: Role[] = ["influencer", "business", "agency"];

export default function RegisterScreen({ navigation, route }: AuthScreenProps<"Register">) {
  const { t, i18n } = useTranslation();
  const preset = route.params?.role;
  const [role, setRole] = useState<Role>(
    preset === "business" || preset === "agency" || preset === "influencer" ? preset : "influencer"
  );
  const [country, setCountry] = useState("BJ");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const roleOptions: Choice[] = useMemo(
    () => [
      { value: "influencer", label: t("auth.roleInfluencer"), description: t("auth.roleInfluencerD") },
      { value: "business", label: t("auth.roleBusiness"), description: t("auth.roleBusinessD") },
      { value: "agency", label: t("auth.roleAgency"), description: t("auth.roleAgencyD") },
    ],
    [t]
  );
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({ value: c.code, label: countryName(c, i18n.language) }));

  const canSubmit = phone.trim().length >= 6 && password.length >= 8;

  async function onSubmit() {
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: { phone: phone.trim(), password, country_code: country, role },
      });
      navigation.navigate("VerifyOtp", { phone: phone.trim() });
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t("auth.registerTitle")}</Title>
      <Subtitle>{t("auth.registerSub")}</Subtitle>
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}

        <View style={{ marginBottom: space(4) }}>
          <Text style={{ fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) }}>
            {t("auth.role")}
          </Text>
          <ChoiceGroup options={roleOptions} value={role} onChange={(v) => setRole(v as Role)} />
        </View>

        {/* A dropdown, not a chip grid: seven countries as chips ate half the
            screen and pushed the form below the fold. */}
        <Select label={t("auth.country")} value={country} options={countryOptions} onChange={setCountry} />

        <Field
          label={t("auth.phone")}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          autoCapitalize="none"
          placeholder={`${dialFor(country)} ...`}
          hint={t("auth.phoneHint")}
        />
        <Field
          label={t("auth.password")}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
          hint={t("auth.passwordHint")}
        />
        <PrimaryButton
          title={busy ? t("common.working") : t("auth.submitRegister")}
          onPress={onSubmit}
          loading={busy}
          disabled={!canSubmit}
        />
      </Card>
      <View style={{ marginTop: space(4), alignItems: "center" }}>
        <Text style={{ fontFamily: family.body, color: colors.muted, fontSize: font.small }}>
          {t("auth.haveAccount")}{" "}
          <Text style={{ color: colors.teal600, fontFamily: family.bodySemi }} onPress={() => navigation.navigate("Login")}>
            {t("auth.loginLink")}
          </Text>
        </Text>
      </View>
    </Screen>
  );
}
