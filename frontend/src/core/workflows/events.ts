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

function reconcileTerminalSteps(
  steps: RunStatus["steps"],
  terminal: RunStatus["status"],
): RunStatus["steps"] {
  if (terminal !== "cancelled" && terminal !== "failed") return steps;
  if (!steps) return steps;
  let changed = false;
  const next: NonNullable<RunStatus["steps"]> = {};
  for (const [nodeId, step] of Object.entries(steps)) {
    if (step.status === "running") {
      changed = true;
      next[nodeId] = { ...step, status: "cancelled" };
    } else {
      next[nodeId] = step;
    }
  }
  return changed ? next : steps;
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
    const message = textValue(event.payload.message);
    if (!message) return next;
    return {
      ...next,
      action_progress: {
        ...next.action_progress,
        [nodeId]: [...(next.action_progress?.[nodeId] ?? []), message],
      },
    };
  }
  if (event.type === "node_started" && nodeId) {
    return {
      ...next,
      status: "running",
      current_step: nodeId,
      steps: updatedStep(next, nodeId, {
        status: "running",
        started_at: textValue(event.payload.started_at) || null,
      }),
    };
  }
  if (event.type === "node_completed" && nodeId) {
    return {
      ...next,
      current_step: null,
      steps: updatedStep(next, nodeId, {
        status: "completed",
        output: event.payload.result,
        finished_at: textValue(event.payload.finished_at) || null,
      }),
    };
  }
  if (event.type === "node_failed" && nodeId) {
    return {
      ...next,
      current_step: null,
      error:
        textValue(event.payload.summary) ||
        textValue(event.payload.error) ||
        next.error,
      error_code: textValue(event.payload.code) || next.error_code,
      steps: updatedStep(next, nodeId, {
        status: "failed",
        error:
          textValue(event.payload.summary) ||
          textValue(event.payload.error) ||
          null,
        error_code: textValue(event.payload.code) || null,
        finished_at: textValue(event.payload.finished_at) || null,
      }),
    };
  }
  if (event.type === "node_skipped" && nodeId) {
    return {
      ...next,
      current_step: null,
      steps: updatedStep(next, nodeId, {
        status: "skipped",
        error: null,
        finished_at: textValue(event.payload.finished_at) || null,
      }),
    };
  }
  if (event.type === "edge_selected") {
    const from = textValue(event.payload.from);
    const to = textValue(event.payload.to);
    if (!from || !to) return next;
    const alreadySelected = (next.selected_edges ?? []).some(
      (edge) => edge.from === from && edge.to === to,
    );
    if (alreadySelected) return next;
    return {
      ...next,
      selected_edges: [...(next.selected_edges ?? []), { from, to }],
    };
  }
  const terminal = terminalStatus[event.type];
  if (terminal)
    return {
      ...next,
      status: terminal,
      error:
        event.type === "run_failed"
          ? textValue(event.payload.summary) ||
            textValue(event.payload.error) ||
            "Workflow failed"
          : next.error,
      error_code:
        event.type === "run_failed"
          ? textValue(event.payload.code) || next.error_code
          : next.error_code,
      steps: reconcileTerminalSteps(next.steps, terminal),
    };
  if (event.type === "interrupted") return { ...next, status: "paused" };
  if (event.type === "resumed") return { ...next, status: "running" };
  return next;
}
