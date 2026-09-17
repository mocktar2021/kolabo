import { useMemo, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type Role, type TokenResponse } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { ROLES, useAuth } from "../lib/auth";
import { COUNTRIES, countryName } from "../lib/countries";
import {
  looksLikeWrongPassword,
  needsProfileAnswers,
  signInWithGoogle,
} from "../lib/googleSignIn";
/* FOR ITS SIDE EFFECT. googleStrings.ts registers the auth.google* keys at
   runtime; without this import every sentence below renders as its raw key. */
import "../lib/googleStrings";
import { GoogleDivider, GoogleSignInButton } from "../components/GoogleSignInButton";
import { LanguageSwitch } from "../components/LanguageSwitch";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  GhostButton,
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

/* The two things Google cannot tell us, asked only when they are needed.

   WHY THIS EXISTS ON THE LOGIN SCREEN AND NOT ON THE REGISTER ONE. A new
   person can arrive at either. The register form has already collected a role
   and a country by the time its Google button is reachable, so it sends both
   on the first call and this panel never opens there. Nothing on a login form
   asks either question, and nothing should: it is a login form. So the first
   call goes without them, and a Google address that has no Kolabo account
   behind it comes back 400 auth_google_profile_required, which is NOT an
   error. It is the first leg of a two step flow, and this is the second leg.

   THE SAME TOKEN IS SENT AGAIN, not a fresh one. A Google ID token is good for
   about an hour, so there is no need to reopen the chooser, and reopening it
   would make somebody prove who they are twice for one sign up. If it has
   expired anyway, the second call answers auth_google_token_invalid and says
   so here, where the cancel button is.

   THE ROLE AND THE COUNTRY ARE THE REGISTER FORM'S, deliberately: ROLES comes
   from lib/auth and COUNTRIES from lib/countries, which are the same two lists
   RegisterScreen draws from, and the labels come from the same auth.role* keys.
   A second set would be a second place for a market to open in and a role to
   be added. */
function GoogleQuestions({
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (role: Role, country: string) => void;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [role, setRole] = useState<Role>("influencer");
  const [country, setCountry] = useState("BJ");

  /* The labels are written out rather than built from the role name, which is
     the same shape web/src/pages/Login.tsx uses. A key assembled from a value
     cannot be found by a search for it, and a role whose label was never
     written would render the raw key instead of failing anywhere visible. */
  const roleOptions: Choice[] = useMemo(() => {
    const label: Record<Role, { t: string; d: string }> = {
      influencer: { t: t("auth.roleInfluencer"), d: t("auth.roleInfluencerD") },
      business: { t: t("auth.roleBusiness"), d: t("auth.roleBusinessD") },
      agency: { t: t("auth.roleAgency"), d: t("auth.roleAgencyD") },
    };
    return ROLES.map((r) => ({ value: r, label: label[r].t, description: label[r].d }));
  }, [t]);
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({
    value: c.code,
    label: countryName(c, i18n.language),
  }));

  return (
    <Card>
      <Title>{t("auth.googleAskTitle")}</Title>
      <Subtitle>{t("auth.googleAskIntro")}</Subtitle>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <View style={{ marginBottom: space(4) }}>
        <Text style={{ fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) }}>
          {t("auth.role")}
        </Text>
        <ChoiceGroup options={roleOptions} value={role} onChange={(v) => setRole(v as Role)} />
      </View>
      <Select label={t("auth.country")} value={country} options={countryOptions} onChange={setCountry} />
      <PrimaryButton
        title={busy ? t("common.working") : t("auth.googleAskSubmit")}
        onPress={() => onSubmit(role, country)}
        loading={busy}
        disabled={busy}
      />
      <View style={{ height: space(2) }} />
      <GhostButton title={t("auth.googleAskCancel")} onPress={onCancel} disabled={busy} />
    </Card>
  );
}

