import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
  parseErrorDetail: vi.fn(),
  formatDetail: vi.fn((detail, action, statusText) => {
    if (typeof detail === "string") return detail;
    return `${action}: ${statusText}`;
  }),
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "http://localhost:8000",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

import * as agentsIndex from "@/core/agents/index";

const expectedAPISymbols = [
  "listAgents",
  "getAgent",
  "createAgent",
  "updateAgent",
  "deleteAgent",
  "checkAgentName",
  "exportAgent",
  "importAgent",
  "toggleAgentFavorite",
  "AgentNameCheckError",
] as const;

const expectedHooksSymbols = [
  "useAgents",
  "useAgent",
  "useCreateAgent",
  "useUpdateAgent",
  "useDeleteAgent",
  "useToggleAgentFavorite",
] as const;

const expectedAll = [...expectedAPISymbols, ...expectedHooksSymbols];

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetModules();
});

describe("agents barrel — runtime exports", () => {
  test("re-exports all api runtime symbols", () => {
    for (const name of expectedAPISymbols) {
      expect(agentsIndex).toHaveProperty(name);
    }
  });

  test("re-exports all hooks runtime symbols", () => {
    for (const name of expectedHooksSymbols) {
      expect(agentsIndex).toHaveProperty(name);
    }
  });

  test("exports exactly the expected runtime symbols", () => {
    const actualKeys = Object.keys(agentsIndex).sort();
    expect(actualKeys).toEqual([...expectedAll].sort());
  });

  test("types are accessible through barrel", () => {
    const _agents: import("@/core/agents").Agent =
      {} as import("@/core/agents").Agent;
    const _create: import("@/core/agents").CreateAgentRequest =
      {} as import("@/core/agents").CreateAgentRequest;
    const _update: import("@/core/agents").UpdateAgentRequest =
      {} as import("@/core/agents").UpdateAgentRequest;
    expect(true).toBe(true);
  });
});

describe("agents barrel — api function behavior", () => {
  test("listAgents returns canonical Agents through barrel", async () => {
    const { listAgents } = await import("@/core/agents/index");
    const { fetch } = await import("@/core/api/fetcher");
    const mockFetch = vi.mocked(fetch);

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          items: [
            {
              id: "11111111-1111-1111-1111-111111111111",
              type: "agent",
              slug: "agent1",
              display_name: "agent1",
              owner_id: "owner",
              visibility: "private",
              scope_department_id: null,
              latest_version: 1,
              draft_revision: 1,
              can_modify: true,
            },
          ],
          total: 1,
        }),
    } as Response);

    const result = await listAgents();
    expect(result).toEqual([
      expect.objectContaining({
        resource_id: "11111111-1111-1111-1111-111111111111",
        name: "agent1",
      }),
    ]);
  });
});

describe("agents barrel — reference identity", () => {
  test("listAgents is same reference as direct api import (ESM live binding)", async () => {
    const barrel = await import("@/core/agents/index");
    const direct = await import("@/core/agents/api");
    expect(barrel.listAgents).toBe(direct.listAgents);
  });
});
