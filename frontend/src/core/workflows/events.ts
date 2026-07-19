import type { RunStatus, WorkflowEvent } from "./types";

const terminalStatus: Record<string, RunStatus["status"]> = {
  run_completed: "completed",
  run_failed: "failed",
  run_cancelled: "cancelled",
};

function textValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function updatedStep(
  status: RunStatus,
  nodeId: string,
  update: Partial<NonNullable<RunStatus["steps"]>[string]>,
) {
  return {
    ...status.steps,
    [nodeId]: {
      status: "pending",
      output: null,
      error: null,
      retries: 0,
      started_at: null,
      finished_at: null,
      ...status.steps?.[nodeId],
      ...update,
    },
  };
}

export function applyWorkflowEvent(
  status: RunStatus,
  event: WorkflowEvent,
): RunStatus {
  const next = { ...status, last_event_seq: event.seq };
  const nodeId =
    typeof event.payload.node_id === "string"
      ? event.payload.node_id
      : undefined;
  if (event.type === "action_token" && nodeId) {
    return {
      ...next,
      action_tokens: {
        ...next.action_tokens,
        [nodeId]: `${next.action_tokens?.[nodeId] ?? ""}${textValue(event.payload.text)}`,
      },
    };
  }
  if (event.type === "action_progress" && nodeId) {
    return {
      ...next,
      action_progress: {
        ...next.action_progress,
        [nodeId]: textValue(event.payload.message),
      },
    };
  }
  if (event.type === "node_started" && nodeId) {
    return {
      ...next,
      status: "running",
      current_step: nodeId,
      steps: updatedStep(next, nodeId, { status: "running" }),
    };
  }
  if (event.type === "node_completed" && nodeId) {
    return {
      ...next,
      current_step: null,
      steps: updatedStep(next, nodeId, {
        status: "completed",
        output: event.payload.result,
      }),
    };
  }
  if (event.type === "node_failed" && nodeId) {
    return {
      ...next,
      current_step: null,
      error: textValue(event.payload.error) || next.error,
      steps: updatedStep(next, nodeId, {
        status: "failed",
        error: textValue(event.payload.error) || null,
      }),
    };
  }
  const terminal = terminalStatus[event.type];
  if (terminal)
    return {
      ...next,
      status: terminal,
      error:
        event.type === "run_failed"
          ? textValue(event.payload.error) || "Workflow failed"
          : next.error,
    };
  if (event.type === "interrupted") return { ...next, status: "paused" };
  if (event.type === "resumed") return { ...next, status: "running" };
  return next;
}
