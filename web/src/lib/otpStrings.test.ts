/* The verification screen tells people where the code actually went, in both
   languages, and keeps telling them after the next change.

   THE SENTENCE THIS REPLACED SHIPPED TO PRODUCTION FOR MONTHS. i18n.ts says,
   under auth.otpDevHint, "In development the code is written to the server
   logs". It was written for whoever was running the stack on a laptop, and
   production showed it to every person who signed up: a note about server logs
   on the one screen a new user cannot skip, in place of the one fact they need,
   which is that an email is on its way and may be in their spam folder.

   SO THERE ARE TWO THINGS TO HOLD, and they are different in kind.

   The first is ordinary: both languages exist and neither is empty. A missing
   key fails nothing on its own, because i18next falls back to the other
   language and renders English in the middle of a French screen with a green
   build behind it, which is the failure googleStrings.test.ts and
   errorMessages.test.ts already exist for.

   The second is that the old key stays dead. auth.otpDevHint is still in
   i18n.ts, unused, because this bundle adds the replacement rather than
   rewriting 600 lines of bilingual copy to remove one line. A dead key that
   still resolves is a key somebody reaches for by autocomplete, so this suite
   reads the source of every page and component and fails if any of them render
   it again. Deleting the key belongs with the next edit to i18n.ts. */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { otp_auth_en, otp_auth_fr } from "./otpStrings";

describe("the two languages agree", () => {
  it("has the same keys", () => {
    expect(Object.keys(otp_auth_fr).sort()).toEqual(Object.keys(otp_auth_en).sort());
  });

  it("has no empty sentence", () => {
    for (const value of [...Object.values(otp_auth_fr), ...Object.values(otp_auth_en)]) {
      expect(value.trim()).not.toBe("");
    }
  });

  it("says email in both, because that is the fact being delivered", () => {
    /* Not a translation check: nothing here can tell whether the French is
       good. What it can tell is that neither sentence lost the only piece of
       information it exists to carry. */
    expect(otp_auth_fr.otpHint.toLowerCase()).toContain("e-mail");
    expect(otp_auth_en.otpHint.toLowerCase()).toContain("email");
  });
});

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, ".."); // web/src

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === "dist" || name.startsWith(".")) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) sourceFiles(full, out);
    else if (name.endsWith(".ts") || name.endsWith(".tsx")) out.push(full);
  }
  return out;
}

/* The CALL, not the name. Several files in this package mention the dead key
   in a comment while explaining why it is dead, including this one, and a scan
   for the bare name would fail on its own documentation. What matters is
   whether a screen asks i18next for it. */
const RENDERS_OLD_KEY = /t\(\s*["']auth\.otpDevHint["']\s*\)/;

describe("the development only hint", () => {
  it("is rendered by nothing", () => {
    const offenders = sourceFiles(SRC)
      .filter((file) => RENDERS_OLD_KEY.test(readFileSync(file, "utf8")))
      .map((file) => relative(SRC, file).split("\\").join("/"));
    expect(offenders).toEqual([]);
  });
});
