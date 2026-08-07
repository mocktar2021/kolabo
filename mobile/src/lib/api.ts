import { API_BASE } from "./config";

/* The mobile twin of web/src/lib/api.ts. Same shapes, same error contract, so
   a refusal reads the same on both clients and the ported errorMessages map
   (see ./errorMessages) turns the code into the reader's language.

   React Native ships a global fetch, so there is no platform shim here — the
   only differences from the web helper are that there is no import.meta and no
   browser FormData typing, and the base URL comes from Expo config. */

export const API_BASE_URL = API_BASE;

/* Build a full URL for a media path the API returns (e.g. an avatar). */
export function mediaSrc(path: string | null | undefined): string | undefined {
  return path ? `${API_BASE}${path}` : undefined;
}

export class ApiError extends Error {
  status: number;
  /* The stable name of the RULE that refused, when the backend sent one —
     "auth_bad_credentials", not a status and not a sentence. errorMessages.ts
     turns it into French or English. Null for a refusal not yet migrated to a
     code, or for anything that failed before the API answered; `message` then
     carries the backend's English fallback. */
  code: string | null;
  /* Interpolation values for that sentence (a ceiling, a count, a currency),
     carried as data so a number is never baked into two languages. */
  values: Record<string, unknown> | null;

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    values: Record<string, unknown> | null = null
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.values = values;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

function parseError(status: number, data: unknown, fallback: string): ApiError {
  const record = data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  const detail = (record && (record.detail || record.message)) || fallback;
  const code = record && typeof record.code === "string" ? record.code : null;
  const values =
    record && record.values && typeof record.values === "object"
      ? (record.values as Record<string, unknown>)
      : null;
  return new ApiError(status, typeof detail === "string" ? detail : fallback, code, values);
}

/* Every request goes through here, so the two ways a call can fail WITHOUT
   the API ever answering are handled once instead of on each screen.

   THE TRANSPORT FAILED. fetch rejects only when the request never completed:
   no route to the host, DNS failure, TLS refused, the radio dropped, the dev
   machine unreachable. React Native's message for all of it is the bare
   "Network request failed", which is English, untranslatable, and reads as a
   bug in the app rather than a phone with no signal — so it is replaced with
   a code errorMessages can say in the reader's language. This matters more
   here than on the web: the pilot markets are places where the connection
   drops mid-tap as a matter of course.

   THE BODY IS NOT THIS API. A captive portal, a proxy error page or an
   expired tunnel answers with HTML, and JSON.parse then throws a SyntaxError
   that reaches the screen as "Unexpected character: <". Caught and named,
   because the fix a reader needs — sign in to the Wi-Fi — is nowhere in a
   parser error.

   Status 0 marks "no response at all", the conventional reading, and keeps
   `e.status === 404` checks elsewhere honest: a 404 test must never be
   satisfied by a phone that never reached the server. */
async function request(url: string, init: RequestInit): Promise<{ res: Response; data: unknown }> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, "Network request failed", "network_unreachable");
  }

  const text = await res.text();
  if (!text) return { res, data: null };
  try {
    return { res, data: JSON.parse(text) };
  } catch {
    throw new ApiError(res.status, "Malformed response", "network_bad_response");
  }
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;

  const { res, data } = await request(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) throw parseError(res.status, data, "Something went wrong");
  return data as T;
}

/* A local image about to be uploaded, as React Native's fetch wants it: a
   {uri, name, type} triple appended to FormData. RN's runtime accepts this
   shape natively (it streams the file at `uri`); the DOM typings do not know
   it, hence the cast at the append site. */
export type LocalImage = { uri: string; name: string; type: string };

export type MediaOut = { id: string; url: string };

/* The mobile twin of web/src/lib/api.ts uploadFile: multipart POST with the
   file under the `file` field, no Content-Type header set by hand — fetch
   writes the multipart boundary itself, and setting it manually breaks the
   upload. */
export async function uploadMedia<T>(
  path: string,
  file: LocalImage,
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const form = new FormData();
  form.append("file", file as unknown as Blob);
  /* Through the same seam as api(): an upload is the request most likely to
     die on a weak connection, so it is the last one that should answer with
     an untranslated transport error. */
  const { res, data } = await request(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) throw parseError(res.status, data, "Upload failed");
  return data as T;
}

/* Auth response shapes, mirrored from backend/app/modules/auth/schemas.py. */
export type Role = "influencer" | "business" | "agency";
export type TokenResponse = { access_token: string; token_type: string; role: Role };
export type RegisterResponse = { user_id: string; message: string };
export type MeOut = {
  id: string;
  phone: string;
  role: Role;
  country_code: string;
  is_verified: boolean;
  created_at: string;
  display_name: string | null;
  avatar_url: string | null;
};

/* Exposed so a unit test can exercise the error-parsing branch without a
   network round-trip — the same seam the web suite tests. */
export const _internal = { parseError };
