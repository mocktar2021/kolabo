/* Per-currency package price floors, mirrored from web/src/lib/pricing.ts and
   backend/app/core/pricing.py. The API rejects a package below these with a
   400 (price_below_floor); the form enforces them first so the server stays
   the source of truth. */
export const MIN_PACKAGE_PRICE: Record<string, number> = {
  XOF: 5000,
  XAF: 5000,
  GHS: 100,
  NGN: 10000,
};

export function minPrice(currency: string): number {
  return MIN_PACKAGE_PRICE[currency] ?? 0;
}

/* Mirror of MIN_LIVE_PACKAGES in backend/app/core/pricing.py, and of
   web/src/lib/pricing.ts, which carries the same pair for the same reason:
   how many active packages a creator needs before they are searchable.

   Mirrored rather than fetched because the API never reports the number.
   GET /profiles/{id}/onboarding-status answers with active_package_count and
   the has_pricing verdict it reached, not the threshold behind that verdict,
   so a client that wants to SAY the number has to hold it. Held once, here,
   and interpolated into the copy: one number to change the day the storefront
   rule does, instead of four sentences in two languages that quietly became
   false. */
export const MIN_LIVE_PACKAGES = 3;

/* Whether turning this one package off takes the creator out of search.

   True only on the crossing — findable now, not findable after. Already below
   the threshold, the profile is hidden either way, and warning about a
   consequence that has already happened is how a warning gets ignored the one
   time it matters. */
export function deactivationHidesProfile(activePackageCount: number): boolean {
  return activePackageCount >= MIN_LIVE_PACKAGES && activePackageCount - 1 < MIN_LIVE_PACKAGES;
}
