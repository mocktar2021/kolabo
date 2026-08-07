import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { isBusinessLike, useAuth } from "../lib/auth";
import { Card, GhostButton, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* A signed-in home. For a creator it's the way into profile setup; the brand
   experience and the creator tabs (briefs, contracts, deliverables, earnings)
   are later slices. */
export default function DashboardScreen({ navigation }: AppScreenProps<"Dashboard">) {
  const { t } = useTranslation();
  const { role, logout } = useAuth();
  const creator = !isBusinessLike(role);

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