export default function LoginScreen({ navigation }: AuthScreenProps<"Login">) {
  const { t } = useTranslation();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /* The token held between the two legs of the Google flow. Non-null means the
     address has no account yet and the panel above stands in for the form. */
  const [googleToken, setGoogleToken] = useState<string | null>(null);
  /* Whether the LAST refusal was the vague one. The backend answers
     auth_bad_credentials both for a wrong password and for an account created
     through Google, which has no usable password at all, and it refuses to
     tell them apart on purpose: a distinct code would say which addresses are
     registered here to anybody with a list of them. So the client does not
     guess either. It points at the button, beside the field, and only after an
     attempt has actually failed, so nobody is told about Google who did not
     need telling. */
  const [maybeGoogleOnly, setMaybeGoogleOnly] = useState(false);

  async function onSubmit() {
    setError(null);
    setMaybeGoogleOnly(false);
    setBusy(true);
    try {
      const res = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: { email: email.trim(), password },
      });
      // Setting the token flips the root navigator to the app; no manual
      // navigate. The role rides along so the experience is restored.
      await login(res.access_token, res.role);
    } catch (err) {
      setError(errorText(err, t));
      // See maybeGoogleOnly above for why this is a hint and not a sentence
      // the server sent. The button has to be on screen for it to point at.
      setMaybeGoogleOnly(looksLikeWrongPassword(err));
      setBusy(false);
    }
  }

  /* ONE ENDPOINT FOR SIGNING IN AND SIGNING UP, because the client cannot know
     which it is doing: whether a Google address already has a Kolabo account
     is a question only the server can answer, and asking it separately would
     also be an "is this person on Kolabo" oracle for anyone with a list of
     addresses.

     So there are exactly three outcomes worth handling. A token and a role,
     which is a sign in. auth_google_profile_required, which is not an error
     and opens the panel. Anything else, which errorText already has a sentence
     for in both languages.

     busy is NOT cleared on the success path, deliberately: login() flips the
     root navigator and this screen unmounts, so setting state afterwards would
     be a write to a component that is gone. */
  async function signIn(credential: string, role?: Role, country?: string) {
    setError(null);
    setMaybeGoogleOnly(false);
    setBusy(true);
    try {
      const res = await signInWithGoogle(
        credential,
        role && country ? { role, country_code: country } : undefined
      );
      await login(res.access_token, res.role);
    } catch (err) {
      if (needsProfileAnswers(err)) {
        // Held so the second call can send the SAME token. See GoogleQuestions.
        setGoogleToken(credential);
        setError(null);
      } else {
        setError(errorText(err, t));
      }
      setBusy(false);
    }
  }

  return (
    <Screen>
      {/* THE LANGUAGE CONTROL, ABOVE THE TITLE AND OUT AT THE EDGE, which is
          where web keeps its own: in the header bar, right of the logo, on
          every page a signed out visitor can reach. A person who cannot read
          this screen has to be able to change it without reading it, so it
          comes before the words rather than after the form.

          Compact rather than the account screen's card, because this screen
          has one job and a titled settings card would be a second thing to
          read. Same component either way, so the choice cannot behave
          differently in the two places. See components/LanguageSwitch.tsx. */}
      <View style={{ alignItems: "flex-end", marginBottom: space(3) }}>
        <LanguageSwitch />
      </View>
      <Title>{t("auth.loginTitle")}</Title>
      <Subtitle>{t("auth.loginSub")}</Subtitle>
      {googleToken ? (
        /* In place of the form rather than beside it: there is exactly one
           thing to do next, and a form underneath it would be two. */
        <GoogleQuestions
          busy={busy}
          error={error}
          onSubmit={(role, country) => void signIn(googleToken, role, country)}
          onCancel={() => {
            setGoogleToken(null);
            setError(null);
          }}
        />
      ) : (
        <Card>
          {error ? <Banner kind="error">{error}</Banner> : null}
          {/* FIRST IN THE CARD, unlike the register screen, where it is last.
              Nothing on this form feeds it: the first call carries the token
              and nothing else, and the two questions are asked afterwards and
              only if the address turns out to be new. Both of these draw
              nothing when no Google web client id is configured. */}
          <GoogleSignInButton
            onCredential={(credential) => void signIn(credential)}
            disabled={busy}
          />
          <GoogleDivider />
          <Field
            label={t("auth.email")}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
          />
          <Field
            label={t("auth.password")}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            /* Beside the field that just failed, which is where somebody is
               already looking, and only after it has failed. The button is
               what it points at, so it is not shown when there is no button:
               GoogleSignInButton draws nothing without a client id, and a hint
               pointing at nothing is worse than no hint. */
            hint={maybeGoogleOnly ? t("auth.googleWrongPassword") : undefined}
          />
          <PrimaryButton
            title={busy ? t("common.working") : t("auth.submitLogin")}
            onPress={onSubmit}
            loading={busy}
            disabled={!email.trim() || !password}
          />
          <View style={{ marginTop: space(3) }}>
            <GhostButton title={t("reset.forgot")} onPress={() => navigation.navigate("ForgotPassword")} />
          </View>
        </Card>
      )}
      <View style={{ marginTop: space(4), alignItems: "center" }}>
        <Text style={{ fontFamily: family.body, color: colors.muted, fontSize: font.small }}>
          {t("auth.needAccount")}{" "}
          <Text style={{ color: colors.teal600, fontFamily: family.bodySemi }} onPress={() => navigation.navigate("Register")}>
            {t("auth.signupLink")}
          </Text>
        </Text>
      </View>
      <View style={{ height: space(2) }} />
      <Hint>{t("dash.comingSoon")}</Hint>
    </Screen>
  );
}
