/** Raw detail shape from a FastAPI error response. */
export interface VisibilityClosureViolation {
  source?: {
    slug?: string;
    display_name?: string;
    type?: string;
  };
  target?: {
    slug?: string;
    display_name?: string;
    type?: string;
    visibility?: string;
  };
  required_visibility?: string;
}

export type ErrorDetail =
  | string
  | {
      code?: string;
      message?: string;
      violations?: VisibilityClosureViolation[];
    }
  | Array<{ msg?: string; loc?: string[] }>
  | undefined;

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  tool: "工具",
  skill: "Skill",
  workflow: "工作流",
  agent: "智能体",
};

const VISIBILITY_LABELS: Record<string, string> = {
  private: "私有",
  department: "部门",
  public: "公开",
};

/**
 * Format a visibility closure violation payload into a localized,
 * actionable message.
 */
export function formatVisibilityClosureViolations(detail: {
  message?: string;
  violations?: VisibilityClosureViolation[];
}): string {
  const violations = detail.violations ?? [];
  const summary =
    detail.message ?? "可见性闭包校验失败：公开资源只能依赖公开资源。";
  const lines = violations.map((violation) => {
    const target = violation.target;
    const label = target?.display_name ?? target?.slug ?? "未知资源";
    const type = target?.type
      ? (RESOURCE_TYPE_LABELS[target.type] ?? target.type)
      : "";
    const visibility = target?.visibility
      ? (VISIBILITY_LABELS[target.visibility] ?? target.visibility)
      : "未知";
    return `- ${type}「${label}」当前可见性：${visibility}`;
  });
  const guidance =
    violations.length > 1
      ? "请先将这些依赖提升为公开，或移除该依赖后重试"
      : "请先将该依赖提升为公开，或移除该依赖后重试";
  return lines.length > 0
    ? `${summary}\n${guidance}：\n${lines.join("\n")}`
    : summary;
}

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
    const structured = detail as {
      code?: string;
      message?: string;
      violations?: VisibilityClosureViolation[];
    };
    if (
      structured.code === "visibility_closure_violation" &&
      Array.isArray(structured.violations)
    ) {
      return formatVisibilityClosureViolations(structured);
    }
    return structured.message ?? JSON.stringify(detail);
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
