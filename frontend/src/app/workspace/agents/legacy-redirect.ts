export type LegacySearchParams = Record<string, string | string[] | undefined>;

/**
 * Build a redirect target that carries the original URL's query string onto
 * the replacement path, so legacy deep links (e.g. `?mock=true`) survive the
 * hop. String values map to single parameters, arrays to repeated ones, and
 * `undefined` entries are dropped.
 */
export function legacyRedirectTarget(
  base: string,
  search: LegacySearchParams,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (typeof value === "string") {
      query.set(key, value);
    } else if (Array.isArray(value)) {
      for (const item of value) query.append(key, item);
    }
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return `${base}${suffix}`;
}
