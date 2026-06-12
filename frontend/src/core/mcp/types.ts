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
