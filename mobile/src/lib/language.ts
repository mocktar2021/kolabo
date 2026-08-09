/* The in-app language override, persisted in the device keystore beside the
   auth token. The device language stays the DEFAULT (i18n.ts picks it at
   boot); this is the explicit choice that beats it — a Ghanaian tester with
   an English phone can check French, and a shared handset can be flipped,
   without touching OS settings. Web has the same control in its nav. */
import * as SecureStore from "expo-secure-store";

const KEY = "kolabo.language";

export type AppLanguage = "en" | "fr";

export async function getStoredLanguage(): Promise<AppLanguage | null> {
  try {
    const v = await SecureStore.getItemAsync(KEY);
    return v === "en" || v === "fr" ? v : null;
  } catch {
    return null;
  }
}

export async function setStoredLanguage(lang: AppLanguage): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY, lang);
  } catch {
    // Persistence is a nicety; the in-memory switch already happened.
  }
}
