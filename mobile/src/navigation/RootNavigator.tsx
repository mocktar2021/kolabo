import { useEffect, useState, type ComponentType } from "react";
import { View } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { isBusinessLike, useAuth } from "../lib/auth";
import { colors, family } from "../theme";
import { HeaderBell } from "../components/shell/HeaderBell";
import { HeaderCart } from "../components/shell/HeaderCart";
import { Splash } from "../components/landing";
import { landingSeenCached, loadLandingSeen } from "../lib/onboarding";
import LandingScreen from "../screens/LandingScreen";
import LoginScreen from "../screens/LoginScreen";
import RegisterScreen from "../screens/RegisterScreen";
import VerifyOtpScreen from "../screens/VerifyOtpScreen";
import ForgotPasswordScreen from "../screens/ForgotPasswordScreen";
import DashboardScreen from "../screens/DashboardScreen";
import CreatorProfileScreen from "../screens/CreatorProfileScreen";
import ContractsListScreen from "../screens/ContractsListScreen";
import ContractDetailScreen from "../screens/ContractDetailScreen";
import CheckoutScreen from "../screens/CheckoutScreen";
import PayoutMethodScreen from "../screens/PayoutMethodScreen";
import EarningsScreen from "../screens/EarningsScreen";
import DisputeDetailScreen from "../screens/DisputeDetailScreen";
import BoardScreen from "../screens/BoardScreen";
import BusinessProfileScreen from "../screens/BusinessProfileScreen";
import SpendScreen from "../screens/SpendScreen";
import CampaignsListScreen from "../screens/CampaignsListScreen";
import CampaignNewScreen from "../screens/CampaignNewScreen";
import DiscoverScreen from "../screens/DiscoverScreen";
import CreatorPublicScreen from "../screens/CreatorPublicScreen";
import CartScreen from "../screens/CartScreen";
import InvitationsScreen from "../screens/InvitationsScreen";
import CampaignDetailScreen from "../screens/CampaignDetailScreen";
import NotificationsScreen from "../screens/NotificationsScreen";
import MoreScreen from "../screens/MoreScreen";
import MessagesScreen from "../screens/MessagesScreen";
import MessageThreadScreen from "../screens/MessageThreadScreen";
import DisputesScreen from "../screens/DisputesScreen";
import AccountScreen from "../screens/AccountScreen";
import type { AppStackParamList, AuthStackParamList } from "./types";

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const AppStack = createNativeStackNavigator<AppStackParamList>();
const Tab = createBottomTabNavigator();

/* How long the splash is held AFTER the keystore has answered, on every cold
   start that lands SIGNED OUT — the intro carousel on a fresh install, and the
   Login screen every launch after that.

   IT USED TO COVER ONLY THE FIRST OF THOSE and that was the wrong half. The
   floor was gated on `startAtLanding`, which is true exactly once per handset:
   the moment a reader taps Login or Register, markLandingSeen fires and every
   launch afterwards went to Login with no floor at all. The brand mark got its
   beat on the one launch that already showed three slides of branding, and
   none on the launch that actually repeats — where the keystore answers in a
   few milliseconds and the logo is gone inside two frames. That flicker is
   worse than no splash, which the note here always said; it was just pointing
   at the wrong launch.

   700ms became 1500 for the same reason: the old number was picked to cover a
   gap before a carousel rather than to be a length anybody would look at.

   A SIGNED-IN READER STILL WAITS FOR NONE OF IT. That is why the condition
   below tests `!isAuthenticated` rather than the timer alone — opening an app
   you are already logged into is the launch that happens every day, and a
   second and a half of logo is a tax on the people who use this most. The same
   test keeps a mid-session logout from flashing a splash on the way to Login:
   the timer started at boot, so it is long since expired by then. */
const SPLASH_FLOOR_MS = 1500;

/* Screens are typed with AppScreenProps (native-stack props over the shared
   param list); the ones hosted on a tab receive bottom-tab props instead.
   Everything they actually use — navigate, goBack, addListener("focus") —
   exists identically on both navigators and resolves against the same
   route names, so the difference is nominal, not behavioural. This cast
   states that once, at registration, instead of forking every screen's
   props type by where it happens to be mounted. */
const asTab = (c: unknown) => c as ComponentType;

/* The signed-out tree, rooted on the intro carousel the first time this
   handset opens the app and on Login every time after. Landing stays
   registered either way: keeping the route table the same shape whichever
   branch was taken means nothing else has to know which one it was. */
