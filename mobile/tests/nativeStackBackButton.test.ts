/* The back arrow stopped working after one use, and the cause was a
   dependency rather than anything in this app.

   WHAT WENT WRONG. react-native-screens 4.16.0, the version Expo SDK 54 pins,
   disables the native back button while a pop animates so that no tap
   highlight is drawn, and relies on didPopItem to switch it back on. Its own
   comment in ios/RNSScreenStack.mm concedes that the button instance changes
   on a regular pop and that "the value of userInteractionEnabled is carried
   on". On iOS 26 the wrapper view is reused for the next push carrying the
   disabled flag, so exactly one back tap works per launch. Reported on a
   TestFlight build on 5 November 2026 as "it works only the first time", and
   seen in another Expo app of ours on the same SDK before that.

   It never appeared on Android because that code sits inside an iOS 26
   availability guard and Android never compiled it.

   WHY THIS TEST EXISTS RATHER THAN A COMMENT. The fix is a pinned version, and
   a pinned version is one `expo install --fix` away from being helpfully
   reverted to the SDK's own pin, which would reintroduce a bug nobody would
   connect to a dependency change. The three assertions below each fail on a
   different way of losing the fix.

   WHEN TO DELETE THIS FILE. When Expo's SDK pin moves past 4.17.1 by itself.
   At that point the exclusion is the only thing holding the app back and this
   test would be defending a floor nobody needs. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const MOBILE = resolve(HERE, "..");
const read = (p: string) => readFileSync(p, "utf8");
const json = (p: string) => JSON.parse(read(p));

describe("react-native-screens is pinned past the iOS 26 back button bug", () => {
  it("declares an exact version, not a range the SDK pin can win", () => {
    const declared = json(resolve(MOBILE, "package.json")).dependencies["react-native-screens"];
    /* Exact, with no ~ or ^: a range is how 4.16.0 comes back. */
    expect(declared).toBe("4.17.1");
  });

  it("has the fixed version actually installed", () => {
    const installed = json(
      resolve(MOBILE, "node_modules", "react-native-screens", "package.json")
    ).version;
    expect(installed).toBe("4.17.1");
  });

  /* The assertion that survives a renumbering. If a future version brings the
     behaviour back under a different release number, the version checks above
     would still pass and this one would not. */
  it("does not ship the code that disables the back button", () => {
    const source = read(
      resolve(MOBILE, "node_modules", "react-native-screens", "ios", "RNSScreenStack.mm")
    );
    expect(source).not.toContain("shouldPopItem");
    expect(source).not.toContain("userInteractionEnabled = false");
  });

  it("tells expo install --fix to leave it alone", () => {
    const pkg = json(resolve(MOBILE, "package.json"));
    expect(pkg.expo?.install?.exclude).toContain("react-native-screens");
  });
});
