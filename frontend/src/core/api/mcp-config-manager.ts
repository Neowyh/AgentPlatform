import { extractError } from "@/core/api/errors";
import { getBackendBaseURL } from "@/core/config";

export interface McpOAuthConfig {
  enabled: boolean;
  token_url: string;
  grant_type: "client_credentials" | "refresh_token";
  client_id?: string;
  client_secret?: string;
  refresh_token?: string;
  scope?: string;
  audience?: string;
  token_field: string;
  token_type_field: string;
  expires_in_field: string;
  default_token_type: string;
  refresh_skew_seconds: number;
  extra_token_params: Record<string, string>;
}

export interface MCPServerConfig {
  enabled: boolean;
  type: "stdio" | "sse" | "http";
  command?: string;
  args: string[];
  env: Record<string, string>;
  url?: string;
  headers: Record<string, string>;
  oauth?: McpOAuthConfig;
  description: string;
}

export interface MCPConfig {
  mcp_servers: Record<string, MCPServerConfig>;
}

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
