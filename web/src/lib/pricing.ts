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
