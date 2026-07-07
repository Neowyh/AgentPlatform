import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { MCPConfig } from "./types";

export async function loadMCPConfig(): Promise<MCPConfig> {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`);
  if (!response.ok) {
    await extractError(response, "Failed to load MCP config");
  }
  const data = (await response.json()) as MCPConfig | null;
  if (!data) {
    throw new Error("Invalid MCP config: server returned empty response");
  }
  return data;
}

export async function updateMCPConfig(config: MCPConfig): Promise<MCPConfig> {
  const response = await fetch(`${getBackendBaseURL()}/api/mcp/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    await extractError(response, "Failed to update MCP config");
  }
  const data = (await response.json()) as MCPConfig | null;
  if (!data) {
    throw new Error("Invalid MCP config: server returned empty response");
  }
  return data;
}
