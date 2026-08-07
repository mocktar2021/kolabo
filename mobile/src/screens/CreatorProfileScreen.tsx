import { useCallback, useEffect, useState } from "react";
import { Image, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api, mediaSrc, uploadMedia, type MediaOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { pickImage } from "../lib/imagePicker";
import { COUNTRIES, joinLocation, splitLocation } from "../lib/countries";
import { CATEGORIES } from "../lib/categories";
import type { InfluencerProfile, InfluencerProfileInput, OnboardingStatus } from "../lib/profileTypes";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  GhostButton,
  Hint,
  MultiChoiceGroup,
  PrimaryButton,
  Screen,
  SectionTitle,
  Subtitle,
  Title,
  type Choice,
} from "../components/ui";
import { SocialsSection } from "../components/profile/SocialsSection";
import { PackagesSection } from "../components/profile/PackagesSection";
import { PortfolioSection } from "../components/profile/PortfolioSection";
import { colors, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const LANGUAGES: Choice[] = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
];

export default function CreatorProfileScreen({ navigation }: AppScreenProps<"CreatorProfile">) {
  const { t } = useTranslation();
  const { userId, token } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
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
      setBirthDate(p.birth_date ?? "");
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
        birth_date: birthDate || null,
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
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({ value: c.code, label: c.name }));
  const categoryOptions: Choice[] = CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) }));

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
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>
      <Title>{t("profile.title")}</Title>
      <Subtitle>{t("profile.sub")}</Subtitle>

      {status ? (
        <Card>
          <SectionTitle>{t("profile.goLiveTitle")}</SectionTitle>
          {checklist.map((row) => (
            <View key={row.label} style={{ flexDirection: "row", alignItems: "center", gap: space(2), paddingVertical: 3 }}>
              <Text style={{ color: row.ok ? colors.teal600 : colors.muted, width: 16 }}>{row.ok ? "✓" : "○"}</Text>
              <Text style={{ color: row.ok ? colors.ink : colors.muted, fontSize: font.small }}>{row.label}</Text>
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
              <Text style={{ fontSize: font.h1, fontWeight: "700", color: colors.muted }}>
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

        <Text style={styles.label}>{t("profile.country")}</Text>
        <ChoiceGroup options={countryOptions} value={country} onChange={setCountry} />
        <View style={{ height: space(3) }} />
        <Field label={t("profile.city")} value={city} onChangeText={setCity} placeholder="Cotonou" />

        <Field
          label={t("profile.birthDate")}
          value={birthDate}
          onChangeText={setBirthDate}
          placeholder="1998-04-20"
          autoCapitalize="none"
          hint={t("profile.birthDateHint")}
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
  label: { fontSize: font.small, fontWeight: "600" as const, color: colors.ink, marginBottom: space(1.5) },
};
