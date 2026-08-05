/* Tiny fetch wrapper around the Kolabo API. The base URL comes from
   VITE_API_URL so the same build points at local, staging, or production. */
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const API_BASE = BASE;

/* Build a full URL for a media path returned by the API (e.g. an image). */
export function mediaSrc(path: string | null | undefined): string | undefined {
  return path ? `${BASE}${path}` : undefined;
}

export class ApiError extends Error {
  status: number;
  /* The stable name of the RULE that refused, when the backend sent one:
     "deliverable_already_answered", not a status and not a sentence. It is
     what lib/errorMessages.ts turns into French — see there for the fallback
     order, and backend/app/core/errors.py for where it comes from.

     Null for every refusal not yet migrated (most of them, today) and for
     anything that failed before the API answered at all. A null code is not
     an error condition: `message` still carries the backend's English, which
     is what the app showed before codes existed. */
  code: string | null;
  /* Interpolation values for that sentence — a ceiling, a count, a currency.
     They travel as data so a number is not baked into two languages that then
     drift apart from each other and from the constant. */
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

/* token is a normal user's bearer JWT.

   adminId is NOT authentication. Admin login and RBAC are not built yet, so
   the backend takes admin identity from an X-Admin-Id header — a deliberate
   placeholder documented in backend/app/modules/admin/router.py, enough to
   attribute and log decisions during the manual pilot. It lives here rather
   than in the one page that needs it because the dispute queue reads from
   both /admin and /payments, and a second fetch helper for the same API is
   how two of them end up disagreeing about error parsing. When real admin
   auth arrives this option is what gets deleted. */
type Options = {
  method?: string;
  body?: unknown;
  token?: string | null;
  adminId?: string | null;
};

function parseError(status: number, data: unknown, fallback: string): ApiError {
  const record = data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  const detail = (record && (record.detail || record.message)) || fallback;
  /* `detail` is still read exactly as it always was, including the
     typeof-string guard that quietly swallows FastAPI's 422 validation array.
     code and values are read ALONGSIDE it, never instead of it: an endpoint
     that has not been migrated returns no code, and this produces the same
     ApiError it produced before any of this existed. */
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
  if (opts.adminId) headers["X-Admin-Id"] = opts.adminId;

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw parseError(res.status, data, "Something went wrong");
  return data as T;
}

/* Multipart upload for images. Does not set Content-Type so the browser adds
   the multipart boundary. */
export async function uploadFile<T>(path: string, file: File, token?: string | null): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: form });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw parseError(res.status, data, "Upload failed");
  return data as T;
}

/* The role rides along with every token grant so the frontend can restore
   the right experience after a fresh login. */
export type TokenResponse = { access_token: string; token_type: string; role: "influencer" | "business" | "agency" };
export type RegisterResponse = { user_id: string; message: string };
