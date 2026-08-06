import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { SOCIAL_PLATFORMS, platformHasAudience, type SocialPlatform } from "../../lib/socialPlatforms";
import { PLATFORM_LABELS } from "../../lib/platforms";
import type { SocialAccount } from "../../lib/profileTypes";
import { Banner, Field, GhostButton, Hint, PrimaryButton, SectionTitle } from "../ui";
import { colors, font, radius, space } from "../../theme";

/* Connected accounts + an inline add flow. Connecting always goes in as a
   manual proof (status "pending") — there is no OAuth handshake in the UI yet,
   the same as web. If the connect response says it enriched, the parent
   reloads so the auto-filled profile fields show at once. */
export function SocialsSection({
  userId,
  token,
  onChanged,
}: {
  userId: string;
  token: string | null;
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [adding, setAdding] = useState<SocialPlatform | null>(null);
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrichedNote, setEnrichedNote] = useState(false);

  const load = useCallback(async () => {
    try {
      setAccounts(await api<SocialAccount[]>(`/profiles/${userId}/social-accounts`, { token }));
    } catch {
      // A failed list is not worth an error state on this section.
    }
  }, [userId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const connected = new Set(accounts.map((a) => a.platform));

  async function add() {
    if (!adding || !handle.trim()) return;
    setBusy(true);
    setError(null);
    const clean = handle.trim().replace(/^@/, "");
    try {
      const res = await api<SocialAccount>(`/profiles/${userId}/social-accounts`, {
        method: "POST",
        token,
        body: {
          platform: adding.id,
          handle: clean,
          method: "manual",
          proof_url: `https://${adding.prefix}${clean}`,
        },
      });
      setAdding(null);
      setHandle("");
      await load();
      if (res.enriched) {
        setEnrichedNote(true);
        await onChanged();
      }
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/profiles/${userId}/social-accounts/${id}`, { method: "DELETE", token });
    } catch {
      // ignore; the list reload below reflects the true state
    }
    void load();
  }

  return (
    <View>
      <SectionTitle>{t("profile.socialTitle")}</SectionTitle>
      <Hint>{t("profile.socialSub")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {enrichedNote ? <Banner kind="success">{t("profile.enriched")}</Banner> : null}

      {accounts.length === 0 ? (
        <Hint>{t("profile.socialEmpty")}</Hint>
      ) : (
        <View style={{ gap: space(2), marginTop: space(2) }}>
          {accounts.map((a) => (
            <View key={a.id} style={styles.row}>
              <View style={{ flexShrink: 1 }}>
                <Text style={styles.rowTitle}>{PLATFORM_LABELS[a.platform] ?? a.platform}</Text>
                <Text style={styles.rowSub}>
                  @{a.handle}
                  {a.follower_count !== null && a.follower_count !== undefined
                    ? ` · ${a.follower_count.toLocaleString()}`
                    : ""}
                </Text>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: space(2) }}>
                <Text style={[styles.chip, a.status === "verified" ? styles.chipOk : styles.chipMuted]}>
                  {a.status === "verified" ? t("profile.verified") : t("profile.pending")}
                </Text>
                <Text style={styles.remove} onPress={() => remove(a.id)}>
                  {t("profile.remove")}
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {adding ? (
        <View style={{ marginTop: space(3) }}>
          <Field
            label={t("profile.handleFor", { platform: adding.label })}
            value={handle}
            onChangeText={(v) => setHandle(v.replace(/^@/, ""))}
            autoCapitalize="none"
            placeholder={adding.prefix}
          />
          {!platformHasAudience(adding.id) ? <Hint>{t("profile.noAudienceHint")}</Hint> : null}
          <View style={{ flexDirection: "row", gap: space(2), marginTop: space(2) }}>
            <View style={{ flex: 1 }}>
              <PrimaryButton
                title={busy ? t("common.working") : t("profile.addToProfile")}
                onPress={add}
                loading={busy}
                disabled={!handle.trim()}
              />
            </View>
            <View style={{ flex: 1 }}>
              <GhostButton
                title={t("common.cancel")}
                onPress={() => {
                  setAdding(null);
                  setHandle("");
                }}
              />
            </View>
          </View>
        </View>
      ) : (
        <View style={{ marginTop: space(3) }}>
          <Text style={styles.addLabel}>{t("profile.socialAdd")}</Text>
          <View style={styles.tiles}>
            {SOCIAL_PLATFORMS.map((p) => {
              const on = connected.has(p.id);
              return (
                <Pressable
                  key={p.id}
                  disabled={on}
                  onPress={() => {
                    setAdding(p);
                    setHandle("");
                    setError(null);
                  }}
                  style={[styles.tile, on && styles.tileOn]}
                >
                  <Text style={[styles.tileText, on && styles.tileTextOn]}>{p.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    gap: space(2),
  },
  rowTitle: { fontSize: font.body, fontWeight: "600", color: colors.ink },
  rowSub: { fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  chip: { fontSize: font.tiny, fontWeight: "600", overflow: "hidden", borderRadius: radius.pill, paddingHorizontal: space(2), paddingVertical: 3 },
  chipOk: { backgroundColor: "#e7f6f0", color: colors.success },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  remove: { fontSize: font.small, color: colors.danger, fontWeight: "600" },
  addLabel: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(2) },
  tiles: { flexDirection: "row", flexWrap: "wrap", gap: space(2) },
  tile: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2.5),
    minWidth: 96,
    alignItems: "center",
  },
  tileOn: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  tileText: { fontSize: font.small, fontWeight: "600", color: colors.ink },
  tileTextOn: { color: colors.teal600 },
});
