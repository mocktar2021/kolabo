/* Datetimes from this API are naive UTC strings ("2026-08-05T09:12:00", no
   suffix). Left to `new Date`, a device in UTC+1 reads them as local and
   invents or destroys an hour — the same trap web/src/lib/orders.parseApiDate
   avoids. Treat a suffix-less string as UTC. */
export function parseApiDate(s: string | null | undefined): Date | null {
  if (!s) return null;
  const hasZone = /[zZ]|[+-]\d\d:?\d\d$/.test(s);
  const d = new Date(hasZone ? s : `${s}Z`);
  return isNaN(d.getTime()) ? null : d;
}

export function formatDate(s: string | null | undefined, locale: string): string {
  const d = parseApiDate(s);
  return d ? d.toLocaleDateString(locale) : "";
}
