import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { relativeParts } from "../lib/notifications";
import type { MessageThread } from "../lib/messageTypes";
import { Banner, GhostButton, Hint, Screen, Subtitle, Title } from "../components/ui";
import { colors, family, font, radius, shadow, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* The inbox: one row per person, from GET /messaging/threads — the same
   payload the web inbox reads. The empty state says WHEN conversations open
   rather than apologising for having none: a thread only ever exists
   alongside a contract, and somebody who does not know that reads an empty
   inbox as a broken feature. */
export default function MessagesScreen({ navigation }: AppScreenProps<"Messages">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [threads, setThreads] = useState<MessageThread[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setThreads(await api<MessageThread[]>("/messaging/threads", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [token, t]);

  useEffect(() => navigation.addListener("focus", () => void load()), [navigation, load]);
  useEffect(() => {
    void load();
  }, [load]);

  const loading = threads === null;
  const empty = !loading && threads.length === 0;

  return (
    <Screen
      loading={threads === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("msg.title")}</Title>
      <Subtitle>{t("msg.sub")}</Subtitle>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {loading ? null : empty ? (
        <>
          <Text style={styles.emptyText}>{t("msg.empty")}</Text>
          <Hint>{t("msg.emptyHint")}</Hint>
        </>
      ) : (
        <View style={{ gap: space(2) }}>
          {threads.map((th) => {
            const avatar = mediaSrc(th.counterparty_avatar_url);
            const name = th.counterparty_name || t("msg.unknownParty");
            const when = th.last_message_at ? relativeParts(th.last_message_at) : null;
            return (
              <Pressable
                key={th.counterparty_user_id}
                onPress={() =>
                  navigation.navigate("MessageThread", {
                    userId: th.counterparty_user_id,
                    name,
                  })
                }
                style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surface }]}
              >
                {avatar ? (
                  <Image source={{ uri: avatar }} style={styles.avatar} />
                ) : (
                  <View style={[styles.avatar, styles.avatarEmpty]}>
                    <Text style={styles.avatarLetter}>{name.charAt(0).toUpperCase()}</Text>
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <View style={styles.rowTop}>
                    <Text style={styles.name} numberOfLines={1}>{name}</Text>
                    {when ? (
                      <Text style={styles.when}>{t(when.key, { n: when.n })}</Text>
                    ) : null}
                  </View>
                  <Text style={styles.meta} numberOfLines={1}>
                    {th.campaign_title || ""}
                    {th.contract_count > 1
                      ? `${th.campaign_title ? " · " : ""}${t("msg.contractsCount", { n: th.contract_count })}`
                      : ""}
                  </Text>
                  {th.last_message ? (
                    <Text
                      style={[styles.preview, th.unread_count > 0 && styles.previewUnread]}
                      numberOfLines={1}
                    >
                      {th.last_message}
                    </Text>
                  ) : (
                    <Text style={styles.preview}>{t("msg.noMessages")}</Text>
                  )}
                </View>
                {th.unread_count > 0 ? (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{th.unread_count}</Text>
                  </View>
                ) : null}
              </Pressable>
            );
          })}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  emptyText: { fontSize: font.body, fontFamily: family.body, color: colors.ink },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(3),
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
    ...shadow.sm,
  },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.surface2 },
  avatarEmpty: { alignItems: "center", justifyContent: "center" },
  avatarLetter: { fontSize: font.h2, fontFamily: family.displaySemi, color: colors.muted },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  name: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink, flexShrink: 1 },
  when: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted },
  meta: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: 1 },
  preview: { fontSize: font.small, fontFamily: family.body, color: colors.muted, marginTop: 3 },
  previewUnread: { color: colors.ink, fontFamily: family.bodySemi },
  badge: {
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.indigo,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  badgeText: { color: colors.white, fontSize: font.tiny - 1, fontFamily: family.bodyBold },
});
