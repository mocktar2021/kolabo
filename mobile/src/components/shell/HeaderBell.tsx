import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { UnreadCount } from "../../lib/notifications";
import { colors, family, font } from "../../theme";

/* The notifications bell, in the header of every tab — the mobile stand-in
   for the web nav's NotificationsBell. The count comes from its own endpoint
   (the list is capped, the badge must not be) and refreshes whenever the tab
   under it regains focus, so answering something clears it without a
   restart. A failed fetch keeps the last number: a badge is not worth an
   error state.

   `nav` is the navigation object the header options callback receives —
   headers render outside a screen, so the usual hooks are not available
   here and the subscription is wired by hand. */
export function HeaderBell({ nav }: {
  nav: {
    navigate: (name: "Notifications") => void;
    addListener: (type: "focus", cb: () => void) => () => void;
  };
}) {
  const { token } = useAuth();
  const [unread, setUnread] = useState(0);

  const load = useCallback(() => {
    if (!token) return;
    api<UnreadCount>("/notifications/unread-count", { token })
      .then((r) => setUnread(r.unread))
      .catch(() => undefined);
  }, [token]);

  useEffect(() => nav.addListener("focus", load), [nav, load]);
  useEffect(load, [load]);

  return (
    <Pressable onPress={() => nav.navigate("Notifications")} style={styles.wrap} hitSlop={8}>
      <Ionicons name="notifications-outline" size={24} color={colors.ink} />
      {unread > 0 ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{unread > 99 ? "99+" : unread}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: 14, paddingVertical: 4 },
  badge: {
    position: "absolute",
    top: 0,
    right: 6,
    minWidth: 17,
    height: 17,
    borderRadius: 9,
    backgroundColor: colors.terracotta,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  badgeText: { color: colors.white, fontSize: font.tiny - 2, fontFamily: family.bodyBold },
});
