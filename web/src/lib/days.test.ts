/* The conversions behind the birth date field.

   WHAT A FAILURE HERE COSTS. This is the only thing standing between what
   somebody typed and what is stored as their date of birth, and the wrong
   answer is not an error page: 04/12 and 12/04 are both real days, so a
   transposition saves a different, perfectly valid birthday and nothing
   anywhere says so. The field that this replaced had the browser guaranteeing
   the day was real; that guarantee now lives in partsFromDisplay, so it is
   tested rather than assumed.

   The same assertions exist on the mobile side of the product, against
   mobile/src/lib/dates.ts. The two files are deliberate duplicates (no shared
   module between the packages) and so are the two suites, for the reason
   punctuation.test.ts gives about itself: a guard only one app runs reads as
   though both are covered. */
import { describe, expect, it } from "vitest";
import {
  displayFromParts,
  formatAsTyped,
  fromIsoDay,
  partsFromDisplay,
  toIsoDay
} from "./days";

describe("fromIsoDay", () => {
  it("writes an ISO day the way the launch markets write it", () => {
    expect(fromIsoDay("1998-04-20")).toBe("20/04/1998");
  });

  it("keeps the leading zeros that make the field a fixed width", () => {
    expect(fromIsoDay("2000-01-02")).toBe("02/01/2000");
  });

  it("returns empty for nothing rather than the word undefined", () => {
    expect(fromIsoDay(null)).toBe("");
    expect(fromIsoDay(undefined)).toBe("");
    expect(fromIsoDay("")).toBe("");
  });

  it("hands back anything that is not an ISO day untouched", () => {
    /* A prefill from an API that changed its mind about the format shows
       something rather than blanking the field silently. */
    expect(fromIsoDay("20/04/1998")).toBe("20/04/1998");
  });
});

describe("toIsoDay", () => {
  it("round trips with fromIsoDay", () => {
    expect(toIsoDay(fromIsoDay("1998-04-20"))).toBe("1998-04-20");
  });

  it("refuses a day that does not exist", () => {
    expect(toIsoDay("31/02/2020")).toBeNull();
    expect(toIsoDay("31/04/2020")).toBeNull();
    expect(toIsoDay("00/04/2020")).toBeNull();
    expect(toIsoDay("20/13/2020")).toBeNull();
    expect(toIsoDay("20/00/2020")).toBeNull();
  });

  it("knows which Februaries have 29 days", () => {
    expect(toIsoDay("29/02/2020")).toBe("2020-02-29");
    expect(toIsoDay("29/02/2021")).toBeNull();
    /* 1900 was not a leap year and 2000 was: the rule is not "every four". */
    expect(toIsoDay("29/02/1900")).toBeNull();
    expect(toIsoDay("29/02/2000")).toBe("2000-02-29");
  });

  it("refuses an unfinished entry rather than guessing at it", () => {
    expect(toIsoDay("")).toBeNull();
    expect(toIsoDay("20")).toBeNull();
    expect(toIsoDay("20/04")).toBeNull();
    expect(toIsoDay("20/04/19")).toBeNull();
    /* Strict widths, because the field pads as it is typed: a short entry
       means an unfinished one, not a shorthand to be interpreted. */
    expect(toIsoDay("1/4/1998")).toBeNull();
  });

  it("ignores surrounding whitespace, which is what a paste brings", () => {
    expect(toIsoDay("  20/04/1998  ")).toBe("1998-04-20");
  });
});

describe("partsFromDisplay and displayFromParts", () => {
  it("read a day apart and put it back together", () => {
    expect(partsFromDisplay("20/04/1998")).toEqual({ day: 20, month: 4, year: 1998 });
    expect(displayFromParts(20, 4, 1998)).toBe("20/04/1998");
  });

  it("pads what it writes, so what it writes is what it accepts", () => {
    const written = displayFromParts(2, 1, 2000);
    expect(written).toBe("02/01/2000");
    expect(toIsoDay(written)).toBe("2000-01-02");
  });
});

describe("formatAsTyped", () => {
  it("adds the slashes as the digits arrive", () => {
    expect(formatAsTyped("2")).toBe("2");
    expect(formatAsTyped("20")).toBe("20");
    expect(formatAsTyped("204")).toBe("20/4");
    expect(formatAsTyped("2004")).toBe("20/04");
    expect(formatAsTyped("20041")).toBe("20/04/1");
    expect(formatAsTyped("20041998")).toBe("20/04/1998");
  });

  it("survives its own output, which is what a controlled field feeds it", () => {
    expect(formatAsTyped("20/04/1998")).toBe("20/04/1998");
  });

  it("takes a date pasted with any separator", () => {
    expect(formatAsTyped("20-04-1998")).toBe("20/04/1998");
    expect(formatAsTyped("20.04.1998")).toBe("20/04/1998");
    expect(formatAsTyped("1998-04-20")).toBe("19/98/0420");
  });

  it("drops the ninth digit, because there is no year 19980", () => {
    expect(formatAsTyped("200419989")).toBe("20/04/1998");
  });

  it("lets a backspace through the slash it inserted", () => {
    /* Deleting the final digit of 20/04/1 leaves "20/04/" in the box, whose
       digits are 2004, so the field settles on 20/04 and the caret does not
       sit behind a slash that cannot be removed. */
    expect(formatAsTyped("20/04/")).toBe("20/04");
  });
});
