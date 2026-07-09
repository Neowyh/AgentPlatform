/** Raw detail shape from a FastAPI error response. */
export type ErrorDetail =
  | string
  | { code?: string; message?: string }
  | Array<{ msg?: string; loc?: string[] }>
  | undefined;

/**
 * Parse the raw error detail from a failed API response.
 *
 * Returns the parsed body and its `detail` field without formatting.
 * Useful for callers that need to inspect the detail before deciding
 * how to handle it (e.g. checking for a specific error code).
 *
 * Returns `undefined` if the body cannot be parsed.
 */
export async function parseErrorDetail(res: Response): Promise<
  | {
      body: { detail?: ErrorDetail };
      detail: ErrorDetail;
    }
  | undefined
> {
  try {
    const body = (await res.json()) as { detail?: ErrorDetail };
    return { body, detail: body.detail };
  } catch {
    return undefined;
  }
}

/**
 * Format a human-readable error message from a pre-parsed error detail.
 */
export function formatDetail(
  detail: ErrorDetail,
  action: string,
  statusText: string,
): string {
  if (Array.isArray(detail)) {
    return detail
      .map(
        (e) =>
          (e.loc ? `${e.loc.join(".")}: ` : "") + (e.msg ?? JSON.stringify(e)),
      )
      .join("; ");
  }
  if (typeof detail === "object" && detail !== null) {
    return (detail as { message?: string }).message ?? JSON.stringify(detail);
  }
  if (typeof detail === "string") {
    return detail;
  }
  return `${action}: ${statusText}`;
}

/**
 * Format a human-readable error message from a failed API response.
 *
 * Handles:
 * - FastAPI validation error arrays (`detail: [{msg, loc}]`)
 * - Simple `detail: string` responses
 * - Structured error objects (`detail: {code, message}`)
 * - Custom `{success, error: {message}}` format (fallback)
 *
 * Returns the message string without throwing — useful for callers
 * that need the message for non-exception flows (e.g. returning
 * `{success: false, message}`).
 */
export async function formatErrorMessage(
  res: Response,
  action: string,
): Promise<string> {
  const parsed = await parseErrorDetail(res);
  if (!parsed) return `${action}: ${res.statusText}`;
  if (parsed.detail !== undefined)
    return formatDetail(parsed.detail, action, res.statusText);
  // Fallback: read from custom `{success, error: {message}}` format
  const body = parsed.body as { error?: { message?: string } };
  if (body.error?.message) return body.error.message;
  return `${action}: ${res.statusText}`;
}

/**
 * Extract a human-readable error message from a failed API response
 * and throw it as an Error.
 *
 * Handles FastAPI validation error arrays (`detail: [{msg, loc}]`)
 * and simple `detail: string` responses.
 */
export async function extractError(
  res: Response,
  action: string,
): Promise<never> {
  const message = await formatErrorMessage(res, action);
  throw new Error(message);
}
