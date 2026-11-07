const REFRESH_KEY = "chama.refresh";

let accessToken: string | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function storedRefresh(): string | null {
  try {
    return sessionStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  try {
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
    else sessionStorage.removeItem(REFRESH_KEY);
  } catch {
    /* Storage may be blocked; the session then lasts for this page only. */
  }
}

export function hasSession(): boolean {
  return Boolean(accessToken || storedRefresh());
}

/** Turns any DRF error body into one sentence a person can act on. */
export function messageFrom(body: unknown): string {
  if (typeof body === "string") return body;
  if (Array.isArray(body)) return body.map(messageFrom).join(" ");
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (record.detail) return messageFrom(record.detail);
    return Object.values(record).map(messageFrom).join(" ");
  }
  return "Something went wrong. Please try again.";
}

async function renew(): Promise<boolean> {
  const refresh = storedRefresh();
  if (!refresh) return false;
  const response = await fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    setTokens(null, null);
    return false;
  }
  const tokens = await response.json();
  setTokens(tokens.access, tokens.refresh ?? refresh);
  return true;
}

async function send(path: string, init: RequestInit, retry = true): Promise<Response> {
  if (!accessToken && storedRefresh()) await renew();
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && retry && (await renew())) return send(path, init, false);
  return response;
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await send(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(messageFrom(body), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const post = <T = unknown>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });

export const patch = <T = unknown>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export async function download(path: string, filename: string) {
  const response = await send(path, {});
  if (!response.ok) throw new ApiError("The file could not be prepared.", response.status);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
