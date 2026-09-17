/* THE LANGUAGE A VISITOR CHOSE, REMEMBERED.

   WHAT WAS WRONG. The switch in the header called i18n.changeLanguage and
   nothing else, so the choice lived in one JavaScript heap and died with it.
   A visitor who pressed EN read English until they opened a creator profile
   in a new tab, or refreshed, or came back tomorrow, and then read French
   again with no indication that anything had happened. The control looked
   like a setting and behaved like a filter, and the people it fails are
   exactly the ones it exists for: anglophone visitors in Ghana and Nigeria,
   on a site that defaults to French.

   FRENCH STAYS THE DEFAULT WHEN NOTHING IS STORED, and that is a decision
   rather than an accident of the old code. Four of the five launch markets
   (Benin, Togo, Cote d'Ivoire, Cameroon) are francophone. This module is the
   memory of an explicit choice and nothing else.

   THE BROWSER'S OWN LANGUAGE IS NOT CONSULTED, deliberately. i18next has a
   detector for it, it would be a new dependency and a new default, and which
   of Accept-Language, navigator.language and a stored value should win is a
   product decision nobody has made. Adding it quietly inside a persistence
   change would make that decision by accident. Stored, else French.

   A SEPARATE MODULE, NOT A CORNER OF lib/auth.tsx, for one hard reason: this
   is read by src/i18n.ts at init, and i18n.ts is the first import in
   main.tsx. Pulling the auth module into that path would drag React and the
   provider tree in ahead of everything. Nothing here imports anything. */

export type AppLanguage = "en" | "fr";

/* The key sits in the same namespace as kolabo_token and kolabo_role, which
   is what makes "clear the Kolabo keys" a thing somebody can actually do. */
const KEY = "kolabo_language";

/* Named rather than written twice, so the answer to "what do we show somebody
   who has never chosen?" has exactly one place to be changed. */
export const DEFAULT_LANGUAGE: AppLanguage = "fr";

/* THE SAME PATTERN lib/auth.tsx USES, AND FOR THE SAME REASON, which is worth
   stating because the duplication is deliberate. localStorage's getter THROWS
   rather than returning null in Safari private mode and in any browser set to
   block site data. An exception here is not a lost preference: it is thrown
   while i18n.ts is initialising, at the top of main.tsx, before anything has
   rendered, so it would take the whole site down to a white page for the
   readers most likely to be browsing privately.

   The helpers are not imported from lib/auth.tsx because they are private
   there, and exporting them would widen that module's surface for a concern
   that has nothing to do with sessions, and because of the import ordering
   above. Two small functions is the cheaper of the two prices. */
function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* Storage is full, or blocked. The in-memory switch has already happened,
       so this tab is in the language that was asked for; it just will not
       survive a reload. That is a worse afternoon, not a broken page. */
  }
}

/* Null means "never chose", which is not the same as "chose French": the
   caller below turns the first into the default, and a value this app does
   not ship is read as never having chosen at all rather than trusted into
   i18next, which would resolve it against fallbackLng and leave the switch
   highlighting neither button. */
export function getStoredLanguage(): AppLanguage | null {
  const value = readStored(KEY);
  return value === "en" || value === "fr" ? value : null;
}

export function setStoredLanguage(lang: AppLanguage): void {
  writeStored(KEY, lang);
}

/* What src/i18n.ts passes as `lng`. A function rather than a constant because
   a constant would be evaluated at module load in whatever order the bundler
   chose, and this has to read storage at the moment init runs. */
export function initialLanguage(): AppLanguage {
  return getStoredLanguage() ?? DEFAULT_LANGUAGE;
}
