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
