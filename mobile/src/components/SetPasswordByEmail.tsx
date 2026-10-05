import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
/* FOR ITS SIDE EFFECT. Every acct.setPw key below is registered at runtime by
   that module, not by src/strings.ts, so without this import they render as
   raw keys. See the same import in AccountScreen and LoginScreen. */
import "../lib/googleStrings";
import { Banner, Field, GhostButton, Hint, PrimaryButton } from "./ui";
import { colors, family, font, space } from "../theme";

const MIN_PASSWORD = 8;
const CODE_LENGTH = 6;

/* GIVE A SIGNED IN ACCOUNT A PASSWORD IT MAY NEVER HAVE HAD, without asking
   for the password it does not have.

   WHY THIS EXISTS. An account created through Google has no usable password:
   backend auth/service.py sets a hash of a secret that is generated, used once
   and never revealed. Everything on the account screen that changes a
   credential, and deleting the account, costs proof of ownership, and
   require_reauth accepts exactly two proofs, a password or a Google token. On
   a build where Google is not offered, which is iOS from this release on, such
   an account holds neither. That is not an inconvenience: App Store Guideline
   5.1.1(v) requires account deletion inside the app, so an account that cannot
   prove ownership cannot be deleted, and the change that satisfied 4.8 would
   have broken 5.1.1(v) instead.

   WHY THE PASSWORD RESET ENDPOINTS, which look like the wrong tool for a
   signed in person. They are the only pair that mints a credential without
   spending one, and they are provider blind: request looks the user up by
   email and branches on nothing, confirm takes an email, a code and a new
   password and NEVER the current one. So the mailbox is the proof. That is the
   same standard the signed out screen uses, and it is strictly stronger here,
   because the address came from /auth/me rather than from a text field.

   WHY NOT NAVIGATE TO ForgotPasswordScreen, which is this flow already built.
   It is on the Auth stack, which RootNavigator mounts only when nobody is
   signed in. A signed in account cannot reach it without restructuring the
   navigator, which is not a change to make alongside a store submission.

   WHAT IT DOES NOT ASK FOR. The address. The person is signed in and the
   address is their own, so a field here would be a chance to typo it and have
   the code sent somewhere unreachable.

   THE COPY REUSES reset.* WHEREVER THE ACT IS THE SAME, deliberately: the code
   field, the two password fields and the two validation sentences are the same
   words the signed out screen uses, because the same act must not read
   differently in two places on one product. Only the sentences that genuinely
   differ are new, and acct.setPwSent is the one that matters: the signed out
   flow has to hedge about whether the address is registered, and this one does
   not. */
export function SetPasswordByEmail({
  email,
  onCancel,
  onSuccess,
}: {
  email: string;
  onCancel: () => void;
  onSuccess: () => void;
}) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"ask" | "code">("ask");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooShort = password !== "" && password.length < MIN_PASSWORD;
  const mismatch = confirm !== "" && confirm !== password;
  const ready =
    code.length === CODE_LENGTH && password.length >= MIN_PASSWORD && confirm === password;

  async function request() {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password-reset/request", { method: "POST", body: { email } });
      setStep("code");
    } catch (err) {
      /* This endpoint is silent about almost everything by design. The one
         refusal it does name is 429 auth_reset_too_many, and errorText says it
         in the reader's language. */
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
        body: { email, code, new_password: password },
      });
      /* No token comes back and none is wanted: this account already holds a
         session. What it now holds as well is a password, which is the proof
         the form underneath has been waiting for. */
      onSuccess();
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ marginBottom: space(4) }}>
      <Text style={styles.title}>{t("acct.setPwTitle")}</Text>
      {error ? <Banner kind="error">{error}</Banner> : null}

      {step === "ask" ? (
        <>
          <Hint>{t("acct.setPwIntro", { email })}</Hint>
          <View style={{ height: space(2) }} />
          <PrimaryButton
            title={busy ? t("common.working") : t("acct.setPwSend")}
            onPress={() => void request()}
            loading={busy}
          />
        </>
      ) : (
        <>
          <Banner kind="info">{t("acct.setPwSent", { email })}</Banner>
          <Field
            label={t("reset.codeLabel")}
            value={code}
            onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, CODE_LENGTH))}
            keyboardType="number-pad"
            maxLength={CODE_LENGTH}
            placeholder="000000"
          />
          <Field
            label={t("reset.newPassword")}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            hint={tooShort ? t("reset.tooShort", { n: MIN_PASSWORD }) : undefined}
          />
          <Field
            label={t("reset.confirmPassword")}
            value={confirm}
            onChangeText={setConfirm}
            secureTextEntry
            autoCapitalize="none"
            hint={mismatch ? t("reset.mismatch") : undefined}
          />
          <PrimaryButton
            title={busy ? t("common.working") : t("reset.confirm")}
            onPress={() => void submit()}
            loading={busy}
            disabled={!ready}
          />
        </>
      )}

      <View style={{ height: space(2) }} />
      <GhostButton title={t("acct.setPwCancel")} onPress={onCancel} />
    </View>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    marginBottom: space(1.5),
  },
});
