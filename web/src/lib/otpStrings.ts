/* What the verification screen says about where the code went.

   IT REPLACES A SENTENCE THAT WAS TRUE ON A LAPTOP AND NOWHERE ELSE.
   auth.otpDevHint in i18n.ts reads "In development the code is written to the
   server logs". That is a note one developer left for another, and production
   has been showing it to every person who signs up. Nobody signing up on
   kolaboafrica.com has server logs. The code is emailed.

   A NEW KEY IN A BUNDLE, which is how copy has arrived in this package ten
   times already: i18n.ts holds the core catalogue, a feature's copy lands in
   its own file beside it, and main.tsx carries the ordering. auth.otpDevHint
   is left behind unused and otpStrings.test.ts fails if any screen renders it
   again; deleting it belongs with the next edit to i18n.ts rather than with a
   rewrite of 600 lines of bilingual copy to remove one line.

   THE SPAM LINE IS NOT PADDING. The code is sent through a transactional
   mailer from a domain whose reputation is two months old, so the first
   message to a Gmail address is the one most likely to be filed as junk, and
   somebody who does not know to look there decides the product is broken on
   the screen before they have seen any of it. The wording is mobile's, which
   has said this since the pilot's first build; one product, one sentence.

   PILOT, NOT DEVELOPMENT, because the sentence has to stay true on the
   production site: email is how the code arrives there, today, for everybody.
   When SMS delivery is live this sentence changes with it. */
import i18n from "../i18n";

export const otp_auth_fr = {
  otpHint:
    "Pendant le pilote, le code est envoyé par e-mail. Regardez dans vos spams s'il n'arrive pas."
};

export const otp_auth_en = {
  otpHint:
    "During the pilot the code is delivered by email. Look in your spam folder if it does not arrive."
};

i18n.addResourceBundle("fr", "translation", { auth: otp_auth_fr }, true, true);
i18n.addResourceBundle("en", "translation", { auth: otp_auth_en }, true, true);
