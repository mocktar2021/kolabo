import { useCallback, useEffect, useState } from "react";
import { Image, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api, mediaSrc, uploadMedia, type MediaOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { pickImage } from "../lib/imagePicker";
import { CITIES, COUNTRIES, countryName, joinLocation, splitLocation } from "../lib/countries";
import { fromIsoDay, maxBirthDate, toIsoDay } from "../lib/dates";
import { CATEGORIES } from "../lib/categories";
import type { InfluencerProfile, InfluencerProfileInput, OnboardingStatus } from "../lib/profileTypes";
import {
  Banner,
  Card,
  ChoiceGroup,
  DateField,
  Field,
  GhostButton,
  Hint,
  MultiChoiceGroup,
  PrimaryButton,
  Screen,
  SectionTitle,
  Select,
  Subtitle,
  type Choice,
} from "../components/ui";
import { SocialsSection } from "../components/profile/SocialsSection";
import { PackagesSection } from "../components/profile/PackagesSection";
import { PortfolioSection } from "../components/profile/PortfolioSection";
import { colors, family, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const LANGUAGES: Choice[] = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
];

export default function CreatorProfileScreen({ navigation }: AppScreenProps<"CreatorProfile">) {
  const { t, i18n } = useTranslation();
  const { userId, token } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  /* Mirrors web ProfileSetup's cityOther: true once the person has asked for
     free text, so picking "Other…" doesn't immediately snap back to the list. */
  const [cityOther, setCityOther] = useState(false);
  /* Held in DD/MM/YYYY — what people here write — and converted to the API's
     ISO form at the save edge. */
  const [birthDate, setBirthDate] = useState("");
  const [bio, setBio] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [languages, setLanguages] = useState<string[]>([]);
  const [gender, setGender] = useState("");
  const [followers, setFollowers] = useState("");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [avatarBusy, setAvatarBusy] = useState(false);

  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    if (!userId) return;
    try {
      setStatus(await api<OnboardingStatus>(`/profiles/${userId}/onboarding-status`, { token }));
    } catch {
      // status is a nicety; a failure just leaves the checklist unfilled
    }
  }, [userId, token]);

  const loadProfile = useCallback(async () => {
    if (!userId) return;
    try {
      const p = await api<InfluencerProfile>(`/profiles/influencer/${userId}`, { token });
      setDisplayName(p.display_name ?? "");
      setHeadline(p.headline ?? "");
      const loc = splitLocation(p.location);
      setCity(loc.city);
      setCountry(loc.country);
      setBirthDate(fromIsoDay(p.birth_date ?? ""));
      setBio(p.bio ?? "");
      setCategories(p.categories ?? []);
      setLanguages(p.languages ?? []);
      setGender(p.gender ?? "");
      setFollowers(p.follower_count ? String(p.follower_count) : "");
      setAvatarUrl(p.avatar_url ?? null);
    } catch (e) {
      // A 404 just means "no profile yet" — a blank form is the right state.
      if (!(e instanceof ApiError && e.status === 404)) setError(errorText(e, t));
    }
  }, [userId, token, t]);

  useEffect(() => {
    void loadProfile();
    void loadStatus();
  }, [loadProfile, loadStatus]);

  function toggle(list: string[], value: string): string[] {
    return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
  }

  /* The avatar saves immediately rather than riding the form's save button:
     upload the bytes, then a one-field PUT — the upsert is exclude_unset, so
     nothing else on the (possibly half-edited) form is touched. */
  async function changeAvatar() {
    if (!userId) return;
    const file = await pickImage();
    if (!file) return;
    setAvatarBusy(true);
    setError(null);
    try {
      const media = await uploadMedia<MediaOut>(`/profiles/${userId}/media`, file, token);
      await api(`/profiles/influencer/${userId}`, {
        method: "PUT",
        token,
        body: { avatar_media_id: media.id },
      });
      setAvatarUrl(media.url);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setAvatarBusy(false);
    }
  }

  async function save() {
    if (!userId) return;
    /* The date is validated here, at the same edge where it is converted:
       the web's <input type="date"> makes a bad day untypeable, so the API
       has never needed to be graceful about one.

       THE BRANCH BELOW STAYS, even though the calendar cannot trip it any
       more. birthDate is also filled from the API in loadProfile, so the
       value being checked has never come from one place only, and a guard
       dropped because one of its two callers stopped needing it is a guard
       dropped from the other caller as well. It costs a parse of eleven
       characters. */
    const isoBirth = birthDate.trim() ? toIsoDay(birthDate) : null;
    if (birthDate.trim() && !isoBirth) {
      setSaved(false);
      setError(t("profile.birthDateBad"));
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const body: InfluencerProfileInput = {
        display_name: displayName || null,
        headline: headline || null,
        location: joinLocation(city, country),
        bio: bio || null,
        categories,
        follower_count: followers ? Number(followers) : null,
        birth_date: isoBirth,
        gender: gender || null,
        languages,
      };
      await api(`/profiles/influencer/${userId}`, { method: "PUT", token, body });
      setSaved(true);
      await loadStatus();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const genderOptions: Choice[] = [
    { value: "", label: t("profile.genderNone") },
    { value: "female", label: t("profile.genderFemale") },
    { value: "male", label: t("profile.genderMale") },
    { value: "other", label: t("profile.genderOther") },
    { value: "prefer_not_to_say", label: t("profile.genderNoSay") },
  ];
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({ value: c.code, label: countryName(c, i18n.language) }));
  const categoryOptions: Choice[] = CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) }));

  /* Web ProfileSetup's cityIsFree, verbatim: free text when the country has
     no list, when "Other…" was chosen, or when the saved city is off-list. */
  const cityList = CITIES[country] ?? [];
  const cityIsFree = cityList.length === 0 || cityOther || (city !== "" && !cityList.includes(city));

  if (!userId) return null;

  const checklist = status
    ? [
        { ok: status.has_bio, label: t("profile.checkBio") },
        { ok: status.has_categories, label: t("profile.checkCategories") },
        { ok: status.has_birth_date, label: t("profile.checkBirthDate") },
        { ok: status.has_pricing, label: t("profile.checkPricing") },
        { ok: status.has_social, label: t("profile.checkSocial") },
      ]
    : [];

  return (
    <Screen>
      <Subtitle>{t("profile.sub")}</Subtitle>

      {status ? (
        <Card>
          <SectionTitle>{t("profile.goLiveTitle")}</SectionTitle>
          {checklist.map((row) => (
            <View key={row.label} style={{ flexDirection: "row", alignItems: "center", gap: space(2), paddingVertical: 3 }}>
              <Text style={{ color: row.ok ? colors.teal600 : colors.muted, width: 16 }}>{row.ok ? "✓" : "○"}</Text>
              <Text style={{ fontFamily: family.body, color: row.ok ? colors.ink : colors.muted, fontSize: font.small }}>{row.label}</Text>
            </View>
          ))}
          <View style={{ height: space(2) }} />
          {status.is_live ? (
            <>
              <Banner kind="success">{t("profile.live")}</Banner>
              <Hint>{t("profile.publicLink")}: /u/{userId}</Hint>
            </>
          ) : (
            <Banner kind="info">{t("profile.notLive")}</Banner>
          )}
        </Card>
      ) : null}

      <View style={{ height: space(4) }} />
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}
        {saved ? <Banner kind="success">{t("profile.saved")}</Banner> : null}

        <View style={{ flexDirection: "row", alignItems: "center", gap: space(3), marginBottom: space(4) }}>
          {avatarUrl ? (
            <Image
              source={{ uri: mediaSrc(avatarUrl) }}
              style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.surface2 }}
            />
          ) : (
            <View
              style={{
                width: 72,
                height: 72,
                borderRadius: 36,
                backgroundColor: colors.surface2,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ fontSize: font.h1, fontFamily: family.display, color: colors.muted }}>
                {(displayName || "?").charAt(0).toUpperCase()}
              </Text>
            </View>
          )}
          <View style={{ flex: 1 }}>
            <GhostButton
              title={avatarBusy ? t("common.working") : t("profile.uploadPhoto")}
              onPress={() => void changeAvatar()}
              disabled={avatarBusy}
            />
          </View>
        </View>

        <Field label={t("profile.displayName")} value={displayName} onChangeText={setDisplayName} placeholder="Ama K." />
        <Field label={t("profile.headline")} value={headline} onChangeText={setHeadline} hint={t("profile.headlineHint")} />

        <Select
          label={t("profile.country")}
          value={country}
          options={countryOptions}
          onChange={(v) => {
            setCountry(v);
            setCityOther(false);
          }}
          placeholder={t("profile.country")}
        />
        {/* City follows the web exactly: a dropdown of the country's major
            cities with an "Other…" escape back to free text, and free text
            whenever the saved city is not on the list — so an unusual city
            never blocks saving. */}
        {cityIsFree ? (
          <Field label={t("profile.city")} value={city} onChangeText={setCity} placeholder="Cotonou" />
        ) : (
          <Select
            label={t("profile.city")}
            value={city}
            options={[
              ...cityList.map((c) => ({ value: c, label: c })),
              { value: "__other__", label: t("profile.cityOther") },
            ]}
            onChange={(v) => {
              if (v === "__other__") {
                setCityOther(true);
                setCity("");
              } else {
                setCity(v);
              }
            }}
            placeholder={t("profile.city")}
          />
        )}

        {/* A calendar rather than a text box. The state stays DD/MM/YYYY and
            toIsoDay still runs at the save edge, so nothing about the wire
            format moved; what changed is that the only days reachable are
            days that parse. maxBirthDate is the 18+ rule the backend
            enforces in profiles service._require_adult, applied before the
            round trip instead of after it, so a fifteen year old is told by
            a greyed-out square rather than by a server error. */}
        <DateField
          label={t("profile.birthDate")}
          value={birthDate}
          onChange={setBirthDate}
          placeholder={t("profile.birthDateFormat")}
          hint={t("profile.birthDateHint")}
          maxDate={maxBirthDate()}
        />

        <Field label={t("profile.bio")} value={bio} onChangeText={setBio} multiline numberOfLines={4} />

        <Text style={styles.label}>{t("profile.categories")}</Text>
        <MultiChoiceGroup options={categoryOptions} values={categories} onToggle={(v) => setCategories((p) => toggle(p, v))} />

        <View style={{ height: space(3) }} />
        <Text style={styles.label}>{t("profile.languages")}</Text>
        <MultiChoiceGroup options={LANGUAGES} values={languages} onToggle={(v) => setLanguages((p) => toggle(p, v))} />

        <View style={{ height: space(3) }} />
        <Text style={styles.label}>{t("profile.gender")}</Text>
        <ChoiceGroup options={genderOptions} value={gender} onChange={setGender} />

        <View style={{ height: space(3) }} />
        <Field
          label={t("profile.followers")}
          value={followers}
          onChangeText={(v) => setFollowers(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          placeholder="10000"
        />

        <PrimaryButton title={busy ? t("common.working") : t("profile.save")} onPress={save} loading={busy} />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <SocialsSection userId={userId} token={token} onChanged={() => { void loadProfile(); void loadStatus(); }} />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <PortfolioSection userId={userId} token={token} />
      </Card>

      <View style={{ height: space(4) }} />
      <Card>
        <PackagesSection userId={userId} token={token} onChanged={loadStatus} />
      </Card>
    </Screen>
  );
}

const styles = {
  label: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
};
