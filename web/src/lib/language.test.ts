/* THE CHOICE HAS TO SURVIVE THE PAGE.

   This file exists because of one bug and guards the fix for it. The language
   switch in the header called i18n.changeLanguage and nothing else, so the
   choice lived only in memory: a refresh, a second tab or a return visit put
   an English reader back into French. The failure was invisible from inside
   the app, because everything worked perfectly until the heap went away.

   What is worth asserting is small and exact, so these tests assert that and
   nothing more. Reading back what was written. French for somebody who has
   never chosen. A rejection of any value that is not one of the two languages
   this app actually ships. And, the one that would otherwise take the whole
   site down rather than merely losing a preference: a storage that throws.

   THE HOSTILE STORAGE CASE IS NOT PARANOIA. localStorage's getter throws in
   Safari private mode and in any browser configured to block site data, and
   initialLanguage() is called by src/i18n.ts at module init, at the top of
   main.tsx, before a single component has rendered. An exception there is a
   white page, not a missing setting. lib/auth.test.tsx guards the same
   property for the same reason on the session token.

   vi.stubGlobal rather than a DOM environment, exactly as auth.test.tsx does
   it: this package's vitest runs in node, the module reads the bare
   `localStorage` global, and a fake is both faster and able to be hostile on
   purpose. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_LANGUAGE, getStoredLanguage, initialLanguage, setStoredLanguage } from "./language";

const KEY = "kolabo_language";

function fakeStorage(seed: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(seed));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k)
  } as unknown as Storage;
}

/* Throws on every access, which is what a blocked store actually does. It
   does not return null. */
function hostileStorage(): Storage {
  const boom = (): never => {
    throw new Error("SecurityError: the operation is insecure.");
  };
  return {
    get getItem() { return boom(); },
    get setItem() { return boom(); },
    get removeItem() { return boom(); }
  } as unknown as Storage;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the chosen language survives the page", () => {
  it("reads back each language it wrote", () => {
    for (const lang of ["fr", "en"] as const) {
      const storage = fakeStorage();
      vi.stubGlobal("localStorage", storage);
      setStoredLanguage(lang);
      expect(storage.getItem(KEY)).toBe(lang);
      expect(getStoredLanguage()).toBe(lang);
      /* THE REGRESSION, in one line: this is what src/i18n.ts passes as
         `lng` on the next page load. Before the fix it was always French. */
      expect(initialLanguage()).toBe(lang);
    }
  });

  it("has chosen nothing when nothing is stored", () => {
    vi.stubGlobal("localStorage", fakeStorage());
    expect(getStoredLanguage()).toBeNull();
  });
});

describe("French is what a first visit gets", () => {
  it("falls back to French rather than to the browser or to English", () => {
    /* Four of the five launch markets are francophone, so this default is
       deliberate. If it ever changes it should change here, loudly, rather
       than drift out of a detector nobody chose to add. */
    expect(DEFAULT_LANGUAGE).toBe("fr");
    vi.stubGlobal("localStorage", fakeStorage());
    expect(initialLanguage()).toBe("fr");
  });

  it("ignores a stored value this app does not ship", () => {
    /* A key written by an older build, a half-written value, or somebody
       editing devtools. Handing "de" to i18next would resolve it against
       fallbackLng and leave the header switch highlighting neither button. */
    for (const junk of ["de", "FR", "", "fr-BJ"]) {
      vi.stubGlobal("localStorage", fakeStorage({ [KEY]: junk }));
      expect(getStoredLanguage()).toBeNull();
      expect(initialLanguage()).toBe("fr");
    }
  });
});

describe("a blocked store loses the preference and nothing else", () => {
  it("does not throw while reading, and answers French", () => {
    vi.stubGlobal("localStorage", hostileStorage());
    expect(() => initialLanguage()).not.toThrow();
    expect(initialLanguage()).toBe("fr");
  });

  it("does not throw while writing", () => {
    /* The switch has already changed the language in memory by the time this
       runs, so swallowing the failure leaves this tab correct. Throwing would
       reach a click handler and leave a broken control. */
    vi.stubGlobal("localStorage", hostileStorage());
    expect(() => setStoredLanguage("en")).not.toThrow();
  });
});
