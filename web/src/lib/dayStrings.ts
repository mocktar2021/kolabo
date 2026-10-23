/* The two sentences a day-first date field needs: the format it wants, and
   what it says when what was typed is not a day.

   ADDED TO THE profile GROUP i18n.ts OWNS, like socialStrings and
   packageStrings before it, so main.tsx imports this file after ./i18n. A
   group of its own would have put the format of the birth date field
   somewhere nobody looking at profile copy would find it.

   THE WORDING IS MOBILE'S, KEY FOR KEY. mobile/src/strings.ts has carried
   profile.birthDateFormat and profile.birthDateBad since the app's profile
   screen started asking for the date as text, and the web asking the same
   question in different words would be two products rather than one. The
   French placeholder is JJ/MM/AAAA because that is how the format is written
   in French: the same format, spelled in the language of the person reading.

   birthDateHint keeps the sentence i18n.ts already has (never shown publicly,
   18 or older) and this bundle does not touch it. The format now lives in the
   placeholder, where it is visible while the field is empty, which is when it
   is needed. */
import i18n from "../i18n";

export const day_profile_fr = {
  birthDateFormat: "JJ/MM/AAAA",
  birthDateBad: "Utilisez le format JJ/MM/AAAA."
};

export const day_profile_en = {
  birthDateFormat: "DD/MM/YYYY",
  birthDateBad: "Use the format DD/MM/YYYY."
};

i18n.addResourceBundle("fr", "translation", { profile: day_profile_fr }, true, true);
i18n.addResourceBundle("en", "translation", { profile: day_profile_en }, true, true);
