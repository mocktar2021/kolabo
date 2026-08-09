import type { ComponentType } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { ActivityIndicator, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { isBusinessLike, useAuth } from "../lib/auth";
import { colors, family } from "../theme";
import { HeaderBell } from "../components/shell/HeaderBell";
import LoginScreen from "../screens/LoginScreen";
import RegisterScreen from "../screens/RegisterScreen";
import VerifyOtpScreen from "../screens/VerifyOtpScreen";
import ForgotPasswordScreen from "../screens/ForgotPasswordScreen";
import DashboardScreen from "../screens/DashboardScreen";
import CreatorProfileScreen from "../screens/CreatorProfileScreen";
import ContractsListScreen from "../screens/ContractsListScreen";
import ContractDetailScreen from "../screens/ContractDetailScreen";
import EarningsScreen from "../screens/EarningsScreen";
import DisputeDetailScreen from "../screens/DisputeDetailScreen";
import BoardScreen from "../screens/BoardScreen";
import BusinessProfileScreen from "../screens/BusinessProfileScreen";
import SpendScreen from "../screens/SpendScreen";
import CampaignsListScreen from "../screens/CampaignsListScreen";
import CampaignNewScreen from "../screens/CampaignNewScreen";
import DiscoverScreen from "../screens/DiscoverScreen";
import CreatorPublicScreen from "../screens/CreatorPublicScreen";
import InvitationsScreen from "../screens/InvitationsScreen";
import CampaignDetailScreen from "../screens/CampaignDetailScreen";
import NotificationsScreen from "../screens/NotificationsScreen";
import MoreScreen from "../screens/MoreScreen";
import type { AppStackParamList, AuthStackParamList } from "./types";

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const AppStack = createNativeStackNavigator<AppStackParamList>();
const Tab = createBottomTabNavigator();

/* Screens are typed with AppScreenProps (native-stack props over the shared
   param list); the ones hosted on a tab receive bottom-tab props instead.
   Everything they actually use — navigate, goBack, addListener("focus") —
   exists identically on both navigators and resolves against the same
   route names, so the difference is nominal, not behavioural. This cast
   states that once, at registration, instead of forking every screen's
   props type by where it happens to be mounted. */
const asTab = (c: unknown) => c as ComponentType;

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Register" component={RegisterScreen} />
      <AuthStack.Screen name="VerifyOtp" component={VerifyOtpScreen} />
      <AuthStack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />
    </AuthStack.Navigator>
  );
}

/* The daily loop lives on the tab bar; everything else stacks above it.

   ROLE-AWARE, mirroring the web nav exactly: a creator's daily surfaces are
   the board, their invitations and their contracts; a brand's are discovery,
   its campaigns and the same contracts. The occasional destinations (profile,
   money, notifications, logout) sit behind More — the same one-tap-deep
   placement the web gives its account menu.

   THE TAB SCREENS KEEP THEIR OLD ROUTE NAMES ("Contracts", "Board"…), which
   is what lets every existing navigate("Contracts") call — and the
   notification router's targets — keep working unchanged: React Navigation
   resolves a name across nested navigators.

   THE BELL RIDES EVERY TAB HEADER, with its unread badge — the web nav's
   NotificationsBell, in the place a phone reader expects it. */
