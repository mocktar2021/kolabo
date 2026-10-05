/* The catch-all route, asserted as source text rather than by rendering it.

   WHY NOT A RENDER TEST. App owns its own BrowserRouter, so it cannot be
   mounted at a chosen URL without changing its shape, and this package's
   vitest runs in node with no jsdom (see language.test.ts), so there is no
   history to drive it with either. The repository already asserts on source
   text where running the thing is out of reach: punctuation.test.ts walks
   web/src and reads files, and the backend's test_schema_owned_by_migrations
   parses migrations as text for the same reason.

   WHAT IT IS FOR. Nothing else in this suite renders a route, so deleting the
   catch-all would restore the blank white page silently and no test would go
   red. This is the thing that notices. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..", "App.tsx");
const source = readFileSync(APP, "utf8");

function declaredRoutes(): string[] {
  const found: string[] = [];
  const re = /<Route path="([^"]*)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) found.push(m[1]);
  return found;
}

describe("the router", () => {
  it("declares a catch-all and renders NotFound from it", () => {
    expect(source).toContain('import NotFound from "./pages/NotFound"');
    expect(source).toMatch(/<Route path="\*" element=\{<NotFound \/>\} \/>/);
  });

  it("declares exactly one catch-all, and keeps it last", () => {
    const routes = declaredRoutes();
    /* A floor rather than an exact count: routes get added, and a test that
       had to be edited every time one was would be edited without being
       read. */
    expect(routes.length).toBeGreaterThan(30);
    expect(routes.filter((p) => p === "*")).toHaveLength(1);
    expect(routes[routes.length - 1]).toBe("*");
  });
});
