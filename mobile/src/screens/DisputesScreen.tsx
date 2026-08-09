import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/dates";
import { respondTimeLeft, type Dispute } from "../lib/disputeTypes";
import { Banner, GhostButton, Hint, Screen, Subtitle, Title } from "../components/ui";
import { colors, family, font, radius, shadow, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* Every dispute the caller is a party to, newest first — the mobile mirror of
   the web /disputes page. Until now DisputeDetail was reachable only through
   a notification tap, which meant an open case with a running response clock
   was invisible to anybody who missed the ping. */
function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const open = status === "awaiting_response" || status === "awaiting_admin";
  return (
    <Text style={[styles.chip, open ? styles.chipOpen : styles.chipClosed]}>
      {t(`dispute.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

export default function DisputesScreen({ navigation }: AppScreenProps<"Disputes">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [disputes, setDisputes] = useState<Dispute[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setDisputes(await api<Dispute[]>("/payments/disputes/mine", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [token, t]);

  useEffect(() => navigation.addListener("focus", () => void load()), [navigation, load]);
  useEffect(() => {
    void load();
  }, [load]);

  const loading = disputes === null;

  return (
    <Screen
      loading={disputes === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("dispute.listTitle")}</Title>
      <Subtitle>{t("dispute.listSub")}</Subtitle>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {loading ? null : disputes.length === 0 ? (
        <Hint>{t("dispute.listEmpty")}</Hint>
      ) : (
        <View style={{ gap: space(2) }}>
          {disputes.map((d) => {
            const opened = parseApiDate(d.created_at);
            const left =
              d.status === "awaiting_response" ? respondTimeLeft(d.respond_by) : null;
            return (
              <Pressable
                key={d.id}
                onPress={() => navigation.navigate("DisputeDetail", { id: d.id })}
                style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surface }]}
              >
                <View style={styles.rowTop}>
                  <Text style={styles.reason} numberOfLines={1}>
                    {t(`dispute.reason_${d.reason}`, { defaultValue: d.reason })}
                  </Text>
                  <StatusChip status={d.status} />
                </View>
                <Text style={styles.meta}>
                  {opened
                    ? t("dispute.openedOn", { date: opened.toLocaleDateString(i18n.language) })
                    : ""}
                  {d.escrow
                    ? `  ·  ${d.escrow.amount.toLocaleString(i18n.language)} ${d.escrow.currency}`
                    : ""}
                </Text>
                {d.status === "awaiting_response" ? (
                  <Text style={styles.clock}>
                    {left === null
                      ? t("dispute.respondOverdue")
                      : left.unit === "hours"
                        ? t("dispute.respondInHours", { n: left.n })
                        : t("dispute.respondInMinutes", { n: left.n })}
                  </Text>
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
  row: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
    ...shadow.sm,
  },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  reason: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink, flexShrink: 1 },
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  chipOpen: { backgroundColor: "#fdecec", color: colors.danger },
  chipClosed: { backgroundColor: colors.surface2, color: colors.muted },
  meta: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: space(1) },
  clock: { fontSize: font.tiny, fontFamily: family.bodySemi, color: colors.terracotta, marginTop: space(1.5) },
});
