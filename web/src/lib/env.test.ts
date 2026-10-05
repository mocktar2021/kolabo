/* Two things, and the second is the one that catches the real mistake.

   The predicate is pure and worth pinning because it decides whether a whole
   deployment announces itself. The chain test is here because the variable has
   to be spelled identically in four files across two directories, and nothing
   else would notice if one of them drifted: a misspelling in the Dockerfile
   produces an empty value, which is a supported state, so the banner would
   simply appear on production with nothing anywhere saying why.

   A TypeScript declaration would not have caught that. Vite's own
   ImportMetaEnv is not strict unless a project opts in with ViteTypeOptions,
   and even strict typing only sees the TypeScript side: it cannot know what
   the Dockerfile or the compose file say. */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isProductionBuild } from "./env";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..", "..");
const REPO = resolve(WEB, "..");
const read = (p: string) => readFileSync(p, "utf8");

describe("isProductionBuild", () => {
  it("is true for production, however the value was whitespaced or cased", () => {
    expect(isProductionBuild("production")).toBe(true);
    expect(isProductionBuild("Production")).toBe(true);
    expect(isProductionBuild("PRODUCTION")).toBe(true);
    expect(isProductionBuild("  production  ")).toBe(true);
  });

  it("is false for everything else, nothing at all included", () => {
    const others = [undefined, "", "   ", "development", "dev", "prod", "staging", "productionn"];
    for (const raw of others) {
      expect(isProductionBuild(raw)).toBe(false);
    }
  });
});

describe("the build-arg chain", () => {
  it("is declared and forwarded in the Dockerfile", () => {
    const dockerfile = read(resolve(WEB, "Dockerfile"));
    expect(dockerfile).toContain("ARG VITE_KOLABO_ENV");
    expect(dockerfile).toContain("ENV VITE_KOLABO_ENV=$VITE_KOLABO_ENV");
  });

  it("is documented for a laptop", () => {
    expect(read(resolve(WEB, ".env.example"))).toContain("VITE_KOLABO_ENV=");
  });

  it("is fed from the deploy ENV rather than a second variable", () => {
    const compose = read(resolve(REPO, "deploy", "docker-compose.prod.yml"));
    /* The linkage is the point. Pointing this at its own variable would give
       a box two settings that can disagree about what it is. */
    expect(compose).toContain("VITE_KOLABO_ENV: ${ENV");
  });
});
