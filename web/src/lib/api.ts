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
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = { method?: string; body?: unknown; token?: string | null };

function parseError(status: number, data: unknown, fallback: string): ApiError {
  const detail = (data && typeof data === "object" && ((data as Record<string, unknown>).detail || (data as Record<string, unknown>).message)) || fallback;
  return new ApiError(status, typeof detail === "string" ? detail : fallback);
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;

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
