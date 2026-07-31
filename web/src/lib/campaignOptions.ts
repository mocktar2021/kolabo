/* Options for building a campaign. The flat PLATFORMS and DELIVERABLE_TYPES
   lists that used to live here are gone: they let a form pair a deliverable
   with a platform the backend rejects with a 400. Platform and deliverable
   choices now come from platforms.ts (PLATFORM_DELIVERABLES mirrors the
   backend catalog). Currencies stay: the common set for the pilot markets. */
export const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];
