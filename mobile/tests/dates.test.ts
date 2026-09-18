/* The day arithmetic behind the calendar picker (KOL-111).

   Two of these describes are regression guards rather than new coverage.
   toIsoDay was rewritten to call partsFromDisplay instead of carrying its own
   regex, and it is the one function here with callers that predate the
   picker: the creator profile, the campaign deadline on three screens, and
   the board filter all convert through it. So its old behaviour is pinned
   case by case, including the cases it refuses.

   The other guard is maxBirthDate, which decides which squares the picker
   greys out. It mirrors a rule the backend owns (profiles
   service._require_adult), and the only way to check the 29 February edge of
   it is to inject the day, which is why the function takes one.

   This file has to live under mobile/tests/: vitest.config.ts collects
   tests/**\/*.test.ts and nothing else, so the same file under src/ would run
   never and pass always. */
import { describe, expect, it } from "vitest";
import {
  displayFromParts,
  fromIsoDay,
  maxBirthDate,
  monthMatrix,
  monthNames,
  partsFromDisplay,
  toIsoDay,
  weekdayInitials,
} from "../src/lib/dates";

describe("monthMatrix", () => {
  /* Always six rows of seven, whatever the month, because a grid that
     changes height makes the sheet jump under the thumb. */
  it("is six rows of seven for a month that starts on a Sunday", () => {
    /* 1 June 2025 was a Sunday, which is the worst case for a Monday-first
       grid: the whole first week is padding but one cell. */
    const grid = monthMatrix(2025, 6);
    expect(grid).toHaveLength(6);
    for (const row of grid) expect(row).toHaveLength(7);
    expect(grid[0]).toEqual([null, null, null, null, null, null, 1]);
    expect(grid[1]).toEqual([2, 3, 4, 5, 6, 7, 8]);
  });

  it("is six rows of seven for a leap February", () => {
    /* 1 February 2024 was a Thursday, and 2024 is a leap year, so the grid
       has to carry a 29 that 2023 does not. */
    const grid = monthMatrix(2024, 2);
    expect(grid).toHaveLength(6);
    for (const row of grid) expect(row).toHaveLength(7);
    expect(grid[0]).toEqual([null, null, null, 1, 2, 3, 4]);
    const days = grid.flat().filter((d) => d !== null);
    expect(days).toEqual(Array.from({ length: 29 }, (_, i) => i + 1));
  });

  it("drops the 29th in a common February", () => {
    const days = monthMatrix(2023, 2).flat().filter((d) => d !== null);
    expect(days).toHaveLength(28);
    expect(days[27]).toBe(28);
  });

  it("pads the tail as well as the head", () => {
    /* A 31 day month starting on a Monday fills 31 of 42 cells, so the last
       eleven must be null rather than missing. */
    const grid = monthMatrix(2025, 12);
    expect(grid.flat()).toHaveLength(42);
    expect(grid[5][6]).toBeNull();
  });
});

describe("partsFromDisplay and displayFromParts", () => {
  it("round trips a day", () => {
    const parts = partsFromDisplay("20/04/1998");
    expect(parts).toEqual({ day: 20, month: 4, year: 1998 });
    expect(displayFromParts(20, 4, 1998)).toBe("20/04/1998");
    expect(displayFromParts(parts!.day, parts!.month, parts!.year)).toBe("20/04/1998");
  });

  it("round trips a single digit day and month, padded", () => {
    expect(displayFromParts(1, 1, 2000)).toBe("01/01/2000");
    expect(partsFromDisplay(displayFromParts(1, 1, 2000))).toEqual({ day: 1, month: 1, year: 2000 });
  });

  it("writes only the form toIsoDay accepts", () => {
    /* The reason displayFromParts pads: a day chosen from the grid has to be
       a day the save edge can convert. */
    expect(toIsoDay(displayFromParts(5, 9, 2008))).toBe("2008-09-05");
  });

  it("rejects a day that does not exist", () => {
    expect(partsFromDisplay("31/02/2020")).toBeNull();
    expect(partsFromDisplay("29/02/2023")).toBeNull();
    expect(partsFromDisplay("31/04/2020")).toBeNull();
  });

  it("rejects an unpadded day", () => {
    expect(partsFromDisplay("1/4/1998")).toBeNull();
  });

  it("accepts a leap day", () => {
    expect(partsFromDisplay("29/02/2024")).toEqual({ day: 29, month: 2, year: 2024 });
  });

  it("agrees with toIsoDay on every case, which is the point of sharing it", () => {
    const cases = [
      "20/04/1998",
      "31/02/2020",
      "1/4/1998",
      "29/02/2024",
      "29/02/2023",
      "00/04/1998",
      "20/13/1998",
      "",
      "not a date",
    ];
    for (const c of cases) {
      expect((partsFromDisplay(c) === null)).toBe(toIsoDay(c) === null);
    }
  });
});

