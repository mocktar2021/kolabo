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
import { useEffect } from "react";
import i18n from "./src/i18n";
import { AuthProvider } from "./src/lib/auth";
import { getStoredLanguage } from "./src/lib/language";
import RootNavigator from "./src/navigation/RootNavigator";

export default function App() {
  /* The device language is the default (i18n.ts); an explicit in-app choice
     (Account → Language) is stored in the keystore and beats it. Applied
     after mount because SecureStore is async and i18n's init is not — the
     first frame may render in the device language for the rare user who
     overrode it, which is cheaper than gating boot on a keystore read. */
  useEffect(() => {
    void getStoredLanguage().then((lang) => {
      if (lang && lang !== i18n.language) void i18n.changeLanguage(lang);
    });
  }, []);
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
