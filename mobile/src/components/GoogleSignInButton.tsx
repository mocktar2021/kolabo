import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { GoogleSigninButton } from "@react-native-google-signin/google-signin";
import { getGoogleCredential, googleConfigured } from "../lib/googleSignIn";
import { Hint } from "./ui";
import { colors, family, font, space } from "../theme";

/* Google's own button, drawn by Google, or nothing at all.

   IT RENDERS NOTHING WHEN THE WEB CLIENT ID IS UNSET, and that is the whole
   contract rather than a nicety. Without one Google issues no ID token, so a
   button here would open the chooser, come back with nothing to post, and
   leave somebody looking at a control that only ever fails. Same rule the rest
   of the platform applies to a provider nobody configured. See lib/config.ts
   for where the id comes from and lib/googleSignIn.ts for what absent means.

   THE CONTROL IS GOOGLE'S, NOT OURS, which is the same decision
   web/src/components/GoogleSignInButton.tsx made and for the same reason:
   Google's branding terms are about their button specifically, and a hand
   drawn lookalike is how an app ends up with a sign in control that is subtly
   wrong in two languages. GoogleSigninButton is a native view, so it does not
   inherit this app's type scale and cannot be restyled beyond a size and a
   colour, and it takes its LANGUAGE FROM THE DEVICE rather than from the in
   app language switch. Both are accepted costs of not drawing it ourselves.

   THE PRESS IS OURS. Unlike the web, where Google renders a button and fires
   a callback, here the native view is just a view: this component owns the
   chooser, and what comes back is the resolved value of a promise. That is
   why cancelling is handled HERE and says nothing. Somebody who opens the
   chooser and changes their mind is looking at the screen they started on,
   and an error banner would be the app telling them off for it. */

type Props = {
  /* Handed the encoded Google ID token, exactly once per completed chooser.
     Never called for a cancellation and never called with an empty string. */
  onCredential: (credential: string) => void;
  /* Set while the screen is doing something with a credential it already has,
     so a second tap cannot start a second sign in over the top of the first
     one's network call. */
  disabled?: boolean;
};

export function GoogleSignInButton({ onCredential, disabled }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  async function press() {
    setUnavailable(false);
    setBusy(true);
    try {
      const result = await getGoogleCredential();
      if (result.status === "ok") {
        onCredential(result.credential);
        return;
      }
      /* Said out loud only for "unavailable": no Google Play services on this
         handset, or a native call that failed for a reason the SDK will not
         name. The sentence points at the email and password form underneath,
         which still works. A cancellation falls through here silently. */
      if (result.status === "unavailable") setUnavailable(true);
    } finally {
      setBusy(false);
    }
  }

  if (!googleConfigured()) return null;

  return (
    <View>
      <GoogleSigninButton
        style={styles.button}
        size={GoogleSigninButton.Size.Wide}
        color={GoogleSigninButton.Color.Light}
        disabled={busy || !!disabled}
        onPress={() => void press()}
      />
      {unavailable ? <Hint>{t("auth.googleUnavailable")}</Hint> : null}
    </View>
  );
}

/* The "or" between the Google button and the email form.

   A separate export because both auth screens draw it and neither should own
   it, and because it is the one piece of chrome around the button that IS
   ours. Hidden along with the button when the provider is unconfigured: a rule
   between one thing and nothing is a line across an empty card. */
export function GoogleDivider() {
  const { t } = useTranslation();
  if (!googleConfigured()) return null;
  return (
    <View style={styles.divider}>
      <View style={styles.rule} />
      <Text style={styles.dividerText}>{t("auth.googleOr")}</Text>
      <View style={styles.rule} />
    </View>
  );
}

const styles = StyleSheet.create({
  /* Full width and the same 48pt floor the app's own buttons keep, so the
     card does not suddenly hold one control of a different size. The height
     is the only part of this view we get to decide. */
  button: { width: "100%", height: 48 },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(3),
    marginVertical: space(4),
  },
  rule: { flex: 1, height: 1, backgroundColor: colors.line },
  dividerText: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted },
});
