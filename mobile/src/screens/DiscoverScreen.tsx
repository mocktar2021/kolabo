import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";
import { SOCIAL_PLATFORMS } from "../lib/socialPlatforms";
import type { SearchResult } from "../lib/discoveryTypes";
import { Banner, ChoiceGroup, Field, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* Discovery, the brand's storefront aisle. Mirrors web/src/pages/Discover.tsx
   against the same public GET /discovery/search: category, country, platform
   and min-followers narrow; results come back verified-first. Search itself
   needs no login (a creator's storefront exists to be found) — only the
   favourites are a signed-in feature, and on mobile every viewer is signed
   in anyway. */

/* Single-select chip rows model "no filter" as a real option, because a chip
   row has no blank state the way a <select> has an empty option. */
const ANY = "";

function CreatorRow({ r, fav, onFav, onOpen }: {
  r: SearchResult;
  fav: boolean;
  onFav: () => void;
  onOpen: () => void;
}) {
  const { t, i18n } = useTranslation();
  const avatar = mediaSrc(r.avatar_url);
  return (
    <Pressable onPress={onOpen} style={({ pressed }) => [styles.card, pressed && { backgroundColor: colors.surface }]}>
      <View style={{ flexDirection: "row", gap: space(3) }}>
        {avatar ? (
          <Image source={{ uri: avatar }} style={styles.avatar} />
        ) : (
          <View style={[styles.avatar, styles.avatarEmpty]}>
            <Text style={styles.avatarLetter}>{(r.display_name || "?").charAt(0).toUpperCase()}</Text>
          </View>
        )}
        <View style={{ flex: 1 }}>
          <View style={styles.nameRow}>
            <Text style={styles.name} numberOfLines={1}>
              {r.display_name || t("discover.creator")}
            </Text>
            {r.is_verified ? <Text style={styles.verified}>{t("discover.verified")}</Text> : null}
          </View>
          {r.headline ? (
            <Text style={styles.headline} numberOfLines={1}>{r.headline}</Text>
          ) : null}
          <Text style={styles.meta}>
            {r.follower_count !== null
              ? `${r.follower_count.toLocaleString(i18n.language)} ${t("discover.followers")}`
              : ""}
            {r.follower_count !== null && r.categories.length > 0 ? " · " : ""}
            {r.categories.slice(0, 3).map((c) => t(`cat.${c}`, { defaultValue: c })).join(", ")}
          </Text>
          <Text style={styles.price}>
            {r.starting_price_amount !== null
              ? t("discover.from", {
                  price: `${r.starting_price_amount.toLocaleString(i18n.language)} ${r.starting_price_currency}`,
                })
              : t("discover.onRequest")}
          </Text>
        </View>
        <Text
          style={[styles.favBtn, fav && styles.favOn]}
          onPress={(e) => {
            e.stopPropagation();
            onFav();
          }}
          accessibilityLabel={t("discover.favorite")}
        >
          {fav ? "♥" : "♡"}
        </Text>
      </View>
    </Pressable>
  );
}

export default function DiscoverScreen({ navigation }: AppScreenProps<"Discover">) {
  const { t } = useTranslation();
  const { token } = useAuth();

  const [category, setCategory] = useState(ANY);
  const [country, setCountry] = useState(ANY);
  const [platform, setPlatform] = useState(ANY);
  const [minFollowers, setMinFollowers] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [refreshing, setRefreshing] = useState(false);
  const search = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (category) qs.set("category", category);
      if (country) qs.set("country", country);
      if (platform) qs.set("platform", platform);
      if (minFollowers) qs.set("min_followers", minFollowers);
      setResults(await api<SearchResult[]>(`/discovery/search?${qs.toString()}`));
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }, [category, country, platform, minFollowers, t]);

  // First load: the unfiltered board, so the screen opens showing people
  // rather than an empty form.
  useEffect(() => {
    void search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!token) return;
    api<{ influencer_user_id: string }[]>("/discovery/favorites", { token })
      .then((favs) => setFavorites(new Set(favs.map((f) => f.influencer_user_id))))
      .catch(() => undefined);
  }, [token]);

  async function toggleFavorite(id: string) {
    const isFav = favorites.has(id);
    try {
      if (isFav) {
        await api(`/discovery/favorites/${id}`, { method: "DELETE", token });
        setFavorites((prev) => {
          const n = new Set(prev);
          n.delete(id);
          return n;
        });
      } else {
        await api(`/discovery/favorites/${id}`, { method: "POST", token });
        setFavorites((prev) => new Set(prev).add(id));
      }
    } catch (e) {
      setError(errorText(e, t));
    }
  }

  return (
    <Screen
      loading={results === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void search().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("discover.title")}</Title>
      <Subtitle>{t("discover.sub")}</Subtitle>

      <View style={{ marginBottom: space(3) }}>
        <GhostButton
          title={showFilters ? t("discover.hideFilters") : t("discover.showFilters")}
          onPress={() => setShowFilters((v) => !v)}
        />
      </View>

      {showFilters ? (
        <View style={styles.filters}>
          <Text style={styles.fieldLabel}>{t("discover.category")}</Text>
          <ChoiceGroup
            options={[
              { value: ANY, label: t("discover.any") },
              ...CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) })),
            ]}
            value={category}
            onChange={setCategory}
          />

          <Text style={[styles.fieldLabel, { marginTop: space(3) }]}>{t("discover.country")}</Text>
          <ChoiceGroup
            options={[
              { value: ANY, label: t("discover.any") },
              ...COUNTRIES.map((c) => ({ value: c.code, label: c.name })),
            ]}
            value={country}
            onChange={setCountry}
          />

          <Text style={[styles.fieldLabel, { marginTop: space(3) }]}>{t("discover.platform")}</Text>
          <ChoiceGroup
            options={[
              { value: ANY, label: t("discover.any") },
              ...SOCIAL_PLATFORMS.map((p) => ({ value: p.id, label: p.label })),
            ]}
            value={platform}
            onChange={setPlatform}
          />

          <View style={{ marginTop: space(3) }}>
            <Field
              label={t("discover.minFollowers")}
              value={minFollowers}
              onChangeText={(v) => setMinFollowers(v.replace(/\D/g, ""))}
              keyboardType="number-pad"
              placeholder="1000"
            />
          </View>

          <PrimaryButton
            title={busy ? t("common.working") : t("discover.searchBtn")}
            onPress={() => void search()}
            loading={busy}
          />
        </View>
      ) : null}

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void search()} />
          </View>
        </>
      ) : null}

      {results === null ? null : results.length === 0 ? (
        <>
          <Text style={{ color: colors.ink, fontSize: font.body }}>{t("discover.empty")}</Text>
          <Hint>{t("discover.emptyHint")}</Hint>
        </>
      ) : (
        <View style={{ gap: space(2) }}>
          {results.map((r) => (
            <CreatorRow
              key={r.user_id}
              r={r}
              fav={favorites.has(r.user_id)}
              onFav={() => void toggleFavorite(r.user_id)}
              onOpen={() => navigation.navigate("CreatorPublic", { userId: r.user_id })}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  filters: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
    marginBottom: space(3),
  },
  fieldLabel: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(1.5) },
  card: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.surface2 },
  avatarEmpty: { alignItems: "center", justifyContent: "center" },
  avatarLetter: { fontSize: font.h2, fontWeight: "700", color: colors.muted },
  nameRow: { flexDirection: "row", alignItems: "center", gap: space(2) },
  name: { fontSize: font.body, fontWeight: "700", color: colors.ink, flexShrink: 1 },
  verified: {
    fontSize: font.tiny,
    fontWeight: "600",
    color: colors.teal600,
    backgroundColor: "#e7f6f0",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 2,
    overflow: "hidden",
  },
  headline: { fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  meta: { fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  price: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginTop: space(1.5) },
  favBtn: { fontSize: 22, color: colors.muted, paddingHorizontal: space(1) },
  favOn: { color: colors.danger },
});
