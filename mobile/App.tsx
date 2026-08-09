import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { I18nextProvider } from "react-i18next";
import { useFonts } from "expo-font";
import { Poppins_600SemiBold, Poppins_700Bold } from "@expo-google-fonts/poppins";
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from "@expo-google-fonts/inter";
import i18n from "./src/i18n";
import { AuthProvider } from "./src/lib/auth";
import RootNavigator from "./src/navigation/RootNavigator";

export default function App() {
  /* The brand faces (web: --font-display Poppins, --font-body Inter),
     bundled locally by the @expo-google-fonts packages — no network fetch.
     Rendering waits for them: they load in milliseconds from disk, and a
     frame of system font that then jumps to Poppins reads as a glitch.
     `error` falls through to rendering anyway, in system font, because a
     font is never worth a hang. */
  const [fontsLoaded, fontError] = useFonts({
    Poppins_600SemiBold,
    Poppins_700Bold,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
  });
  if (!fontsLoaded && !fontError) return null;

  return (
    <SafeAreaProvider>
      <I18nextProvider i18n={i18n}>
        <AuthProvider>
          <StatusBar style="dark" />
          <RootNavigator />
        </AuthProvider>
      </I18nextProvider>
    </SafeAreaProvider>
  );
}
