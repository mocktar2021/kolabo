/* No committed configuration may point a build at the development API.

   KOL-124. What was found: `mobile/app.json` committed
   extra.apiBaseUrl = the development API, and `mobile/eas.json` set the same
   development URL in ALL THREE build profiles, production included. So a
   production build pointed at the dev box by design rather than by accident,
   and the failure mode is the quiet one. The app looks right, signs in, and
   writes to a database nothing depends on. A pilot creator in that build has
   an account that exists nowhere that matters, and nobody finds out until
   they ask where their profile went. A smoke test passes, because everything
   works.

   WHY A TEST AND NOT A COMMENT. The dev URL is the correct value for two of
   the three profiles, so it cannot be banned outright, and "the right string
   in the wrong profile" is exactly the kind of thing a hurried edit
   reintroduces. The check is cheap and reads the committed files rather than
   the runtime, which is the same technique googleOffOnIos.test.ts uses on
   the client ids: what breaks silently here is a link between two config
   files, not a function.

   THE FAILURE THIS TRADES FOR, stated so nobody is surprised by it. With no
   committed default, a production build that forgets EXPO_PUBLIC_API_URL
   falls through to http://localhost:8000, which on a handset is the handset.
   Nothing works at all. That is strictly better than pointing at dev: it is
   found by opening the build once, and it cannot write to anything. The
   production URL belongs in the EAS project's own environment, for the same
   reason deploy/.env.example leaves the production hostnames blank. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const json = (p: string) => JSON.parse(readFileSync(resolve(HERE, p), "utf8"));

const APP = json("../app.json");
const EAS = json("../eas.json");

/* The development API, named once. deploy/.env.example identifies this host
   as the dev one; it is not a guess. */
const DEV_API = "https://api.kolabo.mocktar.com";

const apiUrlOf = (profile: string): string | undefined =>
  EAS.build?.[profile]?.env?.EXPO_PUBLIC_API_URL;

describe("app.json commits no API url at all", () => {
  it("has no extra.apiBaseUrl", () => {
    expect(APP.expo?.extra?.apiBaseUrl).toBeUndefined();
  });

  it("does not mention the development API anywhere in the file", () => {
    // Belt and braces: a default could come back under another key, or in a
    // plugin's options, and still decide where a build points.
    expect(readFileSync(resolve(HERE, "../app.json"), "utf8")).not.toContain(DEV_API);
  });
});

describe("the eas build profiles", () => {
  it("does not point the production profile at the development API", () => {
    // The whole ticket, in one assertion.
    expect(apiUrlOf("production")).not.toBe(DEV_API);
  });

  it("leaves the production API url out of the repository entirely", () => {
    // It comes from the EAS project's environment. A production URL committed
    // here would be the same class of mistake pointing the other way, and the
    // first thing a fork or a leaked tree would carry.
    expect(apiUrlOf("production")).toBeUndefined();
  });

  it("still names the development API explicitly for development and preview", () => {
    // These two SHOULD target dev, and they should say so rather than relying
    // on a fallback. If this fails, those builds are silently on localhost.
    expect(apiUrlOf("development")).toBe(DEV_API);
    expect(apiUrlOf("preview")).toBe(DEV_API);
  });
});
