/* Options for building a campaign. The flat PLATFORMS and DELIVERABLE_TYPES
   lists that used to live here are gone: they let a form pair a deliverable
   with a platform the backend rejects with a 400. Platform and deliverable
   choices now come from platforms.ts (PLATFORM_DELIVERABLES mirrors the
   backend catalog). Currencies stay: the common set for the pilot markets. */
export const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];

/* Mirrors MAX_DESCRIPTION_LENGTH in backend/app/modules/campaigns/schemas.py.
   Longer than a note because the description IS the document: the brand
   explaining context, tone and what it is trying to say. The cap is hit as a
   full textarea rather than as a 422 after the brief has been written. */
export const MAX_DESCRIPTION_LENGTH = 5000;
