/**
 * Workflow run error formatting.
 *
 * The backend emits structured run/node failures as payloads with
 * `code`, `summary`, and `error` (raw detail). `run.error` persists the
 * short summary; the code label keeps list/alert views readable while
 * the detail stays available for expandable views.
 */

/** Chinese label for a backend workflow error code. */
export const WORKFLOW_ERROR_CODE_LABELS: Record<string, string> = {
  invalid_file_roots: "文件访问路径未注册",
  missing_input_roots: "输入路径缺失或为空",
  agent_failed: "智能体执行失败",
  tool_failed: "工具执行失败",
  schema_violation: "输出未通过 Schema 校验",
  precondition_failed: "前置条件不满足",
  node_timeout: "节点执行超时",
  iteration_limit: "循环次数达到上限",
  artifacts_missing: "输出文件缺失",
  event_limit: "事件数量达到上限",
  max_attempts: "重试次数达到上限",
  unknown: "执行失败",
};

export function workflowErrorCodeLabel(
  code: string | null | undefined,
): string {
  if (!code) return "";
  return WORKFLOW_ERROR_CODE_LABELS[code] ?? code;
}

/**
 * Format an error message stored on a run/step with its error code.
 *
 * The summary already reads well on its own; the code label is prepended
 * only when a code is known so contexts without codes stay unchanged.
 */
export function formatWorkflowRunError(
  message: string | null | undefined,
  code?: string | null,
): string {
  if (!message) return "工作流执行失败";
  const label = workflowErrorCodeLabel(code);
  if (!label || code === "unknown") return message;
  return message.startsWith(label) ? message : `${label}：${message}`;
}
