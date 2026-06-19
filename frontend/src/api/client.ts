// Thin fetch wrapper. The SPA is served same-origin as the API under /api.
// A bearer token (when present) is attached to every request; a 401 on an authenticated
// request clears the token and signals the app to return to the login screen.
const BASE = "/api";
const TOKEN_KEY = "ft_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(BASE + path, { ...init, headers });

  if (res.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event("ft-unauthorized"));
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string) => req<T>(path);
export const apiPost = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body != null ? JSON.stringify(body) : undefined });
export const apiPatch = <T>(path: string, body: unknown) =>
  req<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const apiDelete = (path: string) => req<void>(path, { method: "DELETE" });
