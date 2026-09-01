import {
  extractError,
  formatDetail,
  parseErrorDetail,
  type ErrorDetail,
} from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Agent, CreateAgentRequest, UpdateAgentRequest } from "./types";

interface CanonicalAgentResource {
  id: string;
  type: "agent";
  slug: string;
  display_name: string;
  description?: string | null;
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
    description: resource.description ?? resource.display_name,
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

export async function listAgents(): Promise<Agent[]> {
  const items: CanonicalAgentResource[] = [];
  const limit = 200;
  for (let offset = 0; ; offset += limit) {
    const canonicalRes = await fetch(
      `${getBackendBaseURL()}/api/resources?type=agent&limit=${limit}${offset ? `&offset=${offset}` : ""}`,
    );
    if (!canonicalRes.ok)
      await extractError(canonicalRes, "Failed to load canonical agents");
    const canonical = (await canonicalRes.json()) as {
      items: CanonicalAgentResource[];
      total: number;
    };
    items.push(...canonical.items);
    if (items.length >= canonical.total || canonical.items.length === 0) break;
  }
  return items.map(fromCanonicalResource);
}

export async function getAgent(identifier: string): Promise<Agent> {
  return getCanonicalAgent(identifier);
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
  if (!draftRes.ok) await extractError(draftRes, "Failed to save Agent draft");
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
  if (!publishRes.ok) await extractError(publishRes, "Failed to publish Agent");
  await publishRes.json();
  return;
}

export async function deleteAgent(name: string): Promise<void> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/archive`,
    { method: "POST" },
  );
  if (!res.ok) await extractError(res, "Failed to archive Agent");
}

export async function checkAgentName(
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
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/export`,
    { method: "GET" },
  );
  if (!res.ok) await extractError(res, "Failed to export agent");
  return res.blob();
}

export async function importAgent(file: File): Promise<Agent> {
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

export async function toggleAgentFavorite(
  name: string,
  isFavorited = false,
): Promise<{ success: boolean; is_favorited: boolean }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(name)}/favorite`,
    { method: isFavorited ? "DELETE" : "POST" },
  );
  if (!res.ok) await extractError(res, "Failed to update favorite");
  return { success: true, is_favorited: !isFavorited };
}
