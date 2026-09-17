import i18n from "../i18n";

/* The words around the language control, and only the ones that are never
   drawn.

   THE BUTTONS THEMSELVES CARRY NO KEY. They say FR and EN, and the card on
   the account screen says "Français" and "English": both are endonyms, which
   means they read the same to a French reader and to an English one. A key
   whose two translations were identical would be two places to keep one
   string. What a screen reader announces is a different matter, because "FR"
   spoken aloud is two letters and not a language, so the labels below exist
   for exactly that and are the only strings here.

   REGISTERED AT RUNTIME, the convention lib/landingStrings.ts and
   lib/googleStrings.ts set: src/strings.ts is 60 KB and a two key addition
   lands in it invisibly. The cost is the usual one, that a consumer must
   import this module for its side effect or render raw key names, and it is
   paid in one place: components/LanguageSwitch.tsx is the only file that uses
   these keys and it imports this module itself. No screen has to remember.

   A GROUP OF ITS OWN, `lang`, rather than more keys under `acct`. The control
   is no longer only on the account screen: it is on the landing carousel, the
   login screen and the register screen too, and copy filed under `acct` that
   a signed out visitor reads is copy filed in the wrong place. The card's own
   title and hint stay where they are, under acct.langTitle and acct.langHint
   in strings.ts, because those two sentences really are the account screen's.

   French first, like the other bundles: four of the five launch markets are
   francophone. */

const fr = {
  /* The control as a whole, for a screen reader arriving at it cold. */
  a11yGroup: "Langue",
  /* One button. {{lang}} is the language's own name for itself, so it is
     passed in by the component rather than translated here. */
  a11ySwitchTo: "Passer en {{lang}}",
};

const en = {
  a11yGroup: "Language",
  a11ySwitchTo: "Switch to {{lang}}",
};

i18n.addResourceBundle("fr", "translation", { lang: fr }, true, true);
i18n.addResourceBundle("en", "translation", { lang: en }, true, true);
