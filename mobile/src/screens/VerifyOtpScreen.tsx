import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { Banner, Card, Field, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import type { AuthScreenProps } from "../navigation/types";

export default function VerifyOtpScreen({ route }: AuthScreenProps<"VerifyOtp">) {
  const { t } = useTranslation();
  const { login } = useAuth();
  const { phone } = route.params;
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    if (code.length < 6) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/verify-otp", {
        method: "POST",
        body: { phone, code },
      });
      // The verify response's role is the backend truth. Setting the token
      // flips the root navigator into the app.
      await login(res.access_token, res.role);
    } catch (err) {
      setError(errorText(err, t));
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t("auth.otpTitle")}</Title>
      <Subtitle>{t("auth.otpSub")}</Subtitle>
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}
        <Banner kind="info">{t("auth.otpDevHint")}</Banner>
        <Field
          label={t("auth.otpCode")}
          value={code}
          onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))}
          keyboardType="number-pad"
          placeholder="000000"
          maxLength={6}
        />
        <PrimaryButton
          title={busy ? t("common.working") : t("auth.otpSubmit")}
          onPress={onSubmit}
          loading={busy}
          disabled={code.length < 6}
        />
      </Card>
    </Screen>
  );
}
