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

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

/* Every market this app ships in — francophone and anglophone alike — writes
   dates day-first. A bare "en" would fall back to the US month-first form, so
   the locale is pinned to a day-first variant per language. */
function dayFirstLocale(locale: string): string {
  return locale.startsWith("fr") ? "fr-FR" : "en-GB";
}

export function formatDate(s: string | null | undefined, locale: string): string {
  if (!s) return "";
  /* A date-only string ("1998-04-20", a deadline or birthday) names a DAY,
     not an instant: routing it through Date would glue on a midnight-UTC
     time and let a phone west of Greenwich display the previous day. */
  if (ISO_DAY_RE.test(s)) return fromIsoDay(s);
  const d = parseApiDate(s);
  return d ? d.toLocaleDateString(dayFirstLocale(locale)) : "";
}

/* The two faces of a date-only field: the API speaks ISO "1998-04-20", people
   here write "20/04/1998". Conversion happens at the screen edge — state holds
   what the person typed, the wire always carries ISO. */
export function fromIsoDay(iso: string | null | undefined): string {
  if (!iso || !ISO_DAY_RE.test(iso)) return iso ?? "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/* DD/MM/YYYY → ISO, or null if it isn't a real calendar day ("31/02/2020"
   fails; so does anything not in the format). Callers treat null as a
   validation error, mirroring the web where <input type="date"> makes bad
   days impossible to type. */
export function toIsoDay(display: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(display.trim());
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  const day = Number(dd);
  const month = Number(mm);
  const year = Number(yyyy);
  if (month < 1 || month > 12 || day < 1) return null;
  const daysInMonth = new Date(year, month, 0).getDate();
  if (day > daysInMonth) return null;
  return `${yyyy}-${mm}-${dd}`;
}
