import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { getLocales } from "expo-localization";
import { en, fr } from "./strings";
import { error_en, error_fr } from "./lib/errorMessages";

/* Pick the app language from the device, constrained to what we ship. The
   target markets are mostly francophone (Benin, Togo, Cote d'Ivoire, Senegal,
   Cameroon) with anglophone Ghana and Nigeria, so a device set to neither
   falls back to French rather than English — the safer default for the pilot.
   The `apiError` namespace carries the ported refusal sentences so errorText
   can localise a backend code. */
function pickLanguage(): "en" | "fr" {
  const device = getLocales()[0]?.languageCode;
  if (device === "en") return "en";
  return "fr";
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: { ...en, apiError: error_en } },
    fr: { translation: { ...fr, apiError: error_fr } },
  },
  lng: pickLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
