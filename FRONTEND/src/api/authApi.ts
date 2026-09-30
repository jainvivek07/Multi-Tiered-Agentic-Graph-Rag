import type { Token, UserCreate } from '../types/api';

const PREFIX = '/api/v1/auth';
const ORIGIN = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const authApi = {
  /**
   * Login via OAuth2 form (FastAPI expects application/x-www-form-urlencoded).
   * The HttpOnly access_token + refresh_token cookies are set by the server.
   */
  login: async (email: string, password: string): Promise<Token> => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${ORIGIN}${PREFIX}/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    return parseResponse<Token>(res);
  },

  register: async (data: UserCreate): Promise<{ id: string; email: string }> => {
    const res = await fetch(`${ORIGIN}${PREFIX}/register`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return parseResponse(res);
  },

  logout: async (): Promise<void> => {
    await fetch(`${ORIGIN}${PREFIX}/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  },

  refresh: async (): Promise<Token> => {
    const res = await fetch(`${ORIGIN}${PREFIX}/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    return parseResponse<Token>(res);
  },
};
