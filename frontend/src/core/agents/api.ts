import {
  extractError,
  formatDetail,
  parseErrorDetail,
  type ErrorDetail,
} from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Agent, CreateAgentRequest, UpdateAgentRequest } from "./types";

const BACKEND_UNAVAILABLE_STATUSES = new Set([502, 503, 504]);
const RESOURCE_UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

interface CanonicalAgentResource {
  id: string;
  type: "agent";
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

function fromCanonicalResource(resource: CanonicalAgentResource): Agent {
  return {
    resource_id: resource.id,
    slug: resource.slug,
    draft_revision: resource.draft_revision,
    name: resource.display_name,
    description: resource.display_name,
    model: null,
    tool_groups: null,
    skills: null,
    read_only: !resource.can_modify,
    visibility: resource.visibility,
    owner_id: resource.owner_id,
    department_id: resource.scope_department_id,
    is_favorited: resource.is_favorited,
  };
}

function fromCanonicalPublished(payload: {
  resource: CanonicalAgentResource;
  content: {
    config: {
      description?: string;
      model?: string | null;
      tool_groups?: string[] | null;
      skills?: string[] | null;
    };
    soul: string;
  };
}): Agent {
  const agent = fromCanonicalResource(payload.resource);
  return {
    ...agent,
    description: payload.content.config.description ?? "",
    model: payload.content.config.model ?? null,
    tool_groups: payload.content.config.tool_groups ?? null,
    skills: payload.content.config.skills ?? null,
    soul: payload.content.soul,
  };
}

async function getCanonicalAgent(resourceId: string): Promise<Agent> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resourceId)}/published`,
  );
  if (!res.ok) await extractError(res, `Agent '${resourceId}' not found`);
  return fromCanonicalPublished(
    (await res.json()) as Parameters<typeof fromCanonicalPublished>[0],
  );
}

export class AgentNameCheckError extends Error {
  constructor(
    message: string,
    public readonly reason: "backend_unreachable" | "request_failed",
  ) {
    super(message);
    this.name = "AgentNameCheckError";
  }
}

export class AgentsApiDisabledError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AgentsApiDisabledError";
  }
}

/**
 * Check if the error detail indicates the agents API is disabled.
 * Handles both structured format ({code: "AGENTS_API_DISABLED"})
 * and legacy string format (containing "agents_api.enabled").
 */
function isAgentsApiDisabledDetail(detail: ErrorDetail): boolean {
  if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
    return (detail as { code?: string }).code === "AGENTS_API_DISABLED";
  }
  return typeof detail === "string" && detail.includes("agents_api.enabled");
}

export async function listAgents(): Promise<Agent[]> {
  const canonicalRes = await fetch(
    `${getBackendBaseURL()}/api/resources?type=agent&limit=200`,
  );
  if (!canonicalRes.ok)
    await extractError(canonicalRes, "Failed to load canonical agents");
  const canonical = (await canonicalRes.json()) as {
    items: CanonicalAgentResource[];
    mode?: "legacy" | "dual" | "canonical";
  };
  if (canonical.mode === "canonical") {
    return canonical.items.map(fromCanonicalResource);
  }
  const res = await fetch(`${getBackendBaseURL()}/api/agents`);
  if (!res.ok) await extractError(res, "Failed to load agents");
  const data = (await res.json()) as { agents: Agent[] };
  if (canonical.mode === "legacy") return data.agents;
  const canonicalKeys = new Set(
    canonical.items.map((item) => `${item.slug}\u0000${item.owner_id}`),
  );
  const bundledSlugs = new Set(
    canonical.items
      .filter((item) => item.system_owned)
      .map((item) => item.slug),
  );
  const legacy = data.agents.filter((item) => {
    const slug = item.slug ?? item.name;
    return (
      !bundledSlugs.has(slug) &&
      !canonicalKeys.has(`${slug}\u0000${item.owner_id ?? ""}`)
    );
  });
  return [...legacy, ...canonical.items.map(fromCanonicalResource)];
}

export async function getAgent(identifier: string): Promise<Agent> {
  if (RESOURCE_UUID_PATTERN.test(identifier)) {
    return getCanonicalAgent(identifier);
  }
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${identifier}`);
  if (!res.ok && (res.status === 404 || res.status === 410)) {
    const aliasRes = await fetch(
      `${getBackendBaseURL()}/api/resources/aliases/agent/${encodeURIComponent(identifier)}`,
    );
    if (!aliasRes.ok)
      await extractError(aliasRes, `Agent '${identifier}' not found`);
    const resource = (await aliasRes.json()) as CanonicalAgentResource;
    return getCanonicalAgent(resource.id);
  }
  if (!res.ok) await extractError(res, `Agent '${identifier}' not found`);
  return res.json() as Promise<Agent>;
}

