/* Mirror of backend/app/core/pricing.py. The API rejects package prices
   below these per-currency floors with a 400, so the form enforces them
   first and the server stays the source of truth. */
export const MIN_PACKAGE_PRICE: Record<string, number> = {
  XOF: 5000,
  XAF: 5000,
  GHS: 100,
  NGN: 10000
};

export function minPrice(currency: string): number {
  return MIN_PACKAGE_PRICE[currency] ?? 0;
}

/* Mirror of MIN_LIVE_PACKAGES in backend/app/core/pricing.py: how many active
   packages a creator needs before they are searchable.

   Mirrored rather than fetched because the API never reports the number.
   GET /profiles/{id}/onboarding-status answers with active_package_count and
   the has_pricing verdict it reached — the threshold behind that verdict is
   not in the payload, so a client that wants to SAY the number has to hold
   it. Holding it once, here, is the whole point: the copy interpolates it, so
   the day the storefront rule changes there is one number to change and not
   four sentences in two languages that quietly became false. */
export const MIN_LIVE_PACKAGES = 3;

/* Whether turning this one package off takes the creator out of search.

   True only on the crossing — findable now, not findable after. Already below
   the threshold, the profile is hidden either way, and warning about a
   consequence that has already happened is how a warning gets ignored the one
   time it matters. */
export function deactivationHidesProfile(activePackageCount: number): boolean {
  return activePackageCount >= MIN_LIVE_PACKAGES && activePackageCount - 1 < MIN_LIVE_PACKAGES;
}

/* Mirror of settings.commission_bps (1500 = 15 percent).

   Duplicated rather than fetched because there is no endpoint that reports
   it, and the one screen that needs it — an admin splitting a disputed
   escrow — needs it to PREDICT what the server will do, not to decide it.
   The server still computes the real figure at resolution through
   payments.service.commission_for, and the escrow it writes back carries it.
   If this number ever drifts, the admin sees an estimate that was wrong; the
   money is unaffected. */
export const COMMISSION_BPS = 1500;

/* Integer division in minor units, exactly like commission_for: the rounding
   remainder stays with the creator, which is the side it should stay with. */
export function commissionFor(amount: number): number {
  return Math.floor((amount * COMMISSION_BPS) / 10000);
}
