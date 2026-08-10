/* One way to write money everywhere: "85 000 XOF", not "85000 XOF" — the
   grouping that Earnings always had, now shared so the contract screen (and
   anyone else) can't drift back to raw integers. Hermes ships Intl on both
   platforms in this SDK, so toLocaleString really groups; if a locale ever
   fell back to plain digits the string would still be correct, just plainer. */
export function formatAmount(value: number, currency: string, locale: string): string {
  return `${value.toLocaleString(locale)} ${currency}`;
}
