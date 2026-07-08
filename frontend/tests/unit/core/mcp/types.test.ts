import { describe, expect, it } from "vitest";

import type {
  MCPConfig,
  MCPServerConfig,
  McpOAuthConfig,
} from "@/core/mcp/types";

describe("McpOAuthConfig", () => {
  it("can be constructed with all fields", () => {
    const config: McpOAuthConfig = {
      enabled: true,
      token_url: "https://auth.example.com/token",
      grant_type: "client_credentials",
      client_id: "my-client",
      client_secret: "my-secret",
      scope: "read write",
      audience: "https://api.example.com",
      token_field: "access_token",
      token_type_field: "token_type",
      expires_in_field: "expires_in",
      default_token_type: "Bearer",
      refresh_skew_seconds: 30,
      extra_token_params: { resource: "https://api.example.com" },
    };
    expect(config.enabled).toBe(true);
    expect(config.grant_type).toBe("client_credentials");
    expect(config.refresh_skew_seconds).toBe(30);
  });

  it("accepts refresh_token grant_type", () => {
    const config: McpOAuthConfig = {
      enabled: true,
      token_url: "https://auth.example.com/token",
      grant_type: "refresh_token",
      refresh_token: "old-token",
      token_field: "access_token",
      token_type_field: "token_type",
      expires_in_field: "expires_in",
      default_token_type: "Bearer",
      refresh_skew_seconds: 60,
      extra_token_params: {},
    };
    expect(config.grant_type).toBe("refresh_token");
    expect(config.refresh_token).toBe("old-token");
  });
});

describe("MCPServerConfig", () => {
  it("can be constructed for stdio server type", () => {
    const config: MCPServerConfig = {
      enabled: true,
      type: "stdio",
      command: "node",
      args: ["server.js"],
      env: { NODE_ENV: "production" },
      headers: {},
      description: "Node.js MCP server",
    };
    expect(config.type).toBe("stdio");
    expect(config.command).toBe("node");
  });

  it("can be constructed for sse server type with oauth", () => {
    const config: MCPServerConfig = {
      enabled: true,
      type: "sse",
      url: "http://localhost:3001/sse",
      args: [],
      env: {},
      headers: { Authorization: "Bearer token" },
      oauth: {
        enabled: true,
        token_url: "http://localhost:3001/token",
        grant_type: "client_credentials",
        token_field: "access_token",
        token_type_field: "token_type",
        expires_in_field: "expires_in",
        default_token_type: "Bearer",
        refresh_skew_seconds: 30,
        extra_token_params: {},
      },
      description: "SSE server",
    };
    expect(config.type).toBe("sse");
    expect(config.oauth).toBeDefined();
    expect(config.oauth!.enabled).toBe(true);
  });

  it("can be constructed for http server type", () => {
    const config: MCPServerConfig = {
      enabled: true,
      type: "http",
      url: "http://localhost:5000",
      args: [],
      env: {},
      headers: {},
      description: "HTTP server",
    };
    expect(config.type).toBe("http");
  });
});

describe("MCPConfig", () => {
  it("wraps servers in a record keyed by name", () => {
    const config: MCPConfig = {
      mcp_servers: {
        "server-1": {
          enabled: true,
          type: "stdio",
          command: "echo",
          args: [],
          env: {},
          headers: {},
          description: "Server 1",
        },
      },
    };
    const server = config.mcp_servers["server-1"];
    expect(server).toBeDefined();
    expect(server!.description).toBe("Server 1");
  });
});
