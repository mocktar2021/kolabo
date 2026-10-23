/* Day-first dates for the web, and the reason this file exists at all.

   <input type="date"> WAS THE WRONG CONTROL FOR THIS MARKET. It is a good
   control in most respects: it refuses an impossible day, it hands JavaScript
   a clean "YYYY-MM-DD", and it draws a calendar the browser already knows how
   to draw. What it will not do is show the date the way the people using
   Kolabo write it. Chrome takes the displayed order from the operating
   system's locale and says so in its own documentation, together with the part
   that settles the question: "Web authors have no way to change the date
   format because there currently is no standards to specify the format."
   So a creator in Cotonou on a machine configured for the United States is
   shown 04/20/1998 for a birthday they would write 20/04/1998, and there is no
   attribute, no lang, and no stylesheet that changes it.

   That is not a cosmetic complaint for a birth date. 04/12 and 12/04 are both
   real days, so a field in the wrong order does not look wrong, it looks
   answered, and the wrong answer is the one that gets saved.

   SO THE FIELD BECOMES TEXT AND THIS FILE IS THE CONVERSION. The format is
   fixed at DD/MM/YYYY, which every one of the launch markets writes,
   francophone and anglophone alike, rather than being inherited from a machine
   whose settings say nothing about where its owner lives.

   THESE FUNCTIONS ARE DELIBERATE DUPLICATES of mobile/src/lib/dates.ts, which
   has carried the same four conversions since the app's profile screen stopped
   using a text box. The packages share no module, and the alternative to
   duplicating was leaving the two halves of one product disagreeing about what
   a date looks like, which is what this change is ending.

   WHAT IS NOT HERE: the 18+ rule. The backend enforces it in profiles
   service._require_adult and the refusal already lands in the error banner
   through errorText, so a second copy of somebody's age arithmetic on this
   side would be a second thing to keep true. Mobile applies it to grey out
   squares in a calendar grid; there is no grid here to grey out. */

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

/* Zero padding, written once because both directions need it. A formatter
   that padded differently from the parser would produce days the parser then
   refused. */
function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

/* How many days a month has. Day 0 of the NEXT month is the last day of this
   one, so February knows about leap years without a table. */
function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/* ISO to what a person reads. Anything that is not an ISO day comes back
   untouched, so a field prefilled from an API that has changed its mind about
   the format shows something rather than blanking itself. */
export function fromIsoDay(iso: string | null | undefined): string {
  if (!iso || !ISO_DAY_RE.test(iso)) return iso ?? "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/* DD/MM/YYYY to ISO, or null if it is not a real calendar day. "31/02/2020"
   fails, and so does anything not in the format, including "1/4/1998": the
   width is strict because the field pads as you type, so a short entry means
   an unfinished one rather than a shorthand. */
export function toIsoDay(display: string): string | null {
  const p = partsFromDisplay(display);
  if (!p) return null;
  return `${pad(p.year, 4)}-${pad(p.month, 2)}-${pad(p.day, 2)}`;
}

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

export function displayFromParts(day: number, month: number, year: number): string {
  return `${pad(day, 2)}/${pad(month, 2)}/${pad(year, 4)}`;
}

/* What the field shows while somebody is typing into it.

   THE SLASHES ARE WRITTEN FOR THEM, from the digits they enter, which is the
   part that makes a text box acceptable where a calendar used to be. Typing
   20041998 leaves 20/04/1998 behind, and the only invalid entries still
   reachable are an unfinished one and a day that does not exist.

   Non-digits are dropped rather than rejected, so a pasted "20-04-1998" or
   "20.04.1998" lands correctly instead of being refused for its separators.
   Everything past eight digits is dropped too: there is no year 19980. */
export function formatAsTyped(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}
