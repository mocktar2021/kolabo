/* The non-production banner's one sentence. Owns the env.* group outright, so
   it carries no ordering constraint in main.tsx.

   It names what is NOT real rather than saying "test site", because the two
   things anybody actually needs to know before they act are whether an account
   they create here exists anywhere that matters and whether money would move.
   punctuation.test.ts forbids an em or en dash in either language. */
import i18n from "../i18n";

const fr = {
  banner: "Environnement de développement. Les comptes et les paiements ne sont pas réels."
};

const en = {
  banner: "Development environment. Accounts and payments here are not real."
};

i18n.addResourceBundle("fr", "translation", { env: fr }, true, true);
i18n.addResourceBundle("en", "translation", { env: en }, true, true);
