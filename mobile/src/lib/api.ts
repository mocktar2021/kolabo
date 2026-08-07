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

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
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
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
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
