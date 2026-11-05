/* Where the app sends every request, and the shape of that value that took
   the web app's write paths down on 5 November 2026.

   The base was "https://api.kolaboafrica.com/", and because every path
   already starts with "/" each call was built with a doubled slash. Measured
   against production the same afternoon: //health answered 200, and
   //auth/password-reset/request answered 404. A GET survives it and a POST
   does not, so the app looks alive while nothing a user does works.

   The web app took the value from a repository variable and this app takes it
   from the EAS production environment. Neither has a preflight in front of
   it, unlike a box that builds its own bundle, so the stripping lives in
   src/lib/config.ts and is pinned here.

   The loadConfig shape below is googleOffOnIos.test.ts's, for the same
   reason: config.ts resolves its values once at import time, so each case
   needs a fresh module graph or the first one in the file is the only one
   actually tested. */
import { afterEach, describe, expect, it, vi } from "vitest";

async function loadApiBase(
  envValue: string | undefined,
  committed: string | undefined = undefined
): Promise<string> {
  vi.resetModules();
  vi.doMock("react-native", () => ({ Platform: { OS: "android" } }));
  vi.doMock("expo-constants", () => ({
    default: { expoConfig: { extra: committed ? { apiBaseUrl: committed } : {} } },
  }));
  delete process.env.EXPO_PUBLIC_API_URL;
  if (envValue !== undefined) process.env.EXPO_PUBLIC_API_URL = envValue;
  const config = (await import("../src/lib/config")) as unknown as { API_BASE: string };
  return config.API_BASE;
}

afterEach(() => {
  delete process.env.EXPO_PUBLIC_API_URL;
  vi.doUnmock("react-native");
  vi.doUnmock("expo-constants");
  vi.resetModules();
});

describe("API_BASE", () => {
  it("strips a trailing slash, which is the case that broke the web app", async () => {
    expect(await loadApiBase("https://api.kolaboafrica.com/")).toBe(
      "https://api.kolaboafrica.com"
    );
  });

  it("strips however many slashes were typed", async () => {
    expect(await loadApiBase("https://api.kolaboafrica.com//")).toBe(
      "https://api.kolaboafrica.com"
    );
  });

  it("leaves a well formed base exactly as it is", async () => {
    expect(await loadApiBase("https://api.kolaboafrica.com")).toBe(
      "https://api.kolaboafrica.com"
    );
  });

  /* The fallback order is unchanged by the stripping: the environment wins,
     then anything committed in app.json, then localhost. PR #244 emptied the
     committed value on purpose, so in a real build the second step is absent
     and a production build with no variable set falls to localhost, which on
     a phone means the phone itself. That is why the variable is checked
     before a release rather than trusted. */
  it("falls back to a committed value, also stripped", async () => {
    expect(await loadApiBase(undefined, "https://api.kolabo.mocktar.com/")).toBe(
      "https://api.kolabo.mocktar.com"
    );
  });

  it("falls back to localhost when nothing is configured", async () => {
    expect(await loadApiBase(undefined)).toBe("http://localhost:8000");
  });

  it("treats an empty variable as absent rather than as a base", async () => {
    expect(await loadApiBase("   ", "https://api.kolabo.mocktar.com")).toBe(
      "https://api.kolabo.mocktar.com"
    );
  });
});
