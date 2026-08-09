import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { isBusinessLike, useAuth } from "../lib/auth";
import { Card, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* The Home tab. The daily destinations moved to the tab bar and the
   occasional ones behind More, so this screen stopped being a menu — it
   greets, states the account, and points at the one thing each role should
   do first (the profile that makes them visible, or the company profile
   creators will read). The web Dashboard's action cards, pending-orders
   alert and referral panel land here in the dashboard-parity phase. */
export default function DashboardScreen(_props: AppScreenProps<"Dashboard">) {
  const { t } = useTranslation();
  const { role } = useAuth();
  const creator = !isBusinessLike(role);
  const navigation = _props.navigation;

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
        <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: space(4) }}>
          <Text style={{ color: colors.muted, fontSize: font.small, fontFamily: family.body }}>
            {t("dash.roleLabel")}
          </Text>
          <Text style={{ color: colors.ink, fontSize: font.small, fontFamily: family.bodySemi }}>
            {roleLabel}
          </Text>
        </View>

        {creator ? (
          <PrimaryButton
            title={t("dash.setupProfile")}
            onPress={() => navigation.navigate("CreatorProfile")}
          />
        ) : (
          <PrimaryButton
            title={t("biz.title")}
            onPress={() => navigation.navigate("BusinessProfile")}
          />
        )}
      </Card>
    </Screen>
  );
}