export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const createRes = await fetch(`${getBackendBaseURL()}/api/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "agent",
      slug: request.name,
      display_name: request.name,
      storage_kind: "filesystem",
    }),
  });
  if (!createRes.ok) {
    await extractError(createRes, "Failed to create Agent resource");
  }
  const resource = (await createRes.json()) as CanonicalAgentResource;
  try {
    const config = {
      description: request.description,
      model: request.model,
      tool_groups: request.tool_groups,
      skills: request.skills,
    };
    const draftRes = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/agent-draft`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          soul: request.soul ?? "",
          expected_revision: 0,
        }),
      },
    );
    if (!draftRes.ok)
      await extractError(draftRes, "Failed to save Agent draft");
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
      await extractError(publishRes, "Failed to publish Agent");
    await publishRes.json();
    if (request.visibility && request.visibility !== "private") {
      const visibilityRes = await fetch(
        `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/visibility-applications`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_visibility: request.visibility,
            reason: "Requested during Agent creation",
          }),
        },
      );
      if (!visibilityRes.ok) {
        await extractError(visibilityRes, "Failed to request Agent visibility");
      }
    }
    return fromCanonicalResource({ ...resource, latest_version: 1 });
  } catch (error) {
    await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(resource.id)}/archive`,
      { method: "POST" },
    ).catch(() => undefined);
    throw error;
  }
}

export async function updateAgent(
  name: string,
  request: UpdateAgentRequest,
): Promise<Agent | void> {
  if (RESOURCE_UUID_PATTERN.test(name)) {
    const config = {
      description: request.description,
      model: request.model,
      tool_groups: request.tool_groups,
      skills: request.skills,
    };
    const draftRes = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/agent-draft`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          soul: request.soul ?? "",
          expected_revision: request.draft_revision,
        }),
      },
    );
    if (!draftRes.ok)
      await extractError(draftRes, "Failed to save Agent draft");
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
      await extractError(publishRes, "Failed to publish Agent");
    await publishRes.json();
    return;
  }
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) await extractError(res, "Failed to update agent");
  return res.json() as Promise<Agent>;
}

