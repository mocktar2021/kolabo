import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type MeOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { setStoredLanguage, type AppLanguage } from "../lib/language";
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
  Title,
} from "../components/ui";
import { family, font, colors, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const MIN_PASSWORD = 8;

/* The account itself: the number somebody signs in with, their password, the
   app's language, and the way out. Web's /account, minus the notification
   email toggles (there is no GET for their current state yet — flagged in
   the gap report) and plus the language switch, which web keeps in its nav.

   Both credential changes REQUIRE the current password — the backend's rule,
   said before the form: a bearer token proves a session exists, not that the
   holder is the owner. Deleting requires it too, and hard-deletes only an
   account with no contract or escrow history (otherwise the catalog's
   auth_account_has_history sentence points at support). */
export default function AccountScreen(_props: AppScreenProps<"Account">) {
  const { t, i18n } = useTranslation();
  const { token, logout } = useAuth();

  const [me, setMe] = useState<MeOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Phone section
  const [newPhone, setNewPhone] = useState("");
  const [phonePassword, setPhonePassword] = useState("");
  const [phoneBusy, setPhoneBusy] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSaved, setPhoneSaved] = useState(false);

  // Password section
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);

  // Delete section
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api<MeOut>("/auth/me", { token })
      .then(setMe)
      .catch((e) => setLoadError(errorText(e, t)));
  }, [token, t]);

  async function savePhone() {
    if (!newPhone.trim() || !phonePassword) return;
    setPhoneBusy(true);
    setPhoneError(null);
    setPhoneSaved(false);
    try {
      const updated = await api<MeOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { current_password: phonePassword, phone: newPhone.trim() },
      });
      setMe(updated);
      setNewPhone("");
      setPhonePassword("");
      setPhoneSaved(true);
    } catch (e) {
      setPhoneError(errorText(e, t));
    } finally {
      setPhoneBusy(false);
    }
  }

  const pwTooShort = newPassword.length > 0 && newPassword.length < MIN_PASSWORD;
  const pwMismatch = confirm.length > 0 && newPassword !== confirm;
  const pwReady =
    currentPassword.length > 0 &&
    newPassword.length >= MIN_PASSWORD &&
    newPassword === confirm;

  async function savePassword() {
    if (!pwReady) return;
    setPwBusy(true);
    setPwError(null);
    setPwSaved(false);
    try {
      await api<MeOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { current_password: currentPassword, new_password: newPassword },
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
      setPwSaved(true);
    } catch (e) {
      setPwError(errorText(e, t));
    } finally {
      setPwBusy(false);
    }
  }

  function switchLanguage(lang: string) {
    void i18n.changeLanguage(lang);
    void setStoredLanguage(lang as AppLanguage);
  }

  async function deleteAccount() {
    if (!deletePassword) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api("/auth/me", { method: "DELETE", token, body: { password: deletePassword } });
      // The account is gone; dropping the session lands on the login screen.
      void logout();
    } catch (e) {
      setDeleteError(errorText(e, t));
      setDeleteBusy(false);
    }
  }

  return (
    <Screen loading={me === null && !loadError}>
      <Title>{t("acct.title")}</Title>
      <Subtitle>{t("acct.sub")}</Subtitle>

      {loadError ? <Banner kind="error">{loadError}</Banner> : null}

      <Card>
        <SectionTitle>{t("acct.phoneTitle")}</SectionTitle>
        <Hint>{t("acct.phoneWhyPassword")}</Hint>
        <View style={{ height: space(3) }} />
        {me ? (
          <Text style={{ fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(3) }}>
            {t("acct.phoneCurrent")}: {me.phone}
          </Text>
        ) : null}
        {phoneError ? <Banner kind="error">{phoneError}</Banner> : null}
        {phoneSaved ? <Banner kind="success">{t("acct.phoneSaved")}</Banner> : null}
        <Field
          label={t("acct.phoneNew")}
          value={newPhone}
          onChangeText={setNewPhone}
          keyboardType="phone-pad"
          autoCapitalize="none"
        />
        <Field
          label={t("acct.passwordCurrent")}
          value={phonePassword}
          onChangeText={setPhonePassword}
          secureTextEntry
        />
        <PrimaryButton
          title={phoneBusy ? t("common.working") : t("acct.phoneSave")}
          onPress={() => void savePhone()}
          loading={phoneBusy}
          disabled={!newPhone.trim() || !phonePassword}
        />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.passwordTitle")}</SectionTitle>
        {pwError ? <Banner kind="error">{pwError}</Banner> : null}
        {pwSaved ? <Banner kind="success">{t("acct.passwordSaved")}</Banner> : null}
        <Field
          label={t("acct.passwordCurrent")}
          value={currentPassword}
          onChangeText={setCurrentPassword}
          secureTextEntry
        />
        <Field
          label={t("acct.passwordNew")}
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry
          hint={pwTooShort ? t("acct.passwordTooShort", { n: MIN_PASSWORD }) : undefined}
        />
        <Field
          label={t("acct.passwordConfirm")}
          value={confirm}
          onChangeText={setConfirm}
          secureTextEntry
          hint={pwMismatch ? t("acct.passwordMismatch") : undefined}
        />
        <PrimaryButton
          title={pwBusy ? t("common.working") : t("acct.passwordSave")}
          onPress={() => void savePassword()}
          loading={pwBusy}
          disabled={!pwReady}
        />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.langTitle")}</SectionTitle>
        <Hint>{t("acct.langHint")}</Hint>
        <View style={{ height: space(3) }} />
        <ChoiceGroup
          options={[
            { value: "fr", label: "Français" },
            { value: "en", label: "English" },
          ]}
          value={i18n.language === "en" ? "en" : "fr"}
          onChange={switchLanguage}
        />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.deleteTitle")}</SectionTitle>
        <Hint>{t("acct.deleteExplain")}</Hint>
        <View style={{ height: space(3) }} />
        {deleteError ? <Banner kind="error">{deleteError}</Banner> : null}
        {deleteOpen ? (
          <>
            <Field
              label={t("acct.passwordCurrent")}
              value={deletePassword}
              onChangeText={setDeletePassword}
              secureTextEntry
            />
            <PrimaryButton
              title={deleteBusy ? t("common.working") : t("acct.deleteConfirm")}
              onPress={() => void deleteAccount()}
              loading={deleteBusy}
              disabled={!deletePassword}
            />
            <View style={{ height: space(2) }} />
            <GhostButton
              title={t("acct.deleteNo")}
              onPress={() => {
                setDeleteOpen(false);
                setDeletePassword("");
                setDeleteError(null);
              }}
            />
          </>
        ) : (
          <GhostButton title={t("acct.deleteTitle")} onPress={() => setDeleteOpen(true)} />
        )}
      </Card>
    </Screen>
  );
}
