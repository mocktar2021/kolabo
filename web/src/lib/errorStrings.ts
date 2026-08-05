/* Registers the API error sentences as an i18n resource bundle.

   Wiring only — the sentences themselves live in errorMessages.ts, a module
   with no imports so the test that checks them against the backend's codes
   does not have to boot i18next. Exactly the split notificationBodies.ts and
   notificationStrings.ts use.

   Registered under `apiError`, its own namespace rather than an `err*` key
   inside a feature bundle. Error copy has been scattered that way until now —
   account.errPhoneTaken, reset.errTooMany, board.applyConflict — each one
   chosen by a page from an HTTP STATUS CODE, which means a page whose endpoint
   answers three different 400s can localise at most one of them. A code names
   the rule instead of the status, so the copy belongs where any page can reach
   it. The old per-page keys still work and are not touched here; they get
   folded in as their modules are converted. */
import i18n from "../i18n";
import { error_en, error_fr } from "./errorMessages";

i18n.addResourceBundle("fr", "translation", { apiError: error_fr }, true, true);
i18n.addResourceBundle("en", "translation", { apiError: error_en }, true, true);
