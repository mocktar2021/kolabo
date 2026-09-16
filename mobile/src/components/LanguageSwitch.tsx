import { useCallback } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { setStoredLanguage, type AppLanguage } from "../lib/language";
/* FOR ITS SIDE EFFECT. languageStrings.ts registers the lang.* keys at
   runtime; without this import the two accessibility labels below would be
   announced as their raw key names. This module is the only consumer of that
   bundle, so the import lives here rather than in each of the four screens
   that draw one of these controls. */
import "../lib/languageStrings";
import { Card, ChoiceGroup, Hint, SectionTitle } from "./ui";
import { colors, family, font, radius, space } from "../theme";

/* THE LANGUAGE CONTROL, IN ONE PLACE, IN TWO SHAPES.

   IT USED TO BE WRITTEN INLINE IN screens/AccountScreen.tsx and nowhere else,
   which meant it could only be reached by somebody who already had an account
   and had already signed in. That is the wrong half of the audience: four of
   the five launch markets are francophone and one is not, the app defaults to
   French for a device that is set to neither, and a Ghanaian opening it for
   the first time met a French carousel with no way out of it before
   registering. Lifting the control out of that screen is what lets the same
   implementation stand on the signed out screens as well.

   TWO SHAPES BECAUSE TWO PLACES ASK FOR DIFFERENT THINGS, and one shared
   choice underneath, so they cannot drift:

     LanguageCard is the account screen's, unchanged: a titled card with an
     explanatory line and the two languages written out in full. It is a
     settings row, it sits among other settings rows, and it is read rather
     than glanced at.

     LanguageSwitch is the auth screens': a compact FR | EN pill. A titled
     card on a login screen would be a second thing to read on a screen whose
     whole job is one form, and the landing carousel has no card anywhere on
     it to put one in.

   THE COMPACT SHAPE IS WEB'S, DELIBERATELY. web/src/components/Layout.tsx
   draws .lang-switch as exactly this: two buttons in a hairline pill, the
   current one filled indigo, the other muted on white. The two clients must
   not put controls that behave differently in front of the same person for
   the same act, and web's is the one a signed out visitor already meets, so
   the phone follows it rather than inventing a third form.

   THE LABELS ARE ENDONYMS AND ARE NOT TRANSLATED. FR is FR and EN is EN in
   both languages, and "Français" reads as itself to an English speaker, which
   is the point: somebody who cannot read the current language has to be able
   to find their own. What IS translated is what a screen reader announces,
   because "FR" spoken aloud is two letters. See lib/languageStrings.ts. */

/* The choice itself, made once. Changing the language in memory is what the
   reader sees; writing it to the keystore is what makes the choice survive
   the next cold start, and App.tsx reapplies it after mount.

   NOTHING HERE IS GATED ON BEING SIGNED IN, which is what makes this usable
   from the auth stack at all: lib/language.ts talks to expo-secure-store and
   nothing else, the write swallows its own failures, and App.tsx's effect
   runs before any auth state is known. A signed out choice persists exactly
   as a signed in one does. */
function useLanguageChoice() {
  const { i18n } = useTranslation();
  /* Anything that is not English is French, which is the same reading
     src/i18n.ts pickLanguage() applies to the device locale and the same one
     the account card has always applied to i18n.language. It also keeps a
     regional tag such as "fr-BJ" on the French button rather than on
     neither. */
  const current: AppLanguage = i18n.language === "en" ? "en" : "fr";
  const choose = useCallback(
    (lang: AppLanguage) => {
      if (lang === current) return;
      void i18n.changeLanguage(lang);
      void setStoredLanguage(lang);
    },
    [i18n, current]
  );
  return { current, choose };
}

/* The two languages, named by themselves, in the order the account card has
   always listed them: French first, because it is the default and the
   majority of the pilot. */
const OPTIONS: { value: AppLanguage; short: string; endonym: string }[] = [
  { value: "fr", short: "FR", endonym: "Français" },
  { value: "en", short: "EN", endonym: "English" },
];

/* The compact pill, for the signed out screens. */
export function LanguageSwitch() {
  const { t } = useTranslation();
  const { current, choose } = useLanguageChoice();
  return (
    <View style={styles.pill} accessibilityRole="radiogroup" accessibilityLabel={t("lang.a11yGroup")}>
      {OPTIONS.map((option) => {
        const selected = option.value === current;
        return (
          <Pressable
            key={option.value}
            onPress={() => choose(option.value)}
            /* The pill is deliberately small, so the tap target is grown
               rather than the drawing: 40 dp of button plus this reaches the
               44 dp both platforms ask for without turning a quiet control
               into a block. */
            hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={t("lang.a11ySwitchTo", { lang: option.endonym })}
            style={[styles.segment, selected && styles.segmentSelected]}
          >
            <Text style={[styles.segmentText, selected && styles.segmentTextSelected]}>
              {option.short}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/* The account screen's card, moved here verbatim so there is one
   implementation of the choice and not two. Every element of it is the one
   that was written inline in AccountScreen: the same Card, the same
   acct.langTitle and acct.langHint, the same ChoiceGroup with the same two
   options in the same order, and the same spacer between the hint and the
   options. The screen keeps rendering it in the same slot, so nothing about
   that screen moves. */
export function LanguageCard() {
  const { t } = useTranslation();
  const { current, choose } = useLanguageChoice();
  return (
    <Card>
      <SectionTitle>{t("acct.langTitle")}</SectionTitle>
      <Hint>{t("acct.langHint")}</Hint>
      <View style={{ height: space(3) }} />
      <ChoiceGroup
        options={OPTIONS.map((option) => ({ value: option.value, label: option.endonym }))}
        value={current}
        onChange={(value) => choose(value as AppLanguage)}
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  /* web .lang-switch: an inline hairline pill that never stretches. alignSelf
     keeps it that width inside a full width column, which is what a bare View
     in this app would otherwise become. */
  pill: {
    flexDirection: "row",
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.pill,
    backgroundColor: colors.white,
    overflow: "hidden",
  },
  segment: {
    minHeight: 40,
    minWidth: 52,
    paddingHorizontal: space(3),
    alignItems: "center",
    justifyContent: "center",
  },
  /* web .lang-switch button.active: filled indigo, white text. */
  segmentSelected: { backgroundColor: colors.indigo },
  segmentText: { fontFamily: family.bodySemi, fontSize: font.small, color: colors.muted },
  segmentTextSelected: { color: colors.white },
});
