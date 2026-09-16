import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { isBusinessLike, useAuth } from "../lib/auth";
import { Screen } from "../components/ui";
import { colors, family, font, radius, shadow, space } from "../theme";
/* Side-effect import: registers the pay.* copy on the i18n instance. */
import "../lib/paymentStrings";
import type { AppScreenProps } from "../navigation/types";

type IconName = keyof typeof Ionicons.glyphMap;

/* The destinations that are somebody's occasional business rather than their
   daily loop — the mobile equivalent of the web nav's account menu. The four
   daily surfaces live on the tab bar; everything else is a row here, one tap
   deep, which is exactly where the web puts them (one click, behind the
   account button). Account settings (address, phone, password, language,
   deletion) is the settings-outline row below: that screen landed, and this
   note used to say it was still coming. */
export default function MoreScreen({ navigation }: AppScreenProps<"More">) {
  const { t } = useTranslation();
  const { role, logout } = useAuth();
  const brand = isBusinessLike(role);

  const rows: { icon: IconName; label: string; onPress: () => void; danger?: boolean }[] = [
    brand
      ? { icon: "business-outline", label: t("biz.title"), onPress: () => navigation.navigate("BusinessProfile") }
      : { icon: "person-outline", label: t("profile.title"), onPress: () => navigation.navigate("CreatorProfile") },
    brand
      ? { icon: "wallet-outline", label: t("spend.title"), onPress: () => navigation.navigate("Spend") }
      : { icon: "wallet-outline", label: t("earn.title"), onPress: () => navigation.navigate("Earnings") },
    /* Creator-only rather than a ternary, because a brand has no counterpart
       row here: it is never paid out. Spread away entirely for a brand so the
       list has no gap. Until this row existed the screen was registered in the
       navigator and reachable by nothing. */
    ...(brand
      ? []
      : [
          {
            icon: "card-outline" as IconName,
            label: t("pay.payoutTitle"),
            onPress: () => navigation.navigate("PayoutMethod"),
          },
        ]),
    { icon: "chatbubbles-outline", label: t("msg.title"), onPress: () => navigation.navigate("Messages") },
    { icon: "alert-circle-outline", label: t("dispute.listTitle"), onPress: () => navigation.navigate("Disputes") },
    { icon: "notifications-outline", label: t("notif.title"), onPress: () => navigation.navigate("Notifications") },
    { icon: "settings-outline", label: t("acct.title"), onPress: () => navigation.navigate("Account") },
    { icon: "log-out-outline", label: t("dash.logout"), onPress: () => void logout(), danger: true },
  ];

  return (
    <Screen>
      <View style={{ gap: space(2), marginTop: space(2) }}>
        {rows.map((row) => (
          <Pressable
            key={row.label}
            onPress={row.onPress}
            style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surface }]}
          >
            <Ionicons
              name={row.icon}
              size={22}
              color={row.danger ? colors.danger : colors.indigo}
            />
            <Text style={[styles.label, row.danger && { color: colors.danger }]}>{row.label}</Text>
            {!row.danger ? (
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            ) : null}
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(3),
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: space(4),
    paddingVertical: space(4),
    ...shadow.sm,
  },
  label: { flex: 1, fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
});
