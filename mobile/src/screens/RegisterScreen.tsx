import { useMemo, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type RegisterResponse, type Role } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { ROLES, useAuth } from "../lib/auth";
import { COUNTRIES, countryName } from "../lib/countries";
import { googleConfigured, signInWithGoogle } from "../lib/googleSignIn";
/* FOR ITS SIDE EFFECT. See the same import in LoginScreen. */
import "../lib/googleStrings";
import { GoogleDivider, GoogleSignInButton } from "../components/GoogleSignInButton";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  Hint,
  PrimaryButton,
  Screen,
  Select,
  Subtitle,
  Title,
  type Choice,
} from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AuthScreenProps } from "../navigation/types";

/* A loose shape test, deliberately. The backend owns what counts as an
   address and says so with auth_email_invalid, so a strict pattern here would
   only turn away valid addresses nobody thought of. This exists to stop the
   obviously unsendable from costing a round trip, and to do nothing else. */
const EMAIL_SHAPE = /^\S+@\S+\.\S+$/;

export default function RegisterScreen({ navigation, route }: AuthScreenProps<"Register">) {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const preset = route.params?.role;
  const [role, setRole] = useState<Role>(
    preset === "business" || preset === "agency" || preset === "influencer" ? preset : "influencer"
  );
  const [country, setCountry] = useState("BJ");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /* Built from ROLES in lib/auth now, which is the same closed set the Google
     panel on the login screen offers and the same one the backend checks
     against. The labels stay written out; see the note on the twin of this
     block in LoginScreen. */
  const roleOptions: Choice[] = useMemo(() => {
    const label: Record<Role, { t: string; d: string }> = {
      influencer: { t: t("auth.roleInfluencer"), d: t("auth.roleInfluencerD") },
      business: { t: t("auth.roleBusiness"), d: t("auth.roleBusinessD") },
      agency: { t: t("auth.roleAgency"), d: t("auth.roleAgencyD") },
    };
    return ROLES.map((r) => ({ value: r, label: label[r].t, description: label[r].d }));
  }, [t]);
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({ value: c.code, label: countryName(c, i18n.language) }));

  const canSubmit = EMAIL_SHAPE.test(email.trim()) && password.length >= 8;

  async function onSubmit() {
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: { email: email.trim(), password, country_code: country, role },
      });
      navigation.navigate("VerifyOtp", { email: email.trim() });
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  /* THE SAME REGISTRATION, WITHOUT THE PASSWORD AND WITHOUT THE CODE.
     POST /auth/google creates the account and returns a token in one call, so
     there is no VerifyOtp screen to send anybody to: Google has just proved
     the mailbox an OTP would have proved, and the backend marks the row
     verified from birth rather than sending a code nothing would read.

     THE TWO ANSWERS RIDE ALONG ON THE FIRST CALL, which is why this screen
     never shows the second step the login screen has to. Role and country are
     already on this form, so sending them saves a round trip and a question
     the person has just answered. auth_google_profile_required is therefore
     not reachable from here and is deliberately not handled: if it ever were,
     it would mean these two fields had stopped being sent, and a silent
     recovery would hide that.

     NO REFERRAL CODE, and that is not an omission of this change. This form
     has never collected one: web reads it from a ?ref query parameter and the
     phone has no equivalent entry point yet. signInWithGoogle takes one so the
     two clients keep the same seam, and the day a referral deep link reaches
     the app it passes through here.

     busy is NOT cleared on the success path: login() flips the root navigator
     and this screen unmounts. */
  async function onGoogle(credential: string) {
    setError(null);
    setBusy(true);
    try {
      const res = await signInWithGoogle(credential, { role, country_code: country });
      await login(res.access_token, res.role);
    } catch (err) {
      setError(errorText(err, t));
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
          label={t("auth.email")}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
          hint={t("auth.emailHint")}
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

        {/* UNDER THE FORM RATHER THAN OVER IT, which is the opposite of where a
            sign in button usually goes and is deliberate. The role and the
            country this button sends are collected in the fields above it, so
            a button at the top of the card would sign people up as whatever
            the defaults happen to say. All three of these draw nothing at all
            when no Google web client id is configured. */}
        <GoogleDivider />
        <GoogleSignInButton onCredential={(credential) => void onGoogle(credential)} disabled={busy} />
        {googleConfigured() ? <Hint>{t("auth.googleUsesAbove")}</Hint> : null}
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