export async function deleteAgent(name: string): Promise<void> {
  if (RESOURCE_UUID_PATTERN.test(name)) {
    const res = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/archive`,
      { method: "POST" },
    );
    if (!res.ok) await extractError(res, "Failed to archive Agent");
    return;
  }
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "DELETE",
  });
  if (!res.ok) await extractError(res, "Failed to delete agent");
}

export async function checkAgentName(
  name: string,
): Promise<{ available: boolean; name: string }> {
  let res: Response;
  try {
    res = await fetch(
      `${getBackendBaseURL()}/api/agents/check?name=${encodeURIComponent(name)}`,
    );
  } catch {
    throw new AgentNameCheckError(
      "Could not reach the iDeer backend.",
      "backend_unreachable",
    );
  }

  if (res.status === 410) {
    return checkCanonicalAgentName(name);
  }

  if (!res.ok) {
    const parsed = await parseErrorDetail(res);
    const detail = parsed?.detail;
    if (isAgentsApiDisabledDetail(detail)) {
      throw new AgentsApiDisabledError(
        formatDetail(detail, "Failed to check agent name", res.statusText),
      );
    }
    if (BACKEND_UNAVAILABLE_STATUSES.has(res.status)) {
      throw new AgentNameCheckError(
        "Could not reach the iDeer backend.",
        "backend_unreachable",
      );
    }
    throw new AgentNameCheckError(
      formatDetail(detail, "Failed to check agent name", res.statusText),
      "request_failed",
    );
  }
  return res.json() as Promise<{ available: boolean; name: string }>;
}

async function checkCanonicalAgentName(
  name: string,
): Promise<{ available: boolean; name: string }> {
  let aliasRes: Response;
  try {
    aliasRes = await fetch(
      `${getBackendBaseURL()}/api/resources/aliases/agent/${encodeURIComponent(name)}`,
    );
  } catch {
    throw new AgentNameCheckError(
      "Could not reach the iDeer backend.",
      "backend_unreachable",
    );
  }
  if (aliasRes.ok) return { available: false, name };
  if (aliasRes.status === 404) return { available: true, name };
  const detail = (await parseErrorDetail(aliasRes))?.detail;
  throw new AgentNameCheckError(
    formatDetail(detail, "Failed to check agent name", aliasRes.statusText),
    "request_failed",
  );
}

// ── Export / Import ──────────────────────────────────────────────

export async function exportAgent(name: string): Promise<Blob> {
  const canonical = RESOURCE_UUID_PATTERN.test(name);
  const url = canonical
    ? `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/export`
    : `${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/export`;
  const res = await fetch(url, { method: canonical ? "GET" : "POST" });
  if (!res.ok) await extractError(res, "Failed to export agent");
  return res.blob();
}

export async function importAgent(file: File): Promise<Agent> {
  if (file.name.toLowerCase().endsWith(".zip")) {
    const form = new FormData();
    form.append("archive", file);
    const response = await fetch(
      `${getBackendBaseURL()}/api/resources/import/agent`,
      { method: "POST", body: form },
    );
    if (!response.ok) await extractError(response, "Failed to import agent");
    const resource = (await response.json()) as CanonicalAgentResource;
    return getCanonicalAgent(resource.id);
  }
  // Read file content and parse as JSON
  // Backend expects AgentImportRequest JSON: {name, config, soul, visibility}
  const fileContent = await file.text();
  let importData: Record<string, unknown>;
  try {
    importData = JSON.parse(fileContent);
  } catch {
    throw new Error("Invalid import file: must be valid JSON");
  }

  const res = await fetch(`${getBackendBaseURL()}/api/agents/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(importData),
  });
  if (res.status === 410) {
    const config = (importData.config ?? {}) as Record<string, unknown>;
    return createAgent({
      name: importData.name as string,
      description:
        typeof config.description === "string" ? config.description : undefined,
      model: typeof config.model === "string" ? config.model : undefined,
      tool_groups: Array.isArray(config.tool_groups)
        ? (config.tool_groups as string[])
        : undefined,
      skills: Array.isArray(config.skills)
        ? (config.skills as string[])
        : undefined,
      soul: typeof importData.soul === "string" ? importData.soul : undefined,
      visibility:
        typeof importData.visibility === "string"
          ? importData.visibility
          : undefined,
    });
  }
  if (!res.ok) {
    const parsed = await parseErrorDetail(res);
    const detail = parsed?.detail;
    if (isAgentsApiDisabledDetail(detail)) {
      throw new AgentsApiDisabledError(
        formatDetail(detail, "Failed to import agent", res.statusText),
      );
    }
    throw new Error(
      formatDetail(detail, "Failed to import agent", res.statusText),
    );
  }
  return res.json() as Promise<Agent>;
}

export async function toggleAgentFavorite(
  name: string,
  isFavorited = false,
): Promise<{ success: boolean; is_favorited: boolean }> {
  if (RESOURCE_UUID_PATTERN.test(name)) {
    const res = await fetch(
      `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/favorite`,
      { method: isFavorited ? "DELETE" : "POST" },
    );
    if (!res.ok) await extractError(res, "Failed to update favorite");
    return { success: true, is_favorited: !isFavorited };
  }
  const res = await fetch(
    `${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/favorite`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!res.ok) await extractError(res, "Failed to toggle favorite");
  return res.json() as Promise<{ success: boolean; is_favorited: boolean }>;
}
