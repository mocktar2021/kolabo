import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { isBusinessLike, useAuth } from "../lib/auth";
import { PLATFORM_LABELS, deliverableLabel } from "../lib/platforms";
import type { DirectOrder, PublicProfileData } from "../lib/discoveryTypes";
import type { Package } from "../lib/profileTypes";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* A creator's storefront, seen by a buyer. Mirrors the web PublicProfile's
   immediate-order path against the same endpoints: the profile is public
   (GET /profiles/influencer/{id}/public), and ordering a package is
   POST /campaigns/orders with {package_id, note}. Nothing is charged at
   order time — the creator has 48 h to accept, and escrow is funded only
   after the contract is signed. That rule is printed next to the button,
   because it is the fact that makes the button safe to press. */

function PackageRow({ p, selected, onSelect }: {
  p: Package;
  selected: boolean;
  onSelect: () => void;
}) {
  const { i18n } = useTranslation();
  return (
    <Pressable onPress={onSelect} style={[styles.pkg, selected && styles.pkgSelected]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space(2) }}>
        <Text style={[styles.pkgTitle, selected && { color: colors.teal600 }]} numberOfLines={2}>
          {p.title}
        </Text>
        <Text style={styles.pkgPrice}>
          {p.price_amount.toLocaleString(i18n.language)} {p.currency}
        </Text>
      </View>
      <Text style={styles.pkgSub}>
        {PLATFORM_LABELS[p.platform] ?? p.platform} · {deliverableLabel(p.deliverable_type)}
        {p.quantity > 1 ? ` · ×${p.quantity}` : ""}
      </Text>
    </Pressable>
  );
}

export default function CreatorPublicScreen({ navigation, route }: AppScreenProps<"CreatorPublic">) {
  const { userId } = route.params;
  const { t, i18n } = useTranslation();
  const { token, role, userId: viewerId } = useAuth();

  const [profile, setProfile] = useState<PublicProfileData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [ordered, setOrdered] = useState<DirectOrder | null>(null);

  const load = useCallback(async () => {
    try {
      const p = await api<PublicProfileData>(
        `/profiles/influencer/${userId}/public?language=${i18n.language}`
      );
      setProfile(p);
      setSelectedId((prev) => prev ?? p.packages.find((x) => x.is_active)?.id ?? null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else setError(errorText(e, t));
    }
  }, [userId, i18n.language, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const packages = profile?.packages.filter((p) => p.is_active) ?? [];
  const selectedPackage = packages.find((p) => p.id === selectedId) ?? packages[0] ?? null;

  /* Only the buying side may order — the same rule the API applies (403 to an
     influencer) — and nobody orders from themselves. */
  const canOrder = isBusinessLike(role) && viewerId !== userId;

  async function sendOrder() {
    if (!selectedPackage) return;
    setBusy(true);
    setOrderError(null);
    try {
      const trimmed = note.trim();
      const res = await api<DirectOrder>("/campaigns/orders", {
        method: "POST",
        token,
        body: { package_id: selectedPackage.id, note: trimmed || null },
      });
      setOrdered(res);
      setConfirming(false);
    } catch (e) {
      setOrderError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return (
      <Screen>
        <View style={{ marginBottom: space(2) }}>
          <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
        </View>
        <Banner kind="error">{t("public.notFound")}</Banner>
      </Screen>
    );
  }

  const avatar = mediaSrc(profile?.avatar_url);

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>

      {error ? <Banner kind="error">{error}</Banner> : null}
      {profile === null ? null : (
        <>
          <View style={styles.head}>
            {avatar ? (
              <Image source={{ uri: avatar }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatar, styles.avatarEmpty]}>
                <Text style={styles.avatarLetter}>
                  {(profile.display_name || "?").charAt(0).toUpperCase()}
                </Text>
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Title>{profile.display_name || t("discover.creator")}</Title>
              {profile.headline ? <Text style={styles.headline}>{profile.headline}</Text> : null}
              {profile.follower_count !== null ? (
                <Text style={styles.audience}>
                  {profile.follower_count.toLocaleString(i18n.language)} {t("public.audienceUnit")}
                </Text>
              ) : null}
            </View>
          </View>

          {profile.categories.length > 0 ? (
            <Text style={styles.cats}>
              {profile.categories.map((c) => t(`cat.${c}`, { defaultValue: c })).join(" · ")}
            </Text>
          ) : null}

          {profile.bio ? <Text style={styles.bio}>{profile.bio}</Text> : null}

          <SectionTitle>{t("public.packages")}</SectionTitle>
          {packages.length === 0 ? (
            <Hint>{t("public.noPackages")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {packages.map((p) => (
                <PackageRow
                  key={p.id}
                  p={p}
                  selected={selectedPackage?.id === p.id}
                  onSelect={() => setSelectedId(p.id)}
                />
              ))}
            </View>
          )}

          {canOrder && selectedPackage ? (
            <View style={{ marginTop: space(4) }}>
              {ordered ? (
                <Card>
                  <Banner kind="success">{t("public.orderSent")}</Banner>
                  <GhostButton
                    title={t("public.orderView")}
                    onPress={() => navigation.navigate("Campaigns")}
                  />
                </Card>
              ) : confirming ? (
                <Card>
                  <SectionTitle>{t("public.orderConfirm")}</SectionTitle>
                  <Text style={styles.confirmLine}>
                    {selectedPackage.title} — {selectedPackage.price_amount.toLocaleString(i18n.language)}{" "}
                    {selectedPackage.currency}
                  </Text>
                  {orderError ? <Banner kind="error">{orderError}</Banner> : null}
                  <Field
                    label={t("public.orderNote")}
                    value={note}
                    onChangeText={setNote}
                    multiline
                    numberOfLines={3}
                  />
                  <Hint>{t("public.orderRule")}</Hint>
                  <View style={{ height: space(3) }} />
                  <PrimaryButton
                    title={busy ? t("common.working") : t("public.orderSend")}
                    onPress={sendOrder}
                    loading={busy}
                  />
                  <View style={{ height: space(2) }} />
                  <GhostButton title={t("public.orderCancel")} onPress={() => setConfirming(false)} />
                </Card>
              ) : (
                <PrimaryButton title={t("public.order")} onPress={() => setConfirming(true)} />
              )}
            </View>
          ) : null}

          <SectionTitle>{t("public.howItWorks")}</SectionTitle>
          <View style={{ gap: space(1) }}>
            <Hint>{t("public.how1")}</Hint>
            <Hint>{t("public.how2")}</Hint>
            <Hint>{t("public.how3")}</Hint>
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: "row", gap: space(3), alignItems: "center", marginBottom: space(2) },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.surface2 },
  avatarEmpty: { alignItems: "center", justifyContent: "center" },
  avatarLetter: { fontSize: font.h1, fontWeight: "700", color: colors.muted },
  headline: { fontSize: font.small, color: colors.muted, marginTop: -space(1) },
  audience: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginTop: space(1) },
  cats: { fontSize: font.tiny, color: colors.muted, marginBottom: space(2) },
  bio: { fontSize: font.small, color: colors.ink, marginBottom: space(2) },
  pkg: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  pkgSelected: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  pkgTitle: { fontSize: font.body, fontWeight: "700", color: colors.ink, flexShrink: 1 },
  pkgPrice: { fontSize: font.body, fontWeight: "700", color: colors.ink },
  pkgSub: { fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  confirmLine: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(3) },
});
