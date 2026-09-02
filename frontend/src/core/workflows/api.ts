import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  RunArtifact,
  RunStatus,
  WorkflowRunHistory,
  WorkflowDetail,
  WorkflowRunResult,
  WorkflowSummary,
} from "./types";

interface CanonicalWorkflowResource {
  id: string;
  type: "workflow";
  slug: string;
  display_name: string;
  owner_id: string;
  visibility: string;
  scope_department_id: string | null;
  latest_version: number;
  draft_revision: number;
  system_owned: boolean;
  can_modify: boolean;
  is_favorited?: boolean;
}

interface CanonicalWorkflowDefinition {
  schema_version: 2;
  name: string;
  description?: string;
  inputs?: WorkflowDetail["inputs"];
  state?: WorkflowDetail["state"];
  entrypoint: string;
  nodes: WorkflowDetail["nodes"];
  edges: WorkflowDetail["edges"];
}

function fromCanonicalResource(
  resource: CanonicalWorkflowResource,
): WorkflowSummary {
  return {
    resource_id: resource.id,
    slug: resource.slug,
    read_only: !resource.can_modify,
    draft_revision: resource.draft_revision,
    name: resource.display_name,
    description: resource.display_name,
    version: String(resource.latest_version),
    steps_count: 0,
    inputs: {},
    visibility: resource.visibility,
    owner_id: resource.owner_id,
    department_id: resource.scope_department_id,
    is_favorited: resource.is_favorited,
  };
}

function fromCanonicalPublished(payload: {
  resource: CanonicalWorkflowResource;
  version: { version: number };
  content: CanonicalWorkflowDefinition;
  yaml_content?: string;
}): WorkflowDetail {
  const summary = fromCanonicalResource(payload.resource);
  const content = payload.content;
  return {
    ...summary,
    description: content.description ?? "",
    version: String(payload.version.version),
    steps_count: content.nodes.length,
    inputs: content.inputs ?? {},
    yaml_content: payload.yaml_content ?? JSON.stringify(content, null, 2),
    schema_version: 2,
    state: content.state ?? {},
    entrypoint: content.entrypoint,
    nodes: content.nodes,
    steps: content.nodes,
    edges: content.edges,
  };
}

async function getCanonicalWorkflow(
  resourceId: string,
): Promise<WorkflowDetail> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/published`,
  );
  if (!res.ok) return extractError(res, `Workflow '${resourceId}' not found`);
  return fromCanonicalPublished(
    (await res.json()) as Parameters<typeof fromCanonicalPublished>[0],
  );
}

function workflowNameFromYaml(content: string): string {
  const match = /^name:\s*(?:["']([^"']+)["']|([^#\n]+))\s*$/m.exec(content);
  const name = (match?.[1] ?? match?.[2] ?? "").trim();
  if (!name) throw new Error("Workflow YAML must include a top-level name");
  return name;
}

export async function listWorkflows(): Promise<{
  workflows: WorkflowSummary[];
  total: number;
}> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources?type=workflow&limit=200`,
  );
  if (!res.ok) return extractError(res, "Failed to load workflows");
  const canonical = (await res.json()) as {
    items: CanonicalWorkflowResource[];
    total: number;
  };
  return {
    workflows: canonical.items.map(fromCanonicalResource),
    total: canonical.total,
  };
}

export async function getWorkflow(name: string): Promise<WorkflowDetail> {
  return getCanonicalWorkflow(name);
}

export async function createWorkflow(
  data: Record<string, unknown>,
): Promise<WorkflowSummary> {
  const yamlContent = data.yaml_content;
  if (typeof yamlContent !== "string") {
    throw new Error("Workflow YAML content is required");
  }
  const name = workflowNameFromYaml(yamlContent);
  const createRes = await fetch(`${getBackendBaseURL()}/api/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "workflow",
      slug: name,
      display_name: name,
      storage_kind: "database",
    }),
  });
  if (!createRes.ok)
    return extractError(createRes, "Failed to create Workflow resource");
  const resource = (await createRes.json()) as CanonicalWorkflowResource;
  try {
    const draftRes = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/workflow-draft`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: yamlContent, expected_revision: 0 }),
      },
    );
    if (!draftRes.ok)
      return extractError(draftRes, "Failed to save Workflow draft");
    const draft = (await draftRes.json()) as { revision: number };
    const publishRes = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/publish`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_draft_revision: draft.revision,
          scan_result: {},
        }),
      },
    );
    if (!publishRes.ok)
      return extractError(publishRes, "Failed to publish Workflow");
    await publishRes.json();
    return fromCanonicalResource({ ...resource, latest_version: 1 });
  } catch (error) {
    await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/archive`,
      { method: "POST" },
    ).catch(() => undefined);
    throw error;
  }
}

