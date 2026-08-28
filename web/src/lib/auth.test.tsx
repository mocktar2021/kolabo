/* THE FIRST RENDER MUST ALREADY BE SIGNED IN.

   This file exists because of one bug, and it is worth restating so the test
   is not mistaken for ceremony. AuthProvider used to start with a null token
   and hydrate it from localStorage in a useEffect. Every guarded page in this
   app renders `<Navigate to="/login" replace />` when isAuthenticated is
   false, Navigate redirects from an effect of its own, and React runs a
   child's effects before its parents' — so the redirect won the race and the
   hydration landed on a page that was already /login. Refreshing any screen
   signed you out, and so did returning from the payment gateway, which is a
   full page load onto /checkout/return by construction.

   renderToString is the right instrument for exactly one reason: it performs
   the first render pass and NO effects. That is the moment the guards read
   isAuthenticated, so it is the moment worth asserting on. Against the old
   code these tests fail; against any future version that moves the read back
   into an effect, they fail again. That is the whole job. */
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, getStoredRole, isBusinessLike, useAuth } from "./auth";

const TOKEN_KEY = "kolabo_token";
const ROLE_KEY = "kolabo_role";

/* {"sub":"user-123"} as the middle segment. The header and signature are
   never parsed by decodeUserId, so they are only there to make it a JWT. */
const TOKEN = `header.${btoa(JSON.stringify({ sub: "user-123" }))}.signature`;

function fakeStorage(seed: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(seed));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k)
  } as unknown as Storage;
}

/* A storage that throws on every access, which is what Safari private mode
   and a browser with site data blocked actually do — they do not return null.
   An exception thrown while computing initial state takes down the whole
   tree, so "signed out" is the required behaviour here and "white page" is
   not. */
function hostileStorage(): Storage {
  const boom = (): never => {
    throw new Error("SecurityError: the operation is insecure.");
  };
  return {
    get getItem() { return boom(); },
    get setItem() { return boom(); },
    get removeItem() { return boom(); }
  } as unknown as Storage;
}

type Seen = { token: string | null; userId: string | null; isAuthenticated: boolean };

function firstRenderWith(storage: Storage): Seen {
  vi.stubGlobal("localStorage", storage);
  const box: { seen: Seen | null } = { seen: null };
  function Probe() {
    const { token, userId, isAuthenticated } = useAuth();
    box.seen = { token, userId, isAuthenticated };
    return null;
  }
  renderToString(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  );
  if (box.seen === null) throw new Error("the probe never rendered");
  return box.seen;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the session survives a page load", () => {
  it("is authenticated on the very first render, before any effect runs", () => {
    const seen = firstRenderWith(fakeStorage({ [TOKEN_KEY]: TOKEN }));
    /* THE REGRESSION. False here means every guarded page redirects to
       /login on refresh and on the return from checkout. */
    expect(seen.isAuthenticated).toBe(true);
    expect(seen.token).toBe(TOKEN);
  });

  it("has the user id on that same first render", () => {
    /* Not decoration: pages read userId to decide which side of a contract or
       a dispute thread they are looking at, and they read it in the same pass
       the guard runs in. */
    expect(firstRenderWith(fakeStorage({ [TOKEN_KEY]: TOKEN })).userId).toBe("user-123");
  });

  it("is not authenticated when nothing is stored", () => {
    const seen = firstRenderWith(fakeStorage());
    expect(seen.isAuthenticated).toBe(false);
    expect(seen.token).toBeNull();
    expect(seen.userId).toBeNull();
  });

  it("renders a signed-out app rather than throwing when storage is blocked", () => {
    expect(() => firstRenderWith(hostileStorage())).not.toThrow();
    expect(firstRenderWith(hostileStorage()).isAuthenticated).toBe(false);
  });

  it("survives a stored value that is not a JWT", () => {
    /* A token from an older build, or a half-written value. Signed in with no
       id beats a crash on the first paint. */
    const seen = firstRenderWith(fakeStorage({ [TOKEN_KEY]: "not-a-jwt" }));
    expect(seen.isAuthenticated).toBe(true);
    expect(seen.userId).toBeNull();
  });
});

describe("the stored role", () => {
  it("reads back each of the three roles", () => {
    for (const role of ["influencer", "business", "agency"] as const) {
      vi.stubGlobal("localStorage", fakeStorage({ [ROLE_KEY]: role }));
      expect(getStoredRole()).toBe(role);
    }
  });

  it("is null for anything else, including nothing at all", () => {
    vi.stubGlobal("localStorage", fakeStorage());
    expect(getStoredRole()).toBeNull();
    vi.stubGlobal("localStorage", fakeStorage({ [ROLE_KEY]: "admin" }));
    expect(getStoredRole()).toBeNull();
  });

  it("is null rather than an exception when storage is blocked", () => {
    /* BrandOnly and CreatorOnly call this during render. A throw here is the
       same white page as a throw in the provider. */
    vi.stubGlobal("localStorage", hostileStorage());
    expect(() => getStoredRole()).not.toThrow();
    expect(getStoredRole()).toBeNull();
  });
});

describe("isBusinessLike", () => {
  it("counts an agency as a buyer", () => {
    /* The reason the helper exists: agencies buy the way businesses do, and
       every role branch in the app goes through here rather than comparing
       against "business" directly. */
    expect(isBusinessLike("agency")).toBe(true);
    expect(isBusinessLike("business")).toBe(true);
  });

  it("does not count a creator, or an absent role", () => {
    expect(isBusinessLike("influencer")).toBe(false);
    expect(isBusinessLike(null)).toBe(false);
    expect(isBusinessLike(undefined)).toBe(false);
  });
});
