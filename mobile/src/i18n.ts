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
  /* ASKED FOR EXPLICITLY, not merely tolerated. Hermes on Android ships
     without Intl.PluralRules on many devices, so i18next's v4 plural resolver
     cannot initialise and it falls back to this format anyway — while logging
     an ERROR line on every boot. A red line nobody can act on is worse than
     noise during a QA pass: it teaches the reader to ignore red lines.

     Nothing is lost by saying it out loud. This app never uses i18next
     plurals: every count is plain {{n}} interpolation, and no t() call passes
     a `count` option. v3 is in fact the SAFER format for our key names —
     several literal keys end in _other (dispute.reason_other,
     notif.body.dispute_opened_other), which v4 would read as a plural suffix
     and v3 leaves alone.

     The alternative, the intl-pluralrules polyfill, buys a dependency and the
     v4 suffix collision for a feature we do not use. Revisit if a real plural
     ever lands: adopt the polyfill AND rename those keys in the same commit. */
  compatibilityJSON: "v3",
});

export default i18n;
