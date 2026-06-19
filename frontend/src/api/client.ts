// Thin fetch wrapper. The SPA is served same-origin as the API under /api.
const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
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
