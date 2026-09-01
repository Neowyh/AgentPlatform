/**
 * Single-seam re-export for the transport layer.
 *
 * This module is the historical ``client.ts`` location. All CSRF/fetch logic
 * now lives in ``fetcher.ts``. We keep this file as a thin adapter so
 * existing imports (`@/core/api/client`) stay valid while the **interface**
 * has one true owner — `fetcher.ts`. Depth: fetcher is deep, this file is
 * intentionally shallow (adapter, not duplication).
 */
export { fetch as clientFetch } from "./fetcher";
export {
  getCsrfHeaders,
  readCsrfCookie,
  isStateChangingMethod,
} from "./fetcher";
export type {
  StateChangingMethod,
  FetchOptions as ClientFetchOptions,
} from "./fetcher";
export { STATE_CHANGING_METHODS } from "./fetcher";
