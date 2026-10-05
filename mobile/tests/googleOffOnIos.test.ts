/* Google sign in is off on iOS, and this is what holds it off.

   WHY A TEST AT ALL FOR A ONE LINE GATE. The line is not the interesting part.
   What is interesting is that the OBVIOUS way to do this does not work, and
   fails silently: setting EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID="" in an EAS build
   profile looks exactly like turning Google off and does nothing, because an
   empty string is falsy and src/lib/config.ts falls straight through to the
   committed value in app.json. Somebody reading that file later, seeing a
   Platform check where this codebase otherwise treats a provider as pure
   configuration, will be tempted to tidy it into a build profile. The last
   case below is here to fail when they do.

   WHAT IS AT STAKE. App Store Review Guideline 4.8 applies to an app offering
   a third party login service, and its first exemption is an app that uses
   only its own sign in. Google on iOS means Sign in with Apple as well; no
   Google on iOS means neither is required. This gate is the whole of that
   difference, so it is worth more than one assertion.

   NO COMPONENT TESTS HERE, and not for lack of trying. mobile/vitest.config.ts
   runs environment "node" and collects only the test files under tests/, and the
   package carries no react-native testing library, so nothing in this suite can
   render a screen. Asserting "no Google button appears on iOS" would mean adding a
   test stack to the app in the same change as a store submission. What is
   pinned instead is the value every one of those buttons is drawn from, plus a
   source level check that googleConfigured() still reads it. The same technique
   web/src/lib/env.test.ts uses on the build arg chain, and for the same reason:
   the thing that can silently break is a link between files, not a function. */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, "..", "src");

/* Deliberately not real client ids, and deliberately non-empty: the point of
   every case is what happens to a value that IS there. */
const COMMITTED_WEB = "committed-web.apps.googleusercontent.com";
const COMMITTED_IOS = "committed-ios.apps.googleusercontent.com";
const FROM_ENV = "from-env.apps.googleusercontent.com";

const ENV_KEYS = [
  "EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID",
  "EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID",
] as const;

type Loaded = { GOOGLE_WEB_CLIENT_ID: string; GOOGLE_IOS_CLIENT_ID: string };

/* A fresh module graph per case, because config.ts resolves both ids once at
   import time. Without resetModules the first platform in the file would be
   the only one tested and the rest would pass against a cached answer. */
async function loadConfig(
  os: "ios" | "android",
  env: Partial<Record<(typeof ENV_KEYS)[number], string>> = {}
): Promise<Loaded> {
  vi.resetModules();
  vi.doMock("react-native", () => ({ Platform: { OS: os } }));
  vi.doMock("expo-constants", () => ({
    default: {
      expoConfig: {
        extra: {
          apiBaseUrl: "https://api.example.test",
          googleWebClientId: COMMITTED_WEB,
          googleIosClientId: COMMITTED_IOS,
        },
      },
    },
  }));
  for (const key of ENV_KEYS) delete process.env[key];
  Object.assign(process.env, env);
  return (await import("../src/lib/config")) as unknown as Loaded;
}

afterEach(() => {
  for (const key of ENV_KEYS) delete process.env[key];
  vi.doUnmock("react-native");
  vi.doUnmock("expo-constants");
  vi.resetModules();
});

describe("on iOS there is no Google client id, whatever is configured", () => {
  it("returns empty for both ids even though app.json commits real ones", async () => {
    const config = await loadConfig("ios");
    expect(config.GOOGLE_WEB_CLIENT_ID).toBe("");
    expect(config.GOOGLE_IOS_CLIENT_ID).toBe("");
  });

  /* The gate is above the env var, not beside it. An operator who sets the
     variable on an iOS build has not re-enabled Google by accident. */
  it("stays empty even when the env var is set", async () => {
    const config = await loadConfig("ios", {
      EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: FROM_ENV,
      EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID: FROM_ENV,
    });
    expect(config.GOOGLE_WEB_CLIENT_ID).toBe("");
    expect(config.GOOGLE_IOS_CLIENT_ID).toBe("");
  });
});

describe("Android is untouched, which is the other half of the decision", () => {
  it("takes the committed value from app.json", async () => {
    const config = await loadConfig("android");
    expect(config.GOOGLE_WEB_CLIENT_ID).toBe(COMMITTED_WEB);
    expect(config.GOOGLE_IOS_CLIENT_ID).toBe(COMMITTED_IOS);
  });

  it("lets the env var override the committed value", async () => {
    const config = await loadConfig("android", {
      EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: FROM_ENV,
    });
    expect(config.GOOGLE_WEB_CLIENT_ID).toBe(FROM_ENV);
  });

  /* THE CASE THAT EXPLAINS WHY THE GATE IS A PLATFORM CHECK. This is the
     behaviour somebody will assume can replace it. An empty env var is falsy,
     so it does not win; it disappears, and the committed id arrives instead.
     If this ever starts returning "" then an EAS profile really could turn
     Google off and the Platform check in config.ts could be reconsidered. Until
     then, do not move this decision into configuration. */
  it("ignores an empty env var and falls through to the committed id", async () => {
    const config = await loadConfig("android", {
      EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: "",
    });
    expect(config.GOOGLE_WEB_CLIENT_ID).toBe(COMMITTED_WEB);
  });
});

describe("the gate reaches every caller", () => {
  /* googleConfigured() is what every screen asks before drawing anything
     Google, and it is the single hop between the ids above and the UI. It is
     asserted as source text rather than imported because importing it pulls in
     the native Google module and lib/api, neither of which loads in a node
     test. If the definition changes shape, this fails and whoever changed it
     reads this comment. */
  it("googleConfigured() still answers from the web client id alone", () => {
    const text = readFileSync(join(SRC, "lib", "googleSignIn.ts"), "utf8");
    /* MATCHED LOOSELY ON PURPOSE, because this is the one assertion in the file
       that reads a module the change it guards does not touch. An exact string
       would also fail on a reformat: a different quote style, a line break, a
       dropped semicolon. That failure would be red for a reason unrelated to
       the iOS gate, pointing at a file nobody had edited, which is a worse
       outcome than the coupling itself. So the shape is pinned and the spacing
       is not. If this ever fails, read googleSignIn.ts before anything here. */
    expect(text).toMatch(/return\s+GOOGLE_WEB_CLIENT_ID\s*!==\s*""/);
    expect(text).toMatch(/GOOGLE_WEB_CLIENT_ID[\s\S]*?from\s+"\.\/config"/);
  });

  /* One decision in one place. A second Platform check for Google anywhere in
     src/ would mean two answers to one question, which is the state this change
     was made to avoid. */
  it("config.ts is the only place that decides it", () => {
    const text = readFileSync(join(SRC, "lib", "config.ts"), "utf8");
    expect(text).toContain('const GOOGLE_OFF = Platform.OS === "ios";');
    expect(text.match(/Platform\.OS/g) ?? []).toHaveLength(1);
  });
});
