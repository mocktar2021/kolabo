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