export async function updateWorkflow(
  name: string,
  data: Record<string, unknown>,
): Promise<WorkflowSummary | void> {
  const draftRes = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-draft`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: data.yaml_content,
        expected_revision: data.draft_revision,
      }),
    },
  );
  if (!draftRes.ok)
    return extractError(draftRes, "Failed to save Workflow draft");
  const draft = (await draftRes.json()) as { revision: number };
  const publishRes = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_draft_revision: draft.revision,
        scan_result: {},
      }),
    },
  );
  if (!publishRes.ok)
    return extractError(publishRes, "Failed to publish Workflow");
  await publishRes.json();
  return;
}

export async function deleteWorkflow(name: string): Promise<void> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/archive`,
    { method: "POST" },
  );
  if (!res.ok) return extractError(res, "Failed to archive Workflow");
}

export async function runWorkflow(
  name: string,
  inputs: Record<string, unknown>,
  modelName?: string,
): Promise<WorkflowRunResult> {
  const path = `/api/resources/${encodeURIComponent(name)}/workflow-runs`;
  const res = await fetch(`${getBackendBaseURL()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inputs,
      ...(modelName ? { model_name: modelName } : {}),
    }),
  });
  if (!res.ok) return extractError(res, "Failed to run workflow");
  const result = (await res.json()) as WorkflowRunResult;
  return { ...result, workflow: result.workflow ?? name };
}

export async function runWorkflowWithFiles(
  name: string,
  inputs: Record<string, unknown>,
  files: File[],
  modelName?: string,
): Promise<WorkflowRunResult> {
  const body = new FormData();
  body.set("inputs", JSON.stringify(inputs));
  if (modelName) body.set("model_name", modelName);
  for (const file of files) body.append("files", file);
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/with-files`,
    { method: "POST", body },
  );
  if (!res.ok) return extractError(res, "Failed to run workflow with files");
  const result = (await res.json()) as WorkflowRunResult;
  return { ...result, workflow: result.workflow ?? name };
}

export async function getRunStatus(
  name: string,
  runId: string,
): Promise<RunStatus> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}`,
  );
  if (!res.ok) return extractError(res, "Failed to get run status");
  return res.json() as Promise<RunStatus>;
}

export async function listWorkflowRuns(
  name: string,
): Promise<WorkflowRunHistory> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs`,
  );
  if (!res.ok) return extractError(res, "Failed to load workflow runs");
  return res.json() as Promise<WorkflowRunHistory>;
}

export async function listRunArtifacts(
  name: string,
  runId: string,
): Promise<{ run_id: string; workflow: string; artifacts: RunArtifact[] }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/artifacts`,
  );
  if (!res.ok) return extractError(res, "Failed to load run artifacts");
  return res.json() as Promise<{
    run_id: string;
    workflow: string;
    artifacts: RunArtifact[];
  }>;
}

export async function getRunArtifactContent(
  name: string,
  runId: string,
  path: string,
): Promise<string> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`,
  );
  if (!res.ok) return extractError(res, "Failed to load artifact content");
  return res.text();
}

export function workflowEventsUrl(
  name: string,
  runId: string,
  afterSeq = 0,
): string {
  const params = new URLSearchParams({ after_seq: String(afterSeq) });
  return `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/events?${params}`;
}

export function workflowRunArtifactDownloadUrl(
  name: string,
  runId: string,
  path: string,
): string {
  return `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`;
}

export function workflowRunRecordDownloadUrl(
  name: string,
  runId: string,
  format: "jsonl" | "md",
): string {
  return `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/record?format=${format}`;
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
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}/commands`,
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
  isFavorited = false,
): Promise<{ success: boolean; is_favorited: boolean }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/favorite`,
    { method: isFavorited ? "DELETE" : "POST" },
  );
  if (!res.ok) return extractError(res, "Failed to update favorite");
  return { success: true, is_favorited: !isFavorited };
}
