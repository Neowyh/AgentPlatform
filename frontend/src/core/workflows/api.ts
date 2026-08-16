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

const RESOURCE_UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

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

function isCanonicalIdentity(value: string): boolean {
  return RESOURCE_UUID_PATTERN.test(value);
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
  const canonicalRes = await fetch(
    `${getBackendBaseURL()}/api/resources?type=workflow&limit=200`,
  );
  if (!canonicalRes.ok)
    return extractError(canonicalRes, "Failed to load canonical workflows");
  const canonical = (await canonicalRes.json()) as {
    items: CanonicalWorkflowResource[];
    total: number;
    mode?: "legacy" | "dual" | "canonical";
  };
  if (canonical.mode === "canonical") {
    return {
      workflows: canonical.items.map(fromCanonicalResource),
      total: canonical.total,
    };
  }
  const res = await fetch(`${getBackendBaseURL()}/api/workflows`);
  if (!res.ok) return extractError(res, "Failed to load workflows");
  const legacy = (await res.json()) as {
    workflows: WorkflowSummary[];
    total: number;
  };
  if (canonical.mode === "legacy") return legacy;
  const canonicalKeys = new Set(
    canonical.items.map((item) => `${item.slug}\u0000${item.owner_id}`),
  );
  const bundledSlugs = new Set(
    canonical.items
      .filter((item) => item.system_owned)
      .map((item) => item.slug),
  );
  const legacyWorkflows = legacy.workflows.filter((item) => {
    const slug = item.slug ?? item.name;
    return (
      !bundledSlugs.has(slug) &&
      !canonicalKeys.has(`${slug}\u0000${item.owner_id ?? ""}`)
    );
  });
  return {
    workflows: [
      ...legacyWorkflows,
      ...canonical.items.map(fromCanonicalResource),
    ],
    total: legacyWorkflows.length + canonical.total,
  };
}

export async function getWorkflow(name: string): Promise<WorkflowDetail> {
  if (isCanonicalIdentity(name)) {
    return getCanonicalWorkflow(name);
  }
  const res = await fetch(
    `${getBackendBaseURL()}/api/workflows/${encodeURIComponent(name)}`,
  );
  if (!res.ok && (res.status === 404 || res.status === 410)) {
    const aliasRes = await fetch(
      `${getBackendBaseURL()}/api/resources/aliases/workflow/${encodeURIComponent(name)}`,
    );
    if (!aliasRes.ok)
      return extractError(aliasRes, `Workflow '${name}' not found`);
    const resource = (await aliasRes.json()) as CanonicalWorkflowResource;
    return getCanonicalWorkflow(resource.id);
  }
  if (!res.ok) return extractError(res, `Workflow '${name}' not found`);
  return res.json() as Promise<WorkflowDetail>;
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
  if (isCanonicalIdentity(name)) {
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
  if (isCanonicalIdentity(name)) {
    const res = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/archive`,
      { method: "POST" },
    );
    if (!res.ok) return extractError(res, "Failed to archive Workflow");
    return;
  }
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
  const path = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/run`;
  const res = await fetch(`${getBackendBaseURL()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  if (!res.ok) return extractError(res, "Failed to run workflow");
  const result = (await res.json()) as WorkflowRunResult;
  return { ...result, workflow: result.workflow ?? name };
}

export async function getRunStatus(
  name: string,
  runId: string,
): Promise<RunStatus> {
  const path = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs/${encodeURIComponent(runId)}`
    : `/api/workflows/${encodeURIComponent(name)}/runs/${encodeURIComponent(runId)}`;
  const res = await fetch(`${getBackendBaseURL()}${path}`);
  if (!res.ok) return extractError(res, "Failed to get run status");
  return res.json() as Promise<RunStatus>;
}

export async function listWorkflowRuns(
  name: string,
): Promise<WorkflowRunHistory> {
  const path = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/runs`;
  const res = await fetch(`${getBackendBaseURL()}${path}`);
  if (!res.ok) return extractError(res, "Failed to load workflow runs");
  return res.json() as Promise<WorkflowRunHistory>;
}

export async function listRunArtifacts(
  name: string,
  runId: string,
): Promise<{ run_id: string; workflow: string; artifacts: RunArtifact[] }> {
  const base = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/runs`;
  const res = await fetch(
    `${getBackendBaseURL()}${base}/${encodeURIComponent(runId)}/artifacts`,
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
  const base = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/runs`;
  const res = await fetch(
    `${getBackendBaseURL()}${base}/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`,
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
  const base = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/runs`;
  return `${getBackendBaseURL()}${base}/${encodeURIComponent(runId)}/events?${params}`;
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
  const base = isCanonicalIdentity(name)
    ? `/api/resources/${encodeURIComponent(name)}/workflow-runs`
    : `/api/workflows/${encodeURIComponent(name)}/runs`;
  const res = await fetch(
    `${getBackendBaseURL()}${base}/${encodeURIComponent(runId)}/commands`,
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
  if (isCanonicalIdentity(name)) {
    const res = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/favorite`,
      { method: isFavorited ? "DELETE" : "POST" },
    );
    if (!res.ok) return extractError(res, "Failed to update favorite");
    return { success: true, is_favorited: !isFavorited };
  }
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
