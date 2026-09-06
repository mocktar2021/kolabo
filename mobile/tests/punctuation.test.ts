/* No em dash or en dash reaches a user.

   This is a house style rule, not a typography opinion: the copy on Kolabo is
   written to read like a person wrote it, and a long dash in the middle of a
   sentence is the single strongest tell that one did not. The rule was easy to
   hold while the catalogues were small and impossible to hold by eye once they
   were not, which is what this test is for.

   Scope: anything the user can see. Every string literal, every template
   literal, and every run of JSX text between tags, in every .ts and .tsx under
   mobile/src, plus the locale JSON. Comments are exempt, and there are well
   over a thousand dashes in them; they ship to nobody and rewriting them would
   bury the parts of a diff that matter.

   The scanner is a small state machine rather than a regular expression,
   because the two things a regex gets wrong here are exactly the two things
   that occur: a "//" inside a string is not a comment, and a dash inside a
   ${...} interpolation is code, not copy.

   This file has to live under mobile/tests/. The include glob in
   vitest.config.ts collects test files under tests/ and nowhere else, so the
   same file under mobile/src/ would be collected by nothing and would pass by
   never running.

   The web half of this rule lives in web/src/lib/punctuation.test.ts. The two
   are deliberate duplicates: the packages do not share a module, and a guard
   that only one app runs is worse than no guard, because it reads as though
   both are covered.

   Note this file never writes either dash as a literal, so it does not have to
   exempt itself from its own rule. */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, ".."); // mobile/
const SRC = join(ROOT, "src");
const LOCALES = join(ROOT, "locales");

const EM_DASH = String.fromCharCode(0x2014);
const EN_DASH = String.fromCharCode(0x2013);
const FORBIDDEN = new Set([EM_DASH, EN_DASH]);

const NAMES: Record<string, string> = { [EM_DASH]: "em dash", [EN_DASH]: "en dash" };

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) sourceFiles(full, out);
    else if (name.endsWith(".ts") || name.endsWith(".tsx")) out.push(full);
  }
  return out;
}

/* Offsets of every forbidden dash that is NOT inside a comment.

   States: code (which is also JSX text, and that is the point), a single- or
   double-quoted string, a template literal, a // line comment, a block
   comment. `stack` carries the template literal across a ${...} so the closing
   brace returns to it rather than to top-level code. */
export function visibleDashes(text: string): number[] {
  const found: number[] = [];
  let state = "code";
  const stack: string[] = [];
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    const next = text[i + 1];
    if (state === "code") {
      if (c === "/" && next === "/") { state = "line"; i += 2; continue; }
      if (c === "/" && next === "*") { state = "block"; i += 2; continue; }
      if (c === "'" || c === '"') { state = c; i += 1; continue; }
      if (c === "`") { state = "tpl"; i += 1; continue; }
      if (c === "}" && stack.length) { state = stack.pop() as string; i += 1; continue; }
      if (FORBIDDEN.has(c)) found.push(i);
      i += 1;
      continue;
    }
    if (state === "line") {
      if (c === "\n") state = "code";
      i += 1;
      continue;
    }
    if (state === "block") {
      if (c === "*" && next === "/") { state = "code"; i += 2; continue; }
      i += 1;
      continue;
    }
    if (state === "tpl") {
      if (c === "\\") { i += 2; continue; }
      if (c === "`") { state = "code"; i += 1; continue; }
      if (c === "$" && next === "{") { stack.push("tpl"); state = "code"; i += 2; continue; }
      if (FORBIDDEN.has(c)) found.push(i);
      i += 1;
      continue;
    }
    // inside a quoted string
    if (c === "\\") { i += 2; continue; }
    if (c === state) { state = "code"; i += 1; continue; }
    if (c === "\n") { state = "code"; i += 1; continue; } // unterminated, resync
    if (FORBIDDEN.has(c)) found.push(i);
    i += 1;
  }
  return found;
}

function lineOf(text: string, index: number): number {
  let line = 1;
  for (let i = 0; i < index; i += 1) if (text[i] === "\n") line += 1;
  return line;
}

describe("the scanner tells copy from comment", () => {
  /* The scanner is the whole test. If it silently stopped seeing strings, the
     rule would pass forever while the dashes came back. */
  it("sees a dash in a string, a template and JSX text", () => {
    expect(visibleDashes(`const a = "x ${EM_DASH} y";`)).toHaveLength(1);
    expect(visibleDashes("const a = `x " + EM_DASH + " y`;")).toHaveLength(1);
    expect(visibleDashes(`<Text>x ${EM_DASH} y</Text>`)).toHaveLength(1);
    expect(visibleDashes(`const a = "x ${EN_DASH} y";`)).toHaveLength(1);
  });

  it("ignores a dash in either kind of comment", () => {
    expect(visibleDashes(`// x ${EM_DASH} y`)).toEqual([]);
    expect(visibleDashes(`/* x ${EM_DASH} y */`)).toEqual([]);
    expect(visibleDashes(`{/* x ${EM_DASH} y */}`)).toEqual([]);
  });

  it("does not mistake a url in a string for a comment", () => {
    expect(visibleDashes(`const u = "https://k.co"; const a = "x ${EM_DASH} y";`)).toHaveLength(1);
  });

  it("comes back out of an interpolation into the template", () => {
    expect(visibleDashes("`a ${b} c " + EM_DASH + " d`")).toHaveLength(1);
  });

  it("does not treat an apostrophe inside a double-quoted string as a string", () => {
    expect(visibleDashes(`const a = "don't"; // ${EM_DASH}`)).toEqual([]);
  });
});

describe("no dash reaches a user", () => {
  it("has none in any string, template or JSX text under mobile/src", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const text = readFileSync(file, "utf8");
      for (const index of visibleDashes(text)) {
        offenders.push(
          `${relative(ROOT, file)}:${lineOf(text, index)} ${NAMES[text[index]]}`
        );
      }
    }
    /* If this fails: rewrite the sentence, do not reach for a hyphen. A dash
       is usually doing one of three jobs, and each has a plainer form. Joining
       two sentences, so use a full stop. Introducing a list or an explanation,
       so use a colon. Wrapping an aside, so use a pair of commas or brackets.
       Comments are exempt; move the dash into one only if it belongs there. */
    expect(offenders).toEqual([]);
  });

  it("has none in the locale JSON", () => {
    /* No comments to exempt in JSON, so every occurrence counts. */
    const offenders: string[] = [];
    if (existsSync(LOCALES)) {
      for (const name of readdirSync(LOCALES)) {
        if (!name.endsWith(".json")) continue;
        const text = readFileSync(join(LOCALES, name), "utf8");
        for (let i = 0; i < text.length; i += 1) {
          if (FORBIDDEN.has(text[i])) {
            offenders.push(`locales/${name}:${lineOf(text, i)} ${NAMES[text[i]]}`);
          }
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
