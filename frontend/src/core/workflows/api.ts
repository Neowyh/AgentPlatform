import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  RunStatus,
  WorkflowRunHistory,
  WorkflowDetail,
  WorkflowRunResult,
  WorkflowSummary,
} from "./types";

export async function listWorkflows(): Promise<{
  workflows: WorkflowSummary[];
  total: number;
}> {
  const res = await fetch(`${getBackendBaseURL()}/api/workflows`);
  if (!res.ok) return extractError(res, "Failed to load workflows");
  return res.json() as Promise<{ workflows: WorkflowSummary[]; total: number }>;
}

export async function getWorkflow(name: string): Promise<WorkflowDetail> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}`,
  );
  if (!res.ok) return extractError(res, `Workflow '${name}' not found`);
  return res.json() as Promise<WorkflowDetail>;
}

export async function createWorkflow(
  data: Record<string, unknown>,
): Promise<WorkflowSummary> {
  const res = await fetch(`${getBackendBaseURL()}/api/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to create workflow");
  return res.json() as Promise<WorkflowSummary>;
}

export async function updateWorkflow(
  name: string,
  data: Record<string, unknown>,
): Promise<WorkflowSummary> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) return extractError(res, "Failed to update workflow");
  return res.json() as Promise<WorkflowSummary>;
}

export async function deleteWorkflow(name: string): Promise<void> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}`,
    { method: "DELETE" },
  );
  if (!res.ok) return extractError(res, "Failed to delete workflow");
}

export async function runWorkflow(
  name: string,
  inputs: Record<string, unknown>,
): Promise<WorkflowRunResult> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs }),
    },
  );
  if (!res.ok) return extractError(res, "Failed to run workflow");
  return res.json() as Promise<WorkflowRunResult>;
}

export async function getRunStatus(
  name: string,
  runId: string,
): Promise<RunStatus> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}`,
  );
  if (!res.ok) return extractError(res, "Failed to get run status");
  return res.json() as Promise<RunStatus>;
}

export async function listWorkflowRuns(
  name: string,
): Promise<WorkflowRunHistory> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/runs`,
  );
  if (!res.ok) return extractError(res, "Failed to load workflow runs");
  return res.json() as Promise<WorkflowRunHistory>;
}

export function workflowEventsUrl(
  name: string,
  runId: string,
  afterSeq = 0,
): string {
  const params = new URLSearchParams({ after_seq: String(afterSeq) });
  return `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}/events?${params}`;
}

export async function submitWorkflowCommand(
  name: string,
  runId: string,
  command: {
    command_id: string;
    type: "resume" | "cancel";
    payload?: Record<string, unknown>;
  },
): Promise<{ command_id: string; run_id: string; accepted: boolean }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}/commands`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
    },
  );
  if (!res.ok) return extractError(res, "Failed to submit workflow command");
  return res.json() as Promise<{
    command_id: string;
    run_id: string;
    accepted: boolean;
  }>;
}

export async function toggleWorkflowFavorite(
  name: string,
): Promise<{ success: boolean; is_favorited: boolean }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/favorite`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!res.ok) return extractError(res, "Failed to toggle favorite");
  return res.json() as Promise<{ success: boolean; is_favorited: boolean }>;
}
