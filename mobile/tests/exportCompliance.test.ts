/* The export compliance declaration, and the facts it rests on.

   WHAT THIS IS. Apple asks every build what encryption the app implements.
   Answered in App Store Connect it is a dialog per upload; answered in the
   Info.plist it is once and for good. Apple's own wording for the key: set it
   to NO when the app, "including any third-party libraries you link against,"
   either uses no encryption "or only uses encryption that's exempt from export
   compliance requirements", and YES for non-exempt encryption, which then also
   needs a compliance code Apple issues. app.json therefore carries
   ITSAppUsesNonExemptEncryption: false, which Expo writes into the ipa's
   Info.plist at build time.

   WHY THAT ANSWER. Kolabo implements no encryption. It calls no crypto API of
   its own, it reaches the API over the TLS already built into iOS, and it
   keeps the session token in the iOS Keychain through expo-secure-store. The
   encryption it uses is the operating system's.

   SO THIS FILE GUARDS THE FACTS, NOT THE FLAG. A line in app.json cannot carry
   a comment and cannot notice when it stops being true. The day somebody adds
   a crypto library or hashes something in app code, that declaration becomes a
   false statement filed with Apple, and nothing would say so: the build would
   go out carrying an answer nobody re-read. These assertions are what say so.

   IF ONE OF THESE FAILS, the fix is not to widen the list. It is to work out
   what the new code does and whether the declaration still holds, and to change
   the declaration if it does not. */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const MOBILE = resolve(HERE, "..");
const read = (p: string) => readFileSync(p, "utf8");

/* Package names that mean somebody brought their own encryption. Two lists
   because package names split two ways: "expo-crypto" is a word among words,
   while "tweetnacl" is one word with the giveaway buried inside it. Matching
   whole words on the first list is what keeps a future "phrases" or "praise"
   from failing this test for its spelling. */
const CRYPTO_WORDS = new Set([
  "crypto",
  "cipher",
  "aes",
  "rsa",
  "bcrypt",
  "scrypt",
  "argon2",
  "openssl",
  "jose",
  "jwt",
]);
const CRYPTO_NAMES = ["tweetnacl", "libsodium", "sjcl", "forge", "jsencrypt", "cryptojs"];

function looksLikeCrypto(pkg: string): boolean {
  const flat = pkg.replace(/[^a-z0-9]/gi, "").toLowerCase();
  if (CRYPTO_NAMES.some((n) => flat.includes(n))) return true;
  return pkg
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .some((word) => CRYPTO_WORDS.has(word));
}

/* Every .ts and .tsx file under src, read once. The app's own code is the half
   of the declaration that this repo controls; the other half is the dependency
   list above. */
function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

describe("the app declares that it implements no encryption", () => {
  const app = JSON.parse(read(resolve(MOBILE, "app.json")));

  it("sets ITSAppUsesNonExemptEncryption to false in the Info.plist", () => {
    /* Literally false, not absent and not the string "false". Absent is what
       produced the Missing Compliance prompt on build 7, and a string is a
       plist value Apple reads as neither. */
    expect(app.expo.ios.infoPlist.ITSAppUsesNonExemptEncryption).toBe(false);
  });
});

describe("the facts that declaration rests on", () => {
  it("links no encryption library", () => {
    const pkg = JSON.parse(read(resolve(MOBILE, "package.json")));
    const named = Object.keys(pkg.dependencies ?? {}).filter(looksLikeCrypto);
    /* expo-secure-store is here and is not on this list on purpose: it is the
       iOS Keychain, which is the operating system's encryption and the thing
       the declaration is about using rather than implementing. */
    expect(named).toEqual([]);
  });

  it("calls no crypto API in its own code", () => {
    /* Call shapes, never bare words. An earlier pass of this check matched
       "conversation" and "hours" and would have failed on the French copy, so
       what is searched for here is the way a crypto API is actually reached:
       an import of one, or a call into one. */
    const patterns: [string, RegExp][] = [
      ["an import of node crypto", /from\s+[\"']crypto[\"']|require\(\s*[\"']crypto[\"']\s*\)/],
      ["an import of expo-crypto", /[\"']expo-crypto[\"']/],
      ["the Web Crypto API", /crypto\s*\.\s*subtle/],
      ["a node cipher or hash", /create(?:Cipher|Decipher|Hash|Hmac)\w*\s*\(/],
      ["CryptoJS", /\bCryptoJS\b/],
      ["an encrypt or decrypt call", /\b(?:encrypt|decrypt)\w*\s*\(/i],
    ];

    const offenders: string[] = [];
    for (const file of sourceFiles(resolve(MOBILE, "src"))) {
      const body = read(file);
      for (const [what, re] of patterns) {
        if (re.test(body)) offenders.push(`${file.slice(MOBILE.length + 1)}: ${what}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
