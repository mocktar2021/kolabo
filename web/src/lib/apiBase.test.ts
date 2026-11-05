/* The base URL every request is built on, and the one shape of it that has
   taken production down.

   On 5 November 2026 VITE_API_URL was set to "https://api.kolaboafrica.com/"
   through a repository variable. api.ts builds `${BASE}${path}` and every
   path already begins with "/", so each call went to a doubled slash. That
   answers 200 on a GET, which is why the site looked healthy, and 404 on a
   POST, which is why nothing a user actually did worked. Both measured
   against production that afternoon.

   These cases pin the stripping. The workflow refuses the shape as well, and
   deploy/checks/preflight-env.sh refuses it for a box that builds its own
   bundle, so there are three defences for one mistake. That is proportionate:
   the fault is silent, it only shows on writes, and the value now arrives
   from three different places depending on who built the image. */
import { describe, expect, it } from "vitest";
import { apiBase } from "./api";

describe("apiBase", () => {
  it("strips a trailing slash, which is the case that broke production", () => {
    expect(apiBase("https://api.kolaboafrica.com/")).toBe("https://api.kolaboafrica.com");
  });

  it("strips however many slashes were typed", () => {
    expect(apiBase("https://api.kolaboafrica.com///")).toBe("https://api.kolaboafrica.com");
  });

  it("leaves a well formed base exactly as it is", () => {
    expect(apiBase("https://api.kolaboafrica.com")).toBe("https://api.kolaboafrica.com");
  });

  it("trims whitespace, since a pasted value carries it", () => {
    expect(apiBase("  https://api.kolaboafrica.com/  ")).toBe("https://api.kolaboafrica.com");
  });

  /* A path is not stripped, only the slash that ends it. A base with a path
     is a different mistake, refused in the workflow where it can be explained
     rather than silently rewritten here into something nobody asked for. */
  it("keeps a path but drops its trailing slash", () => {
    expect(apiBase("https://example.test/api/")).toBe("https://example.test/api");
  });

  it("answers empty for nothing, so the caller's own default applies", () => {
    expect(apiBase(undefined)).toBe("");
    expect(apiBase(null)).toBe("");
    expect(apiBase("")).toBe("");
    expect(apiBase("   ")).toBe("");
  });
});
