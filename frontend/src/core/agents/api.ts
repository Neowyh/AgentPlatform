import { extractError, parseErrorDetail } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export { fetchAgentsApiEnabled } from "@/core/features/api";
import type { Agent, CreateAgentRequest, UpdateAgentRequest } from "./types";

const BACKEND_UNAVAILABLE_STATUSES = new Set([502, 503, 504]);
export class AgentNameCheckError extends Error {
  constructor(
    message: string,
    public readonly reason: "backend_unreachable" | "request_failed",
    public readonly detail: string | null = null,
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
type Resource = {
  id: string;
  type: "agent";
  slug: string;
  display_name: string;
  description?: string | null;
  owner_id: string;
  visibility: string;
  scope_department_id: string | null;
  latest_version?: number;
  draft_revision?: number;
  system_owned?: boolean;
  can_modify?: boolean;
  is_favorited?: boolean;
};
function fromResource(resource: Resource, content?: unknown): Agent {
  const payload =
    content && typeof content === "object"
      ? (content as { config?: Record<string, unknown>; soul?: string | null })
      : {};
  const config =
    payload.config ??
    (content && typeof content === "object"
      ? (content as Record<string, unknown>)
      : {});
  return {
    resource_id: resource.id,
    slug: resource.slug,
    name: resource.slug,
    description:
      (config.description as string) ??
      resource.description ??
      resource.display_name,
    model: (config.model as string) ?? null,
    tool_groups: (config.tool_groups as string[]) ?? null,
    skills: (config.skills as string[]) ?? null,
    allowed_subagents: (config.allowed_subagents as string[]) ?? null,
    model_settings: (config.model_settings as Agent["model_settings"]) ?? null,
    thinking_enabled: (config.thinking_enabled as boolean) ?? null,
    reasoning_effort:
      (config.reasoning_effort as Agent["reasoning_effort"]) ?? null,
    soul: payload.soul ?? null,
    read_only: resource.can_modify === false,
    visibility: resource.visibility,
    owner_id: resource.owner_id,
    department_id: resource.scope_department_id,
    latest_version: resource.latest_version,
    draft_revision: resource.draft_revision,
    can_modify: resource.can_modify,
    system_owned: resource.system_owned,
    is_favorited: resource.is_favorited,
  };
}
async function fail(res: Response, message: string): Promise<never> {
  await extractError(res, message);
  throw new Error(message);
}
export async function listAgents(): Promise<Agent[]> {
  const agents: Agent[] = [];
  for (let offset = 0; ; offset += 200) {
    const res = await fetch(
      `${getBackendBaseURL()}/api/resources?type=agent&limit=200${offset ? `&offset=${offset}` : ""}`,
    );
    if (!res.ok) await fail(res, "Failed to load canonical agents");
    const data = (await res.json()) as { items: Resource[]; total: number };
    agents.push(...data.items.map((item) => fromResource(item)));
    if (agents.length >= data.total || data.items.length === 0) return agents;
  }
}
export async function getAgent(id: string): Promise<Agent> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(id)}/published`,
  );
  if (!res.ok) await fail(res, `Agent '${id}' not found`);
  const payload = (await res.json()) as {
    resource: Resource;
    content: unknown;
  };
  return fromResource(payload.resource, payload.content);
}
export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const base = getBackendBaseURL();
  const res = await fetch(`${base}/api/resources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type: "agent",
      slug: request.name,
      display_name: request.name,
      storage_kind: "filesystem",
    }),
  });
  if (!res.ok) await fail(res, "Failed to create Agent resource");
  const resource = (await res.json()) as Resource;
  const draft = await fetch(
    `${base}/api/resources/${resource.id}/agent-draft`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        config: {
          ...request,
          name: undefined,
          knowledge_dependencies: undefined,
        },
        soul: request.soul,
        knowledge_dependencies: request.knowledge_dependencies,
        expected_revision: 0,
      }),
    },
  );
  if (!draft.ok) await fail(draft, "Failed to save Agent draft");
  const draftPayload = (await draft.json()) as { revision: number };
  const publish = await fetch(`${base}/api/resources/${resource.id}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      expected_draft_revision: draftPayload.revision,
      scan_result: {},
    }),
  });
  if (!publish.ok) await fail(publish, "Failed to publish Agent");
  if (request.visibility && request.visibility !== "private") {
    const approval = await fetch(
      `${base}/api/resources/${resource.id}/visibility-applications`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_visibility: request.visibility }),
      },
    );
    if (!approval.ok)
      await fail(approval, "Failed to submit Agent visibility request");
  }
  return fromResource({
    ...resource,
    latest_version: 1,
    draft_revision: draftPayload.revision,
  });
}
export async function updateAgent(
  id: string,
  request: UpdateAgentRequest,
): Promise<Agent> {
  const base = getBackendBaseURL();
  const draft = await fetch(
    `${base}/api/resources/${encodeURIComponent(id)}/agent-draft`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        config: {
          ...request,
          name: undefined,
          knowledge_dependencies: undefined,
        },
        soul: request.soul,
        knowledge_dependencies: request.knowledge_dependencies,
        expected_revision: request.draft_revision ?? 0,
      }),
    },
  );
  if (!draft.ok) await fail(draft, "Failed to update agent");
  const payload = (await draft.json()) as { revision: number };
  const publish = await fetch(
    `${base}/api/resources/${encodeURIComponent(id)}/publish`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_draft_revision: payload.revision,
        scan_result: {},
      }),
    },
  );
  if (!publish.ok) await fail(publish, "Failed to publish Agent");
  return getAgent(id);
}
export async function deleteAgent(id: string): Promise<void> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(id)}/archive`,
    { method: "POST" },
  );
  if (!res.ok) await fail(res, "Failed to delete agent");
}
export async function toggleAgentFavorite(
  id: string,
  isFavorited = false,
): Promise<{ success: boolean; is_favorited: boolean }> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(id)}/favorite`,
    { method: isFavorited ? "DELETE" : "POST" },
  );
  if (!res.ok) await fail(res, "Failed to update Agent favorite");
  return { success: true, is_favorited: !isFavorited };
}
export async function checkAgentName(
  name: string,
): Promise<{ available: boolean; name: string }> {
  let res: Response;
  try {
    res = await fetch(
      `${getBackendBaseURL()}/api/resources/aliases/agent/${encodeURIComponent(name)}`,
    );
  } catch {
    throw new AgentNameCheckError(
      "Could not reach the iDeer backend",
      "backend_unreachable",
    );
  }
  if (res.status === 404) return { available: true, name };
  if (!res.ok) {
    const parsed = await parseErrorDetail(res);
    const detail = typeof parsed?.detail === "string" ? parsed.detail : null;
    if (BACKEND_UNAVAILABLE_STATUSES.has(res.status))
      throw new AgentNameCheckError(
        "Could not reach the iDeer backend",
        "backend_unreachable",
        detail,
      );
    throw new AgentNameCheckError(
      detail ?? `Failed to check agent name: ${res.statusText}`,
      "request_failed",
      detail,
    );
  }
  return { available: false, name };
}
export async function exportAgent(id: string): Promise<Blob> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/resources/${encodeURIComponent(id)}/export`,
    { method: "GET" },
  );
  if (!res.ok) await fail(res, "Failed to export agent");
  return res.blob();
}
export async function importAgent(file: File): Promise<Agent> {
  const body = new FormData();
  body.append("archive", file);
  const res = await fetch(`${getBackendBaseURL()}/api/resources/import/agent`, {
    method: "POST",
    body,
  });
  if (!res.ok) await fail(res, "Failed to import agent");
  const resource = (await res.json()) as Resource;
  return getAgent(resource.id);
}
