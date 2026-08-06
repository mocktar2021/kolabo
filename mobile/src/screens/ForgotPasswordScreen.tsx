import { useState } from "react";
import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { space } from "../theme";
import type { AuthScreenProps } from "../navigation/types";

const MIN_PASSWORD_LENGTH = 8;

/* Two steps, mirroring web/src/pages/Login.tsx's PasswordReset.

   THE SECURITY PROPERTY THIS MUST KEEP: POST /auth/password-reset/request
   answers the same 202 whether or not the number is registered — two answers
   would make it a free "is this person on Kolabo?" lookup. So the confirmation
   after the request says "if that number is registered" and never "a code has
   been sent": the client genuinely does not know. Every way the confirm step
   can fail comes back as the same refusal, so it gets one sentence too. */
export default function ForgotPasswordScreen({ navigation }: AuthScreenProps<"ForgotPassword">) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = password !== "" && password.length < MIN_PASSWORD_LENGTH;
  const mismatch = confirm !== "" && confirm !== password;
  const ready = code.length === 6 && password.length >= MIN_PASSWORD_LENGTH && confirm === password;

  async function request() {
    if (!phone.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/request", { method: "POST", body: { phone: phone.trim() } });
      setStep("code");
    } catch (err) {
      // 429 (auth_reset_too_many) is the one case this endpoint is not silent
      // about; errorText says it in the reader's language.
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!ready) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        body: { phone: phone.trim(), code, new_password: password },
      });
      // No token is returned on purpose — proving you hold the phone earns a
      // new password, not a session. Back to login to sign in with it.
      navigation.navigate("Login");
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>{t("reset.title")}</Title>
      <Subtitle>{step === "phone" ? t("reset.intro") : t("reset.sentHint")}</Subtitle>
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}

        {step === "phone" ? (
          <>
            <Field
              label={t("reset.phoneLabel")}
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              autoCapitalize="none"
              placeholder="+229 ..."
            />
            <PrimaryButton
              title={busy ? t("common.working") : t("reset.request")}
              onPress={request}
              loading={busy}
              disabled={!phone.trim()}
            />
            <View style={{ marginTop: space(3) }}>
              <GhostButton title={t("reset.back")} onPress={() => navigation.navigate("Login")} />
            </View>
          </>
        ) : (
          <>
            <Banner kind="info">{t("reset.sent")}</Banner>
            <Field
              label={t("reset.codeLabel")}
              value={code}
              onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))}
              keyboardType="number-pad"
              maxLength={6}
              placeholder="000000"
            />
            <Field
              label={t("reset.newPassword")}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
            />
            {tooShort ? <Hint>{t("reset.tooShort", { n: MIN_PASSWORD_LENGTH })}</Hint> : null}
            <View style={{ height: space(3) }} />
            <Field
              label={t("reset.confirmPassword")}
              value={confirm}
              onChangeText={setConfirm}
              secureTextEntry
              autoCapitalize="none"
            />
            {mismatch ? <Hint>{t("reset.mismatch")}</Hint> : null}
            <View style={{ height: space(2) }} />
            <PrimaryButton
              title={busy ? t("common.working") : t("reset.confirm")}
              onPress={submit}
              loading={busy}
              disabled={!ready}
            />
            <View style={{ marginTop: space(3) }}>
              <GhostButton
                title={t("reset.changePhone")}
                onPress={() => {
                  setStep("phone");
                  setError(null);
                }}
              />
            </View>
          </>
        )}
      </Card>
    </Screen>
  );
}