function AuthNavigator({ startAtLanding }: { startAtLanding: boolean }) {
  return (
    <AuthStack.Navigator
      screenOptions={{ headerShown: false }}
      initialRouteName={startAtLanding ? "Landing" : "Login"}
    >
      <AuthStack.Screen name="Landing" component={LandingScreen} />
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
   NotificationsBell, in the place a phone reader expects it. THE BASKET RIDES
   BESIDE IT FOR A BRAND, and for a brand only: mobile has no route guards, so
   an entry point that must not exist for a creator has to simply not be
   rendered. The API applies the same rule from the other side — checkout
   answers 403 (campaign_author_only) to a creator whatever the client shows. */
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
        headerRight: () => (
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            {brand ? <HeaderCart nav={navigation} /> : null}
            <HeaderBell nav={navigation} />
          </View>
        ),
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
        /* Navigation 7 dropped headerBackTitleVisible; its own typings point to
           "minimal" as the equivalent of the old `false`. */
        headerBackButtonDisplayMode: "minimal",
      }}
    >
      <AppStack.Screen name="Tabs" component={TabNavigator} options={{ headerShown: false }} />
      <AppStack.Screen name="CreatorProfile" component={CreatorProfileScreen} options={{ title: t("profile.title") }} />
      <AppStack.Screen name="BusinessProfile" component={BusinessProfileScreen} options={{ title: t("biz.title") }} />
      <AppStack.Screen name="ContractDetail" component={ContractDetailScreen} options={{ title: t("contract.title") }} />
      {/* The two payment screens. Their titles come from the pay.* bundle,
          which each screen registers as a side effect of its own import — the
          imports above are what put those keys on i18n before this renders. */}
      <AppStack.Screen name="Checkout" component={CheckoutScreen} options={{ title: t("pay.title") }} />
      <AppStack.Screen name="PayoutMethod" component={PayoutMethodScreen} options={{ title: t("pay.payoutTitle") }} />
      <AppStack.Screen name="CampaignDetail" component={CampaignDetailScreen} options={{ title: "" }} />
      <AppStack.Screen name="CampaignNew" component={CampaignNewScreen} options={{ title: t("campaign.title") }} />
      <AppStack.Screen name="CreatorPublic" component={CreatorPublicScreen} options={{ title: "" }} />
      {/* Registered for everybody and reachable only by a brand: the header
          button and the storefront's Add are both behind isBusinessLike, and
          the screen itself says whose the cart is if anyone lands here anyway.
          Its title comes from the cart.* bundle, which CartScreen registers as
          a side effect of its own import — the import above is what puts those
          keys on i18n before this renders, exactly as the payment screens
          do. */}
      <AppStack.Screen name="Cart" component={CartScreen} options={{ title: t("cart.title") }} />
      <AppStack.Screen name="DisputeDetail" component={DisputeDetailScreen} options={{ title: t("dispute.formTitle") }} />
      <AppStack.Screen name="Earnings" component={EarningsScreen} options={{ title: t("earn.title") }} />
      <AppStack.Screen name="Spend" component={SpendScreen} options={{ title: t("spend.title") }} />
      <AppStack.Screen name="Notifications" component={NotificationsScreen} options={{ title: t("notif.title") }} />
      <AppStack.Screen name="Messages" component={MessagesScreen} options={{ title: t("msg.title") }} />
      <AppStack.Screen
        name="MessageThread"
        component={MessageThreadScreen}
        options={({ route }) => ({ title: route.params.name })}
      />
      <AppStack.Screen name="Disputes" component={DisputesScreen} options={{ title: t("dispute.listTitle") }} />
      <AppStack.Screen name="Account" component={AccountScreen} options={{ title: t("acct.title") }} />
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
  /* Has this handset already been through the pre-auth intro? Read once at
     boot from the same keystore the token lives in, then held in a module
     cache so this component can consult it DURING RENDER — a logout later in
     the same session has to land on Login, and it would not if the decision
     were waiting on a fresh asynchronous read while the stack was already
     mounting. See lib/onboarding.ts. */
  const [introRead, setIntroRead] = useState(landingSeenCached() !== null);
  const [floorPassed, setFloorPassed] = useState(false);

  useEffect(() => {
    let active = true;
    void loadLandingSeen().then(() => {
      if (active) setIntroRead(true);
    });
    const id = setTimeout(() => {
      if (active) setFloorPassed(true);
    }, SPLASH_FLOOR_MS);
    return () => {
      active = false;
      clearTimeout(id);
    };
  }, []);

  const restoring = loading || !introRead;
  const startAtLanding = !restoring && !isAuthenticated && landingSeenCached() === false;

  /* The splash stands where a bare ActivityIndicator used to: it covers the
     keystore reads for everybody, and is then held to the floor for anyone
     arriving signed out — whether that is the intro carousel on a fresh
     install or the Login screen on every launch after it.

     `!isAuthenticated` rather than `!floorPassed` alone is what keeps a
     returning signed-in reader out of the wait entirely, and what stops a
     mid-session logout flashing a splash: by then the timer set at boot has
     long since fired. See SPLASH_FLOOR_MS. */
  if (restoring || (!isAuthenticated && !floorPassed)) return <Splash />;

  return (
    <NavigationContainer>
      {isAuthenticated ? <AppNavigator /> : <AuthNavigator startAtLanding={startAtLanding} />}
    </NavigationContainer>
  );
}
