/* Options for building a campaign. The flat PLATFORMS and DELIVERABLE_TYPES
   lists that used to live here are gone: they let a form pair a deliverable
   with a platform the backend rejects with a 400. Platform and deliverable
   choices now come from platforms.ts (PLATFORM_DELIVERABLES mirrors the
   backend catalog).

   CURRENCIES IS THE OPEN MARKETS' CURRENCIES AND NOTHING ELSE, which is XOF
   alone: Benin, Togo, Cote d'Ivoire and Senegal all use it. XAF, GHS and NGN
   were in this list because Cameroon, Ghana and Nigeria were once expected in
   the first wave, and they stayed in it after those three were closed. A
   currency offered in a dropdown is a promise that money can move in it, and
   money cannot move in any of those three: they sit outside the XOF area the
   payment provider's BCEAO licence covers. A brand could price a campaign in
   naira and no creator could ever be paid for it.

   THE LIST IS GUARDED RATHER THAN TRUSTED. currencies.test.ts holds it against
   backend/app/core/country_config.py, so opening Ghana in that file fails this
   package until GHS comes back here. Reopening a market stays a one-line
   change in each of the four places that still keep their own country list;
   what the guard ends is the chance of forgetting this one. */
export const CURRENCIES = ["XOF"];

/* Mirrors MAX_DESCRIPTION_LENGTH in backend/app/modules/campaigns/schemas.py.
   Longer than a note because the description IS the document: the brand
   explaining context, tone and what it is trying to say. The cap is hit as a
   full textarea rather than as a 422 after the brief has been written. */
export const MAX_DESCRIPTION_LENGTH = 5000;
