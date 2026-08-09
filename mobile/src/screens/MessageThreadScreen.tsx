import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/dates";
import { MESSAGE_MAX_LENGTH, type Message } from "../lib/messageTypes";
import { Banner, GhostButton, PrimaryButton, Screen } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* One conversation, with the person named in the header. Reading is
   GET /messaging/with/{userId} — which also marks the thread read
   server-side — and sending posts to the same path with just {body}: the
   recipient is in the path, and the server stamps the message with the most
   recent shared contract, so provenance (which job this was about — what a
   dispute reads) survives without the client choosing a campaign.

   Messages are refetched after sending rather than appended locally: the
   server assigns the id and the timestamp, and a message that exists only on
   screen is the one that turns out never to have been sent. */
export default function MessageThreadScreen({ route }: AppScreenProps<"MessageThread">) {
  const { userId } = route.params;
  const { t, i18n } = useTranslation();
  const { token, userId: myId } = useAuth();

  const [messages, setMessages] = useState<Message[] | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setMessages(
        await api<Message[]>(`/messaging/with/${encodeURIComponent(userId)}`, { token })
      );
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [token, userId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send() {
    const trimmed = body.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/messaging/with/${encodeURIComponent(userId)}`, {
        method: "POST",
        token,
        body: { body: trimmed },
      });
      setBody("");
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  function when(iso: string): string {
    const d = parseApiDate(iso);
    return d ? d.toLocaleString(i18n.language) : "";
  }

  return (
    <Screen
      loading={messages === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {messages === null ? null : messages.length === 0 ? (
        <Text style={styles.none}>{t("msg.noMessages")}</Text>
      ) : (
        <View style={{ gap: space(2) }}>
          {messages.map((m) => {
            const mine = m.sender_user_id === myId;
            return (
              <View key={m.id} style={[styles.bubbleWrap, mine && styles.bubbleWrapMine]}>
                <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}>
                  <Text style={[styles.body, mine && styles.bodyMine]}>{m.body}</Text>
                </View>
                <Text style={styles.time}>{when(m.created_at)}</Text>
              </View>
            );
          })}
        </View>
      )}

      <View style={styles.composer}>
        <TextInput
          style={styles.input}
          value={body}
          onChangeText={setBody}
          placeholder={t("msg.placeholder")}
          placeholderTextColor={colors.muted}
          multiline
          maxLength={MESSAGE_MAX_LENGTH}
        />
        <PrimaryButton
          title={busy ? t("common.working") : t("msg.send")}
          onPress={() => void send()}
          loading={busy}
          disabled={body.trim().length === 0}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  none: { fontSize: font.body, fontFamily: family.body, color: colors.muted },
  bubbleWrap: { alignItems: "flex-start" },
  bubbleWrapMine: { alignItems: "flex-end" },
  bubble: {
    maxWidth: "82%",
    borderRadius: radius.md,
    paddingHorizontal: space(3),
    paddingVertical: space(2.5),
  },
  bubbleTheirs: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line },
  bubbleMine: { backgroundColor: colors.indigo },
  body: { fontSize: font.body, fontFamily: family.body, color: colors.ink, lineHeight: 21 },
  bodyMine: { color: colors.white },
  time: { fontSize: font.tiny - 1, fontFamily: family.body, color: colors.muted, marginTop: 2 },
  composer: { marginTop: space(4), gap: space(2) },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(3),
    fontSize: font.body,
    fontFamily: family.body,
    color: colors.ink,
    backgroundColor: colors.white,
    minHeight: 44,
    maxHeight: 120,
  },
});
