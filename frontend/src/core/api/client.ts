import { buildLoginUrl } from "@/core/auth/types";

import { isStateChangingMethod } from "./fetcher";

export type StateChangingMethod = "POST" | "PUT" | "DELETE" | "PATCH";

export const STATE_CHANGING_METHODS: ReadonlySet<StateChangingMethod> = new Set(
  ["POST", "PUT", "DELETE", "PATCH"],
);

export interface ClientFetchOptions extends RequestInit {
  /** When false, skip the automatic 401 → login redirect. Default: true. */
  redirectOn401?: boolean;
}

/**
 * Read the ``csrf_token`` cookie set by the gateway at login.
 *
 * SSR-safe: returns ``null`` when ``document`` is undefined so the same
 * helper can be imported from server components without a guard.
 */
export function readCsrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  for (const pair of document.cookie.split("; ")) {
    if (pair.startsWith("csrf_token=")) {
      return decodeURIComponent(pair.slice("csrf_token=".length));
    }
  }
  return null;
}

/**
 * Fetch with credentials and automatic CSRF protection.
 *
 * Two centralized contracts every API call needs:
 *
 * 1. ``credentials: "include"`` so the HttpOnly access_token cookie
 *    accompanies cross-origin SSR-routed requests.
 * 2. ``X-CSRF-Token`` header on state-changing methods (POST/PUT/
 *    DELETE/PATCH), echoed from the ``csrf_token`` cookie.
 *
 * Auto-redirects to ``/login`` on 401 (unless ``redirectOn401: false``).
 */
export async function clientFetch(
  input: RequestInfo | string,
  init?: ClientFetchOptions,
): Promise<Response> {
  const url = typeof input === "string" ? input : input.url;

  // Inject CSRF for state-changing methods
  let headers = init?.headers;
  if (isStateChangingMethod(init?.method ?? "GET")) {
    const token = readCsrfCookie();
    if (token) {
      const merged = new Headers(headers);
      if (!merged.has("X-CSRF-Token")) {
        merged.set("X-CSRF-Token", token);
      }
      headers = merged;
    }
  }

  const res = await globalThis.fetch(url, {
    ...init,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && init?.redirectOn401 !== false) {
    window.location.href = buildLoginUrl(window.location.pathname);
    throw new Error("Unauthorized");
  }

  return res;
}

/**
 * Build headers for CSRF-protected requests.
 *
 * For legacy call sites that need to compose headers manually.
 * Prefer ``clientFetch`` for new code.
 */
export function getCsrfHeaders(): HeadersInit {
  const token = readCsrfCookie();
  return token ? { "X-CSRF-Token": token } : {};
}
