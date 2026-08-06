import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { Banner, Card, GhostButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, space } from "../theme";

/* A placeholder home for a signed-in account: it proves the token round-trips
   and gives the tester somewhere to land and a way back out. The creator tabs
   (profile, briefs, contracts, deliverables, earnings) are the next slice. */
export default function DashboardScreen() {
  const { t } = useTranslation();
  const { role, logout } = useAuth();

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
        <Banner kind="info">{t("dash.comingSoon")}</Banner>
        <GhostButton title={t("dash.logout")} onPress={() => void logout()} />
      </Card>
    </Screen>
  );
}