describe("toIsoDay still behaves as it did before the refactor", () => {
  it("converts a valid day", () => {
    expect(toIsoDay("20/04/1998")).toBe("1998-04-20");
    expect(toIsoDay("01/01/2000")).toBe("2000-01-01");
    expect(toIsoDay("29/02/2024")).toBe("2024-02-29");
  });

  it("trims surrounding space", () => {
    expect(toIsoDay(" 20/04/1998 ")).toBe("1998-04-20");
  });

  it("refuses everything it refused before", () => {
    expect(toIsoDay("31/02/2020")).toBeNull();
    expect(toIsoDay("29/02/2023")).toBeNull();
    expect(toIsoDay("1/4/1998")).toBeNull();
    expect(toIsoDay("20/13/1998")).toBeNull();
    expect(toIsoDay("20/00/1998")).toBeNull();
    expect(toIsoDay("00/04/1998")).toBeNull();
    expect(toIsoDay("1998-04-20")).toBeNull();
    expect(toIsoDay("")).toBeNull();
    expect(toIsoDay("not a date")).toBeNull();
  });

  it("still round trips with fromIsoDay", () => {
    expect(fromIsoDay("1998-04-20")).toBe("20/04/1998");
    expect(toIsoDay(fromIsoDay("1998-04-20"))).toBe("1998-04-20");
  });
});

describe("maxBirthDate", () => {
  it("is exactly eighteen years before an ordinary day", () => {
    expect(maxBirthDate(new Date(2026, 8, 18))).toEqual({ day: 18, month: 9, year: 2008 });
    expect(maxBirthDate(new Date(2026, 0, 1))).toEqual({ day: 1, month: 1, year: 2008 });
    expect(maxBirthDate(new Date(2026, 11, 31))).toEqual({ day: 31, month: 12, year: 2008 });
  });

  it("clamps a 29 February back to the 28th", () => {
    /* Eighteen years before a leap day is never itself a leap day, because
       18 is not a multiple of four. Rolling forward to 1 March instead would
       admit somebody born on 1 March, who is still 17 on 29 February, which
       is exactly what the backend rejects. */
    expect(maxBirthDate(new Date(2024, 1, 29))).toEqual({ day: 28, month: 2, year: 2006 });
    expect(maxBirthDate(new Date(2028, 1, 29))).toEqual({ day: 28, month: 2, year: 2010 });
  });

  it("returns a day the save edge accepts", () => {
    const m = maxBirthDate(new Date(2024, 1, 29));
    expect(toIsoDay(displayFromParts(m.day, m.month, m.year))).toBe("2006-02-28");
  });

  it("defaults to today when no day is injected", () => {
    const now = new Date();
    expect(maxBirthDate().year).toBe(now.getFullYear() - 18);
  });
});

describe("month and weekday labels", () => {
  /* The catalogue has no month names in it, on purpose: Intl already knows
     them in every language the app will ever add. These check that the
     locale is actually reaching Intl, not the spelling of any one word. */
  it("gives twelve months, and different ones per language", () => {
    expect(monthNames("en")).toHaveLength(12);
    expect(monthNames("fr")).toHaveLength(12);
    expect(monthNames("fr")[0]).not.toBe(monthNames("en")[0]);
    for (const name of monthNames("fr")) expect(name.length).toBeGreaterThan(0);
  });

  it("gives seven weekdays, Monday first", () => {
    const week = weekdayInitials("en");
    expect(week).toHaveLength(7);
    /* 14 September 2026 was a Monday. Formatted independently here, so this
       is not the helper checking its own arithmetic. */
    const monday = new Intl.DateTimeFormat("en-GB", { weekday: "short" }).format(new Date(2026, 8, 14));
    expect(week[0]).toBe(monday);
    expect(weekdayInitials("fr")).toHaveLength(7);
    expect(weekdayInitials("fr")[0]).not.toBe(week[0]);
  });
});
