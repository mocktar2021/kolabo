import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, space } from "../theme";
import type { AuthScreenProps } from "../navigation/types";

export default function LoginScreen({ navigation }: AuthScreenProps<"Login">) {
  const { t } = useTranslation();
  const { login } = useAuth();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: { phone: phone.trim(), password },
      });
      // Setting the token flips the root navigator to the app; no manual
      // navigate. The role rides along so the experience is restored.
      await login(res.access_token, res.role);
    } catch (err) {
      setError(errorText(err, t));
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t("auth.loginTitle")}</Title>
      <Subtitle>{t("auth.loginSub")}</Subtitle>
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}
        <Field
          label={t("auth.phone")}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          autoCapitalize="none"
          placeholder="+229 ..."
        />
        <Field
          label={t("auth.password")}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
        />
        <PrimaryButton
          title={busy ? t("common.working") : t("auth.submitLogin")}
          onPress={onSubmit}
          loading={busy}
          disabled={!phone.trim() || !password}
        />
        <View style={{ marginTop: space(3) }}>
          <GhostButton title={t("reset.forgot")} onPress={() => navigation.navigate("ForgotPassword")} />
        </View>
      </Card>
      <View style={{ marginTop: space(4), alignItems: "center" }}>
        <Text style={{ color: colors.muted, fontSize: font.small }}>
          {t("auth.needAccount")}{" "}
          <Text style={{ color: colors.teal600, fontWeight: "600" }} onPress={() => navigation.navigate("Register")}>
            {t("auth.signupLink")}
          </Text>
        </Text>
      </View>
      <View style={{ height: space(2) }} />
      <Hint>{t("dash.comingSoon")}</Hint>
    </Screen>
  );
}
