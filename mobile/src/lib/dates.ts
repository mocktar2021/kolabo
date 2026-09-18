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
export function dayFirstLocale(locale: string): string {
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
  const p = partsFromDisplay(display);
  if (!p) return null;
  return `${pad(p.year, 4)}-${pad(p.month, 2)}-${pad(p.day, 2)}`;
}

/* Zero padding, written once because both directions of DD/MM/YYYY need it.
   A picker that padded differently from the parser would hand the save edge
   days it then refused, which is the class of bug a picker exists to end. */
function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

/* How many days a month has. Day 0 of the NEXT month is the last day of this
   one, which is the trick toIsoDay has always used; it lives here now so the
   calendar grid and the validator can never disagree about whether a given
   February has 29 days. */
function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/* The parser behind toIsoDay, exposed so the picker can read an existing
   value back into a day it can highlight. Same regex, same calendar check,
   ONE implementation: that is the point. Null for anything that is not a real
   day, which includes "31/02/2020" and, because the format is strict about
   width, "1/4/1998". */
export function partsFromDisplay(
  display: string
): { day: number; month: number; year: number } | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(display.trim());
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  const day = Number(dd);
  const month = Number(mm);
  const year = Number(yyyy);
  if (month < 1 || month > 12 || day < 1) return null;
  if (day > daysInMonth(year, month)) return null;
  return { day, month, year };
}

/* The other direction: what the picker writes back into the field. Padded on
   purpose, because the padded form is the only one toIsoDay accepts, so a day
   chosen from the grid is always a day that saves. */
export function displayFromParts(day: number, month: number, year: number): string {
  return `${pad(day, 2)}/${pad(month, 2)}/${pad(year, 4)}`;
}

/* One month as a grid, for the calendar to lay out row by row.

   MONDAY FIRST, for the same reason dayFirstLocale pins the date order: every
   market this ships in writes its week starting Monday, and a Sunday column
   in the wrong place is misread rather than noticed.

   ALWAYS SIX ROWS, even for a month five would hold, because a grid that
   changes height makes the sheet jump as you page through it, and a target
   that moves under the thumb is how somebody taps the wrong day. Cells
   outside the month are null so the caller renders a gap, not a number from
   a neighbouring month that would be tappable by mistake. */
export function monthMatrix(year: number, month: number): (number | null)[][] {
  /* getDay counts from Sunday, so rotate it: Sunday becomes the last column. */
  const lead = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const cells: (number | null)[] = [];
  for (let i = 0; i < lead; i += 1) cells.push(null);
  for (let d = 1; d <= daysInMonth(year, month); d += 1) cells.push(d);
  while (cells.length < 42) cells.push(null);
  const rows: (number | null)[][] = [];
  for (let r = 0; r < 6; r += 1) rows.push(cells.slice(r * 7, r * 7 + 7));
  return rows;
}

/* Month names from Intl rather than from the catalogue. Twelve months and
   seven weekdays in two languages is nineteen keys to write, review and keep
   in step for words the platform already knows in every language it has; and
   the day a third language lands, these two functions need no edit at all. */
export function monthNames(locale: string): string[] {
  const fmt = new Intl.DateTimeFormat(dayFirstLocale(locale), { month: "long" });
  /* Any ordinary year does; the day of the month cannot change a month name. */
  return Array.from({ length: 12 }, (_, i) => fmt.format(new Date(2021, i, 1)));
}

/* Seven short weekday labels in monthMatrix's column order. 1 January 2024
   was a Monday, so walking a week from there gives Monday first without
   hard-coding a single name. */
export function weekdayInitials(locale: string): string[] {
  const fmt = new Intl.DateTimeFormat(dayFirstLocale(locale), { weekday: "short" });
  return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2024, 0, 1 + i)));
}

/* The latest birth date that is already 18, so the picker can grey out a
   younger day instead of letting somebody choose one and learn about it after
   a round trip. The backend stays the authority (profiles
   service._require_adult); this mirrors its rule, including that a person is
   18 ON their birthday and not the day after.

   A 29 February today has no eighteen-years-ago twin, so the day clamps back
   to the 28th rather than rolling forward into March: born on 1 March you are
   still 17 on 29 February, and rolling forward would let that person through.
   `today` is injectable because a boundary nobody can test is a boundary
   nobody has checked. */
export function maxBirthDate(today: Date = new Date()): { day: number; month: number; year: number } {
  const year = today.getFullYear() - 18;
  const month = today.getMonth() + 1;
  return { day: Math.min(today.getDate(), daysInMonth(year, month)), month, year };
}
