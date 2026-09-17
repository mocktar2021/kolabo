import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type MeOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { deleteProof, googleConfigured, patchProof, type Proof } from "../lib/googleSignIn";
/* FOR ITS SIDE EFFECT. See the same import in LoginScreen. */
import "../lib/googleStrings";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
/* The language card, lifted out of this file and into a component of its own
   so the signed out screens can draw the same control. It is the same card,
   in the same slot, built from the same two keys: see
   components/LanguageSwitch.tsx for why it moved and what the second shape of
   it is for. */
import { LanguageCard } from "../components/LanguageSwitch";
import {
  Banner,
  Card,
  Field,
  GhostButton,
  Hint,
  PrimaryButton,
  Screen,
  SectionTitle,
  Subtitle,
} from "../components/ui";
import { family, font, colors, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const MIN_PASSWORD = 8;

/* The notify() call sites, in the order web/src/pages/Account.tsx lists them. */
const NOTIFY_KEYS = [
  "acct.notifInvitation",
  "acct.notifProposal",
  "acct.notifContract",
  "acct.notifPayment",
  "acct.notifDispute",
  "acct.notifMessage",
  "acct.notifSecurity",
] as const;

/* PROOF THAT THE CALLER OWNS THIS ACCOUNT, and the decision this screen turns
   on. The same one web/src/pages/Account.tsx made, so the two clients cannot
   put a different control in front of the same person.

   THE RULE. An account that is NOT linked to Google sees exactly what it saw
   before: a password field, and nothing else. An account that IS linked is
   offered GOOGLE FIRST, with the password reachable behind one plain button
   that says so.

   WHY THAT ORDER RATHER THAN SHOWING BOTH. google_linked cannot distinguish an
   account created through Google, which has no usable password at all, from
   one that registered with a password and later signed in with Google, which
   has two ways in. Defaulting to the password would put a field in front of
   the first of those that it can never fill, which is the one thing the
   backend work shipped to prevent: before AccountPatch and
   DeleteAccountRequest learned to take a Google token, such an account could
   not change its own address or close itself at all. Defaulting to Google is
   the choice that always works for a linked account, and the second button is
   what keeps the account that genuinely has a password from losing it.

   WHY AN UNLINKED ACCOUNT IS NOT OFFERED GOOGLE. require_reauth would in fact
   accept a Google token for any account whose address matches, linked or not.
   But this client has no way to know whether the person holds a Google account
   at that address, so the button would be a coin flip: most would open the
   chooser, pick the only address they have, and be refused for a reason the
   screen cannot explain. A control that usually fails is worse than no control.

   TWO STEPS ON THE GOOGLE BRANCH, ON PURPOSE. The credential arrives and is
   held; the form is submitted afterwards by its own button. Signing in with
   Google must not be the gesture that deletes an account.

   `linked` RATHER THAN THE WHOLE ACCOUNT, because it is also false when
   /auth/me could not be loaded at all, and the right screen for an account
   nobody could read is the one this screen has always drawn. */
function ProofField({
  linked,
  passwordLabel,
  value,
  onChange,
}: {
  linked: boolean;
  passwordLabel: string;
  value: Proof | null;
  onChange: (next: Proof | null) => void;
}) {
  const { t } = useTranslation();
  const [usePassword, setUsePassword] = useState(!linked);

  if (usePassword) {
    return (
      <>
        <Field
          label={passwordLabel}
          value={value?.kind === "password" ? value.secret : ""}
          onChangeText={(text) => onChange(text ? { kind: "password", secret: text } : null)}
          secureTextEntry
        />
        {linked ? (
          <View style={{ marginBottom: space(4) }}>
            <GhostButton
              title={t("acct.proofUseGoogle")}
              onPress={() => {
                onChange(null);
                setUsePassword(false);
              }}
            />
          </View>
        ) : null}
      </>
    );
  }

  return (
    <View style={{ marginBottom: space(4) }}>
      <Text style={styles.proofLabel}>{t("acct.proofLabel")}</Text>
      {value?.kind === "google" ? (
        <>
          <Banner kind="success">{t("acct.proofGoogleReady")}</Banner>
          <GhostButton title={t("acct.proofGoogleRedo")} onPress={() => onChange(null)} />
        </>
      ) : (
        <GoogleSignInButton onCredential={(credential) => onChange({ kind: "google", secret: credential })} />
      )}
      <View style={{ height: space(2) }} />
      <GhostButton
        title={t("acct.proofUsePassword")}
        onPress={() => {
          onChange(null);
          setUsePassword(true);
        }}
      />
    </View>
  );
}

/* The account itself: the address somebody signs in with, the number they can
   be reached on, their password, the app's language, and the way out. Web's
   /account, minus the notification email toggles (there is no GET for their
   current state yet — flagged in the gap report) and plus the language
   switch, which web keeps in its nav.

   THE EMAIL LEADS because it is the identity. The phone under it is a contact
   detail that registration no longer asks for, which makes this screen the
   only place an account ever acquires one; for anybody who signed up after
   the flip it starts empty, and the copy says so rather than rendering a gap.

   Every credential change REQUIRES PROOF OF OWNERSHIP, in one of its two
   forms: the backend's rule, said before the form. A bearer token proves a
   session exists, not that the holder is the owner. Deleting requires it too,
   and hard-deletes only an account with no contract or escrow history
   (otherwise the catalog's auth_account_has_history sentence points at
   support). See ProofField for which form is offered to whom. */
export default function AccountScreen(_props: AppScreenProps<"Account">) {
  const { t } = useTranslation();
  const { token, logout } = useAuth();

  const [me, setMe] = useState<MeOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Email section: the sign-in identity, so it comes first on screen too
  const [newEmail, setNewEmail] = useState("");
  const [emailProof, setEmailProof] = useState<Proof | null>(null);
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailSaved, setEmailSaved] = useState(false);

  // Phone section: a contact detail, not a way in
  const [newPhone, setNewPhone] = useState("");
  const [phoneProof, setPhoneProof] = useState<Proof | null>(null);
  const [phoneBusy, setPhoneBusy] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSaved, setPhoneSaved] = useState(false);

  // Password section
  const [pwProof, setPwProof] = useState<Proof | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);

  // Delete section
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [delProof, setDelProof] = useState<Proof | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  /* Both halves are required. The link can be real while this build carries no
     Google client id, in which case Google is not on offer here any more than
     it is on the login screen, and the password is the only door left. */
  const canUseGoogle = !!me?.google_linked && googleConfigured();

  useEffect(() => {
    if (!token) return;
    api<MeOut>("/auth/me", { token })
      .then(setMe)
      .catch((e) => setLoadError(errorText(e, t)));
  }, [token, t]);

  async function saveEmail() {
    if (!newEmail.trim() || !emailProof) return;
    setEmailBusy(true);
    setEmailError(null);
    setEmailSaved(false);
    try {
      const updated = await api<MeOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { ...patchProof(emailProof), email: newEmail.trim() },
      });
      setMe(updated);
      setNewEmail("");
      setEmailProof(null);
      setEmailSaved(true);
    } catch (e) {
      setEmailError(errorText(e, t));
    } finally {
      setEmailBusy(false);
    }
  }

  async function savePhone() {
    if (!newPhone.trim() || !phoneProof) return;
    setPhoneBusy(true);
    setPhoneError(null);
    setPhoneSaved(false);
    try {
      const updated = await api<MeOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { ...patchProof(phoneProof), phone: newPhone.trim() },
      });
      setMe(updated);
      setNewPhone("");
      setPhoneProof(null);
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
    pwProof !== null &&
    newPassword.length >= MIN_PASSWORD &&
    newPassword === confirm;

  async function savePassword() {
    if (!pwReady || !pwProof) return;
    setPwBusy(true);
    setPwError(null);
    setPwSaved(false);
    try {
      await api<MeOut>("/auth/me", {
        method: "PATCH",
        token,
        body: { ...patchProof(pwProof), new_password: newPassword },
      });
      setPwProof(null);
      setNewPassword("");
      setConfirm("");
      setPwSaved(true);
    } catch (e) {
      setPwError(errorText(e, t));
    } finally {
      setPwBusy(false);
    }
  }

  async function deleteAccount() {
    if (!delProof) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      /* deleteProof, NOT patchProof. DELETE /auth/me reads `password` and
         PATCH reads `current_password`, and sending the wrong one is not a
         422: pydantic drops the unknown key, the request arrives with no
         proof at all, and 403 auth_reauth_required reads like a rejected
         password. */
      await api("/auth/me", { method: "DELETE", token, body: deleteProof(delProof) });
      // The account is gone; dropping the session lands on the login screen.
      void logout();
    } catch (e) {
      setDeleteError(errorText(e, t));
      setDeleteBusy(false);
    }
  }

  return (
    <Screen loading={me === null && !loadError}>
      <Subtitle>{t("acct.sub")}</Subtitle>

      {loadError ? <Banner kind="error">{loadError}</Banner> : null}

      <Card>
        <SectionTitle>{t("acct.emailTitle")}</SectionTitle>
        {/* The same argument either way. The variant names what this account
            can actually pay with, so a person who has no password is not told
            that one is the price. */}
        <Hint>{canUseGoogle ? t("acct.emailWhyProof") : t("acct.emailWhyPassword")}</Hint>
        <View style={{ height: space(3) }} />
        {/* Null is a real answer for both columns, so neither is rendered as a
            bare value: an account from before the flip has no address, and one
            created after it has no number until somebody adds one here. */}
        {me ? (
          <Text style={styles.current}>
            {me.email ? `${t("acct.emailCurrent")}: ${me.email}` : t("acct.emailNone")}
          </Text>
        ) : null}
        {emailError ? <Banner kind="error">{emailError}</Banner> : null}
        {emailSaved ? <Banner kind="success">{t("acct.emailSaved")}</Banner> : null}
        <Field
          label={t("acct.emailNew")}
          value={newEmail}
          onChangeText={setNewEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
        />
        <ProofField
          linked={canUseGoogle}
          passwordLabel={t("acct.passwordCurrent")}
          value={emailProof}
          onChange={setEmailProof}
        />
        <PrimaryButton
          title={emailBusy ? t("common.working") : t("acct.emailSave")}
          onPress={() => void saveEmail()}
          loading={emailBusy}
          disabled={!newEmail.trim() || !emailProof}
        />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.phoneTitle")}</SectionTitle>
        <Hint>{canUseGoogle ? t("acct.phoneWhyProof") : t("acct.phoneWhyPassword")}</Hint>
        <View style={{ height: space(3) }} />
        {me ? (
          <Text style={styles.current}>
            {me.phone ? `${t("acct.phoneCurrent")}: ${me.phone}` : t("acct.phoneNone")}
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
        <ProofField
          linked={canUseGoogle}
          passwordLabel={t("acct.passwordCurrent")}
          value={phoneProof}
          onChange={setPhoneProof}
        />
        <PrimaryButton
          title={phoneBusy ? t("common.working") : t("acct.phoneSave")}
          onPress={() => void savePhone()}
          loading={phoneBusy}
          disabled={!newPhone.trim() || !phoneProof}
        />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.passwordTitle")}</SectionTitle>
        {/* Says "if", because the server tells us the account is linked and
            not whether it also has a password. See MeOut.google_linked. This
            form is also the ONLY way a Google created account ever acquires
            one: sending new_password with a Google token is what
            AccountPatch.google_token exists for. */}
        {canUseGoogle ? <Hint>{t("acct.passwordMaybeFirst")}</Hint> : null}
        {pwError ? <Banner kind="error">{pwError}</Banner> : null}
        {pwSaved ? <Banner kind="success">{t("acct.passwordSaved")}</Banner> : null}
        <View style={{ height: space(2) }} />
        <ProofField
          linked={canUseGoogle}
          passwordLabel={t("acct.passwordCurrent")}
          value={pwProof}
          onChange={setPwProof}
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

      {/* Whether Google reaches this account, said once and changed nowhere.

          THERE IS NO DISCONNECT BUTTON AND THAT IS NOT AN OVERSIGHT. No
          endpoint clears users.google_sub: not PATCH /auth/me, which cannot
          carry the column, and not anything else. A button here would have to
          either lie or call something that does not exist, so the row is
          informational and says as much. The day the backend grows a way to
          unlink, the control belongs here.

          Under the two credentials it is about, because it is a statement
          rather than a control and must not sit above the things somebody came
          to this screen to change. */}
      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.googleTitle")}</SectionTitle>
        <Text style={styles.body}>
          {me?.google_linked ? t("acct.googleLinkedYes") : t("acct.googleLinkedNo")}
        </Text>
        {me?.google_linked ? <Hint>{t("acct.googleNoDisconnect")}</Hint> : null}
      </Card>

      {/* Web /account's Payment tab, verbatim: explained rather than collected.
          Nothing in this system stores a payment instrument — money moves by
          Mobile Money through the buyer-funded escrow, and no endpoint accepts
          a payout destination. A form here would collect details nobody reads
          or imply an automatic payout that does not exist yet. */}
      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.paymentTitle")}</SectionTitle>
        <Text style={styles.body}>{t("acct.paymentBody")}</Text>
        <Hint>{t("acct.paymentPending")}</Hint>
        <Hint>{t("acct.paymentMeanwhile")}</Hint>
      </Card>

      {/* Web /account's Notifications tab, verbatim: the list of what the
          platform sends, READ-ONLY. There are no notification preferences
          server-side — notify() writes a row for every event — so there are
          no switches; switches that switched nothing would teach people to
          distrust the product. The entries mirror the notify() call sites. */}
      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.notifTitle")}</SectionTitle>
        <Hint>{t("acct.notifIntro")}</Hint>
        <View style={{ height: space(2) }} />
        {NOTIFY_KEYS.map((key) => (
          <View key={key} style={styles.notifRow}>
            <Text style={styles.notifBullet}>•</Text>
            <Text style={styles.notifText}>{t(key)}</Text>
          </View>
        ))}
        <Hint>{t("acct.notifReadOnly")}</Hint>
      </Card>

      <View style={{ height: space(4) }} />
      <LanguageCard />

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>{t("acct.deleteTitle")}</SectionTitle>
        <Hint>{t("acct.deleteExplain")}</Hint>
        <View style={{ height: space(3) }} />
        {deleteError ? <Banner kind="error">{deleteError}</Banner> : null}
        {deleteOpen ? (
          <>
            <ProofField
              linked={canUseGoogle}
              passwordLabel={t("acct.passwordCurrent")}
              value={delProof}
              onChange={setDelProof}
            />
            <PrimaryButton
              title={deleteBusy ? t("common.working") : t("acct.deleteConfirm")}
              onPress={() => void deleteAccount()}
              loading={deleteBusy}
              disabled={!delProof}
            />
            <View style={{ height: space(2) }} />
            <GhostButton
              title={t("acct.deleteNo")}
              onPress={() => {
                setDeleteOpen(false);
                setDelProof(null);
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

const styles = StyleSheet.create({
  current: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(3) },
  body: { fontFamily: family.body, fontSize: font.small, color: colors.ink, lineHeight: 20, marginBottom: space(2) },
  proofLabel: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    marginBottom: space(1.5),
  },
  notifRow: { flexDirection: "row", gap: space(2), paddingVertical: 3 },
  notifBullet: { fontFamily: family.body, fontSize: font.small, color: colors.muted },
  notifText: { flex: 1, fontFamily: family.body, fontSize: font.small, color: colors.ink, lineHeight: 19 },
});
