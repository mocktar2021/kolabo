import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { isBusinessLike, useAuth } from "../lib/auth";
import {
  PAGE_SIZE,
  notificationBody,
  relativeParts,
  targetFor,
  type AppNotification,
  type MarkAllRead,
  type NavTarget,
} from "../lib/notifications";
import { Banner, GhostButton, Hint, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* The whole history, newest first, one server page at a time. The paging is
   offset paging and it is safe: the server sorts on created_at AND id, so two
   notifications raised in the same call cannot make a paged read show a row
   twice and skip another.

   A click marks the row read (optimistically — a failed mark costs a badge
   count, not data) and opens the item it is about when this app has a screen
   for it: the contract, the dispute, the campaign, the invitations list.
   Rows without a mobile destination just mark themselves read. */
export default function NotificationsScreen({ navigation }: AppScreenProps<"Notifications">) {
  const { t } = useTranslation();
  const { token, role } = useAuth();
  const isBrand = isBusinessLike(role);

  const [rows, setRows] = useState<AppNotification[] | null>(null);
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      // Trailing slash on purpose: the list route is @router.get("/") under
      // the /notifications prefix.
      setRows(
        await api<AppNotification[]>(
          `/notifications/?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`,
          { token }
        )
      );
      setError(null);
    } catch {
      setError(t("notif.loadFailed"));
    }
  }, [token, page, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function go(target: NavTarget) {
    switch (target.name) {
      case "ContractDetail":
        navigation.navigate("ContractDetail", { id: target.id });
        return;
      case "CampaignDetail":
        navigation.navigate("CampaignDetail", { id: target.id });
        return;
      case "DisputeDetail":
        navigation.navigate("DisputeDetail", { id: target.id });
        return;
      case "Contracts":
        navigation.navigate("Contracts");
        return;
      case "Campaigns":
        navigation.navigate("Campaigns");
        return;
      case "Invitations":
        navigation.navigate("Invitations");
        return;
      case "Earnings":
        navigation.navigate("Earnings");
        return;
      case "Spend":
        navigation.navigate("Spend");
        return;
    }
  }

  function openRow(row: AppNotification) {
    if (!row.is_read) {
      setRows((prev) =>
        prev ? prev.map((r) => (r.id === row.id ? { ...r, is_read: true } : r)) : prev
      );
      api(`/notifications/${row.id}/read`, { method: "POST", token }).catch(() => undefined);
    }
    const target = targetFor(row, isBrand);
    if (target) go(target);
  }

  function markAll() {
    setRows((prev) => (prev ? prev.map((r) => ({ ...r, is_read: true })) : prev));
    api<MarkAllRead>("/notifications/read-all", { method: "POST", token }).catch(() => undefined);
  }

  const loading = rows === null;
  /* The API returns a page and no total, so "is there a next page" can only
     be answered by whether this one came back full. */
  const hasMore = !loading && rows.length === PAGE_SIZE;
  const unreadOnPage = !loading && rows.some((r) => !r.is_read);

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>
      <Title>{t("notif.title")}</Title>
      <Subtitle>{t("notif.sub")}</Subtitle>
      <Hint>{t("notif.routeNote")}</Hint>

      <View style={{ marginTop: space(2), marginBottom: space(3) }}>
        <GhostButton title={t("notif.markAll")} onPress={markAll} disabled={!unreadOnPage} />
      </View>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {loading ? null : rows.length === 0 ? (
        <>
          <Text style={{ color: colors.ink, fontSize: font.body }}>
            {page === 0 ? t("notif.empty") : t("notif.pageEnd")}
          </Text>
          {page === 0 ? <Hint>{t("notif.emptyHint")}</Hint> : null}
        </>
      ) : (
        <View style={{ gap: space(2) }}>
          {rows.map((row) => {
            const when = relativeParts(row.created_at);
            return (
              <Pressable
                key={row.id}
                onPress={() => openRow(row)}
                style={({ pressed }) => [
                  styles.row,
                  !row.is_read && styles.rowUnread,
                  pressed && { backgroundColor: colors.surface },
                ]}
              >
                <Text style={[styles.body, !row.is_read && { fontWeight: "600" }]}>
                  {notificationBody(row, t)}
                </Text>
                <View style={styles.metaRow}>
                  <Text style={styles.when}>{t(when.key, { n: when.n })}</Text>
                  {!row.is_read ? <Text style={styles.unread}>{t("notif.unreadMark")}</Text> : null}
                </View>
              </Pressable>
            );
          })}
        </View>
      )}

      {!loading ? (
        <View style={{ flexDirection: "row", gap: space(2), marginTop: space(4) }}>
          {page > 0 ? (
            <View style={{ flex: 1 }}>
              <GhostButton title={t("notif.newer")} onPress={() => setPage((p) => p - 1)} />
            </View>
          ) : null}
          {hasMore ? (
            <View style={{ flex: 1 }}>
              <GhostButton title={t("notif.older")} onPress={() => setPage((p) => p + 1)} />
            </View>
          ) : null}
        </View>
      ) : null}
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
  },
  rowUnread: { backgroundColor: colors.surface2, borderColor: colors.teal },
  body: { fontSize: font.small, color: colors.ink },
  metaRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: space(1.5) },
  when: { fontSize: font.tiny, color: colors.muted },
  unread: { fontSize: font.tiny, fontWeight: "700", color: colors.teal600 },
});