function TabNavigator() {
  const { t } = useTranslation();
  const { role } = useAuth();
  const brand = isBusinessLike(role);

  return (
    <Tab.Navigator
      screenOptions={({ navigation }) => ({
        headerShown: true,
        headerTitleStyle: { fontFamily: family.displaySemi, fontSize: 17, color: colors.ink },
        headerStyle: { backgroundColor: colors.white },
        headerShadowVisible: false,
        headerRight: () => <HeaderBell nav={navigation} />,
        tabBarActiveTintColor: colors.indigo,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontFamily: family.bodySemi, fontSize: 11 },
        tabBarStyle: { backgroundColor: colors.white, borderTopColor: colors.line },
      })}
    >
      <Tab.Screen
        name="Dashboard"
        component={asTab(DashboardScreen)}
        options={{
          title: t("tab.home"),
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} />,
        }}
      />
      {brand ? (
        <Tab.Screen
          name="Discover"
          component={asTab(DiscoverScreen)}
          options={{
            title: t("tab.discover"),
            tabBarIcon: ({ color, size }) => <Ionicons name="search-outline" size={size} color={color} />,
          }}
        />
      ) : (
        <Tab.Screen
          name="Board"
          component={asTab(BoardScreen)}
          options={{
            title: t("tab.board"),
            tabBarIcon: ({ color, size }) => <Ionicons name="briefcase-outline" size={size} color={color} />,
          }}
        />
      )}
      {brand ? (
        <Tab.Screen
          name="Campaigns"
          component={asTab(CampaignsListScreen)}
          options={{
            title: t("tab.campaigns"),
            tabBarIcon: ({ color, size }) => <Ionicons name="megaphone-outline" size={size} color={color} />,
          }}
        />
      ) : (
        <Tab.Screen
          name="Invitations"
          component={asTab(InvitationsScreen)}
          options={{
            title: t("tab.invitations"),
            tabBarIcon: ({ color, size }) => <Ionicons name="mail-outline" size={size} color={color} />,
          }}
        />
      )}
      <Tab.Screen
        name="Contracts"
        component={asTab(ContractsListScreen)}
        options={{
          title: t("tab.contracts"),
          tabBarIcon: ({ color, size }) => <Ionicons name="document-text-outline" size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="More"
        component={asTab(MoreScreen)}
        options={{
          title: t("tab.more"),
          tabBarIcon: ({ color, size }) => <Ionicons name="menu-outline" size={size} color={color} />,
        }}
      />
    </Tab.Navigator>
  );
}

/* Detail screens stack above the tabs with native headers — the platform's
   own back affordance, replacing the hand-rolled "Back" ghost button every
   screen used to carry. */
function AppNavigator() {
  const { t } = useTranslation();
  return (
    <AppStack.Navigator
      screenOptions={{
        headerShown: true,
        headerTitleStyle: { fontFamily: family.displaySemi, fontSize: 17, color: colors.ink },
        headerStyle: { backgroundColor: colors.white },
        headerShadowVisible: false,
        headerTintColor: colors.indigo,
        headerBackTitleVisible: false,
      }}
    >
      <AppStack.Screen name="Tabs" component={TabNavigator} options={{ headerShown: false }} />
      <AppStack.Screen name="CreatorProfile" component={CreatorProfileScreen} options={{ title: t("profile.title") }} />
      <AppStack.Screen name="BusinessProfile" component={BusinessProfileScreen} options={{ title: t("biz.title") }} />
      <AppStack.Screen name="ContractDetail" component={ContractDetailScreen} options={{ title: t("contract.title") }} />
      <AppStack.Screen name="CampaignDetail" component={CampaignDetailScreen} options={{ title: "" }} />
      <AppStack.Screen name="CampaignNew" component={CampaignNewScreen} options={{ title: t("campaign.title") }} />
      <AppStack.Screen name="CreatorPublic" component={CreatorPublicScreen} options={{ title: "" }} />
      <AppStack.Screen name="DisputeDetail" component={DisputeDetailScreen} options={{ title: t("dispute.formTitle") }} />
      <AppStack.Screen name="Earnings" component={EarningsScreen} options={{ title: t("earn.title") }} />
      <AppStack.Screen name="Spend" component={SpendScreen} options={{ title: t("spend.title") }} />
      <AppStack.Screen name="Notifications" component={NotificationsScreen} options={{ title: t("notif.title") }} />
    </AppStack.Navigator>
  );
}

/* Which tree renders is a function of auth state, not a navigation action:
   logging in flips `isAuthenticated` and the whole stack swaps, so screens
   never navigate to "the app" by name — the React Navigation pattern for auth
   flows, and what keeps a signed-out user from ever holding a back-stack into
   signed-in screens. */
export default function RootNavigator() {
  const { loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <ActivityIndicator color={colors.indigo} size="large" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <AppNavigator /> : <AuthNavigator />}
    </NavigationContainer>
  );
}
