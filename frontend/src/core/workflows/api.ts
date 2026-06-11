import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  ReviewData,
  RunStatus,
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
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(
      err.detail ?? `Failed to create workflow: ${res.statusText}`,
    );
  }
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
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(
      err.detail ?? `Failed to update workflow: ${res.statusText}`,
    );
  }
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
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to run workflow: ${res.statusText}`);
  }
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

export async function submitReview(
  name: string,
  runId: string,
  data: ReviewData,
): Promise<{ success: boolean; run_id: string }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approved: data.approved,
        data: { comment: data.comment },
      }),
    },
  );
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to submit review: ${res.statusText}`);
  }
  return res.json() as Promise<{ success: boolean; run_id: string }>;
}
