/**
 * Authenticated fetch client.
 *
 * All requests use `credentials: 'include'` so the HttpOnly cookie
 * (access_token) is sent automatically by the browser.
 * On 401 the client clears the auth store and redirects to /login.
 */
import { useAuthStore } from '../store/authStore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  public readonly status: number;
  public readonly body?: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    // 204 No Content
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = await res.text();
  }

  if (res.status === 401) {
    useAuthStore.getState().clearUser();
    window.location.href = '/login';
  }

  const message =
    typeof body === 'object' && body !== null && 'detail' in body
      ? String((body as Record<string, unknown>).detail)
      : `HTTP ${res.status}`;

  throw new ApiError(res.status, message, body);
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  params?: Record<string, string | number | undefined>;
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, params, headers, ...rest } = options;

  const init: RequestInit = {
    credentials: 'include',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    ...rest,
  };

  const res = await fetch(buildUrl(path, params), init);
  return handleResponse<T>(res);
}

/** Returns the raw Response for endpoints that handle streaming manually. */
export async function apiFetchRaw(path: string, options: RequestOptions = {}): Promise<Response> {
  const { params, headers, body, ...rest } = options;
  const res = await fetch(buildUrl(path, params), {
    credentials: 'include',
    headers: { ...headers },
    body: body as BodyInit | null | undefined,
    ...rest,
  });
  if (!res.ok) await handleResponse<never>(res);
  return res;
}

export { BASE_URL };
