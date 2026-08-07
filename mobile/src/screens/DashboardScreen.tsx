import { useCallback, useEffect, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { isBusinessLike, useAuth } from "../lib/auth";
import type { UnreadCount } from "../lib/notifications";
import { Card, GhostButton, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* A signed-in home, and the app's stand-in for the web's persistent header:
   the notifications entry lives here, badge included, because there is no nav
   bar to hang a bell on. */
export default function DashboardScreen({ navigation }: AppScreenProps<"Dashboard">) {
  const { t } = useTranslation();
  const { role, token, logout } = useAuth();
  const creator = !isBusinessLike(role);

  /* The badge count comes from its own endpoint rather than a list length:
     the list is capped and the badge must not be. Refreshed on focus so
     answering something clears it without a restart; a failed fetch keeps
     the last number rather than erasing it. */
  const [unread, setUnread] = useState(0);
  const loadUnread = useCallback(() => {
    if (!token) return;
    api<UnreadCount>("/notifications/unread-count", { token })
      .then((r) => setUnread(r.unread))
      .catch(() => undefined);
  }, [token]);
  useEffect(() => navigation.addListener("focus", loadUnread), [navigation, loadUnread]);
  useEffect(loadUnread, [loadUnread]);

  const roleLabel =
    role === "business"
      ? t("dash.roleBusiness")
      : role === "agency"
        ? t("dash.roleAgency")
        : t("dash.roleInfluencer");

  return (
    <Screen>
      <Title>{t("dash.title")}</Title>
      <Subtitle>{t("dash.hello")}</Subtitle>
      <Card>
        <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: space(3) }}>
          <Text style={{ color: colors.muted, fontSize: font.small }}>{t("dash.roleLabel")}</Text>
          <Text style={{ color: colors.ink, fontSize: font.small, fontWeight: "600" }}>{roleLabel}</Text>
        </View>

        {creator ? (
          <View style={{ marginBottom: space(3) }}>
            <PrimaryButton title={t("dash.setupProfile")} onPress={() => navigation.navigate("CreatorProfile")} />
          </View>
        ) : (
          <View style={{ marginBottom: space(3) }}>
            <PrimaryButton title={t("biz.title")} onPress={() => navigation.navigate("BusinessProfile")} />
          </View>
        )}

        {creator ? (
          <>
            <View style={{ marginBottom: space(3) }}>
              <GhostButton title={t("board.title")} onPress={() => navigation.navigate("Board")} />
            </View>
            <View style={{ marginBottom: space(3) }}>
              <GhostButton title={t("invitation.title")} onPress={() => navigation.navigate("Invitations")} />
            </View>
          </>
        ) : (
          <>
            <View style={{ marginBottom: space(3) }}>
              <GhostButton title={t("discover.title")} onPress={() => navigation.navigate("Discover")} />
            </View>
            <View style={{ marginBottom: space(3) }}>
              <GhostButton title={t("campaign.listTitle")} onPress={() => navigation.navigate("Campaigns")} />
            </View>
          </>
        )}
        <View style={{ marginBottom: space(3) }}>
          <GhostButton title={t("contract.listTitle")} onPress={() => navigation.navigate("Contracts")} />
        </View>
        <View style={{ marginBottom: space(3) }}>
          <GhostButton
            title={unread > 0 ? t("notif.titleWithCount", { n: unread }) : t("notif.title")}
            onPress={() => navigation.navigate("Notifications")}
          />
        </View>
        {creator ? (
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("earn.title")} onPress={() => navigation.navigate("Earnings")} />
          </View>
        ) : (
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("spend.title")} onPress={() => navigation.navigate("Spend")} />
          </View>
        )}
        <GhostButton title={t("dash.logout")} onPress={() => void logout()} />
      </Card>
    </Screen>
  );
}
