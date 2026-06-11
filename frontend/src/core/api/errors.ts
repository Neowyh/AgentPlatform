/**
 * Extract a human-readable error message from a failed API response.
 *
 * Handles FastAPI validation error arrays (`detail: [{msg, loc}]`)
 * and simple `detail: string` responses.
 */
export async function extractError(
  res: Response,
  action: string,
): Promise<never> {
  let detail: string | undefined;
  try {
    const body = (await res.json()) as {
      detail?: string | Array<{ msg?: string; loc?: string[] }>;
    };
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors: array of {msg, loc, type}
      detail = body.detail
        .map(
          (e) =>
            (e.loc ? `${e.loc.join(".")}: ` : "") +
            (e.msg ?? JSON.stringify(e)),
        )
        .join("; ");
    } else {
      detail = body.detail;
    }
  } catch {
    // Response body not JSON
  }
  throw new Error(detail ?? `${action}: ${res.statusText}`);
}
