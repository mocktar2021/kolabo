import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "../lib/auth";
import { colors } from "../theme";
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
import type { AppStackParamList, AuthStackParamList } from "./types";

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const AppStack = createNativeStackNavigator<AppStackParamList>();

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

function AppNavigator() {
  return (
    <AppStack.Navigator screenOptions={{ headerShown: false }}>
      <AppStack.Screen name="Dashboard" component={DashboardScreen} />
      <AppStack.Screen name="CreatorProfile" component={CreatorProfileScreen} />
      <AppStack.Screen name="Contracts" component={ContractsListScreen} />
      <AppStack.Screen name="ContractDetail" component={ContractDetailScreen} />
      <AppStack.Screen name="Earnings" component={EarningsScreen} />
      <AppStack.Screen name="DisputeDetail" component={DisputeDetailScreen} />
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
        <ActivityIndicator color={colors.teal} size="large" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <AppNavigator /> : <AuthNavigator />}
    </NavigationContainer>
  );
}
