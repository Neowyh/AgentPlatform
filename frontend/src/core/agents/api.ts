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
  const res = await fetch(`${getBackendBaseURL()}/api/agents`);
  if (!res.ok) await extractError(res, "Failed to load agents");
  const data = (await res.json()) as { agents: Agent[] };
  return data.agents;
}

export async function getAgent(name: string): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`);
  if (!res.ok) await extractError(res, `Agent '${name}' not found`);
  return res.json() as Promise<Agent>;
}

export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const parsed = await parseErrorDetail(res);
    const detail = parsed?.detail;
    if (isAgentsApiDisabledDetail(detail)) {
      throw new AgentsApiDisabledError(
        formatDetail(detail, "Failed to create agent", res.statusText),
      );
    }
    throw new Error(
      formatDetail(detail, "Failed to create agent", res.statusText),
    );
  }
  return res.json() as Promise<Agent>;
}

export async function updateAgent(
  name: string,
  request: UpdateAgentRequest,
): Promise<Agent> {
  const res = await fetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) await extractError(res, "Failed to update agent");
  return res.json() as Promise<Agent>;
}

export async function deleteAgent(name: string): Promise<void> {
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

// ── Export / Import ──────────────────────────────────────────────

export async function exportAgent(name: string): Promise<Blob> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/export`,
    { method: "POST" },
  );
  if (!res.ok) await extractError(res, "Failed to export agent");
  return res.blob();
}

export async function importAgent(file: File): Promise<Agent> {
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
): Promise<{ success: boolean; is_favorited: boolean }> {
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
