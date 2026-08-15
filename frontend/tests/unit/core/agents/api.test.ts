import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
  parseErrorDetail: vi.fn(),
  formatDetail: vi.fn((detail: unknown, action: string, statusText: string) => {
    if (typeof detail === "string") return detail;
    if (typeof detail === "object" && detail !== null && "message" in detail)
      return (detail as { message: string }).message;
    return `${action}: ${statusText}`;
  }),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

import {
  listAgents,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
  checkAgentName,
  exportAgent,
  importAgent,
  toggleAgentFavorite,
  AgentNameCheckError,
  AgentsApiDisabledError,
} from "@/core/agents/api";
import { extractError, parseErrorDetail } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";

const mockFetch = fetch as ReturnType<typeof vi.fn>;
const mockExtractError = extractError as ReturnType<typeof vi.fn>;
const mockParseErrorDetail = parseErrorDetail as ReturnType<typeof vi.fn>;

afterEach(() => {
  vi.clearAllMocks();
});

// ── listAgents ───────────────────────────────────────────────────────────

describe("listAgents", () => {
  test("returns agents array from API", async () => {
    const agents = [
      {
        name: "agent1",
        description: "Test agent",
        model: "gpt-4",
        visibility: "public",
      },
    ];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: 0, mode: "dual" }),
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ agents }),
    });

    const result = await listAgents();

    expect(mockFetch).toHaveBeenCalledWith("http://localhost:8000/api/agents");
    expect(result).toEqual(agents);
  });

  test("merges visible canonical Agents and keeps their UUID as route identity", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          items: [
            {
              id: "11111111-1111-1111-1111-111111111111",
              type: "agent",
              slug: "shared-agent",
              display_name: "Shared Agent",
              owner_id: "owner",
              visibility: "public",
              scope_department_id: null,
            },
          ],
          total: 1,
        }),
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ agents: [] }),
    });

    await expect(listAgents()).resolves.toEqual([
      expect.objectContaining({
        resource_id: "11111111-1111-1111-1111-111111111111",
        name: "Shared Agent",
        slug: "shared-agent",
        read_only: true,
      }),
    ]);
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(
      new Error("Failed to load canonical agents"),
    );

    await expect(listAgents()).rejects.toThrow(
      "Failed to load canonical agents",
    );
    expect(mockExtractError).toHaveBeenCalledWith(
      expect.anything(),
      "Failed to load canonical agents",
    );
  });

  test("canonical mode never reads the legacy Agent list", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: 0, mode: "canonical" }),
    });

    await expect(listAgents()).resolves.toEqual([]);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  test("loads a UUID Agent from the canonical resources facade", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          resource: {
            id: "11111111-1111-1111-1111-111111111111",
            type: "agent",
            slug: "shared-agent",
            display_name: "Shared Agent",
            owner_id: "owner",
            visibility: "public",
            scope_department_id: null,
            draft_revision: 1,
            can_modify: false,
          },
          content: {
            config: {
              description: "Shared description",
              model: "gpt-4",
              tool_groups: ["web"],
              skills: [],
            },
            soul: "Shared soul",
          },
        }),
    });

    const result = await getAgent("11111111-1111-1111-1111-111111111111");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/resources/11111111-1111-1111-1111-111111111111/published",
    );
    expect(result).toEqual(
      expect.objectContaining({
        resource_id: "11111111-1111-1111-1111-111111111111",
        name: "Shared Agent",
        description: "Shared description",
        soul: "Shared soul",
      }),
    );
  });
});

// ── getAgent ─────────────────────────────────────────────────────────────

describe("getAgent", () => {
  test("returns single agent by name", async () => {
    const agent = {
      name: "agent1",
      description: "Test",
      model: null,
      visibility: "public",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(agent),
    });

    const result = await getAgent("agent1");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/agents/agent1",
    );
    expect(result).toEqual(agent);
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("Agent not found"));

    await expect(getAgent("nonexistent")).rejects.toThrow("Agent not found");
  });

  test("resolves a migrated legacy slug to its canonical UUID", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    const resource = {
      id: resourceId,
      type: "agent",
      slug: "migrated-agent",
      display_name: "Migrated Agent",
      owner_id: "owner",
      visibility: "public",
      scope_department_id: null,
      latest_version: 1,
      draft_revision: 1,
      can_modify: false,
    };
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(resource),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            resource,
            content: { config: {}, soul: "" },
          }),
      });

    await expect(getAgent("migrated-agent")).resolves.toMatchObject({
      resource_id: resourceId,
    });
    expect(mockFetch.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/api/agents/migrated-agent",
      "http://localhost:8000/api/resources/aliases/agent/migrated-agent",
      `http://localhost:8000/api/resources/${resourceId}/published`,
    ]);
  });
});

// ── createAgent ──────────────────────────────────────────────────────────

describe("createAgent", () => {
  test("creates, drafts, and publishes a private canonical Agent", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: resourceId,
            type: "agent",
            slug: "new-agent",
            display_name: "new-agent",
            owner_id: "owner",
            visibility: "private",
            scope_department_id: null,
            latest_version: 0,
            draft_revision: 0,
            can_modify: true,
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ revision: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ version: 1 }),
      });

    const result = await createAgent({ name: "new-agent", description: "New" });

    expect(mockFetch.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/api/resources",
      `http://localhost:8000/api/resources/${resourceId}/agent-draft`,
      `http://localhost:8000/api/resources/${resourceId}/publish`,
    ]);
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/resources",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(result).toMatchObject({
      resource_id: resourceId,
      name: "new-agent",
      read_only: false,
    });
  });

  test("delegates canonical resource creation failures", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });
    mockExtractError.mockRejectedValue(new Error("create failed"));

    await expect(createAgent({ name: "test" })).rejects.toThrow(
      "create failed",
    );
  });

  test("submits non-private visibility through approval after publishing", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: resourceId,
            type: "agent",
            slug: "shared-agent",
            display_name: "shared-agent",
            owner_id: "owner",
            visibility: "private",
            scope_department_id: null,
            latest_version: 0,
            draft_revision: 0,
            can_modify: true,
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ revision: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ version: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "app" }),
      });

    await createAgent({ name: "shared-agent", visibility: "public" });

    expect(mockFetch).toHaveBeenNthCalledWith(
      4,
      `http://localhost:8000/api/resources/${resourceId}/visibility-applications`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ── updateAgent ──────────────────────────────────────────────────────────

describe("updateAgent", () => {
  test("sends PUT request with updated data", async () => {
    const agent = {
      name: "agent1",
      description: "Updated",
      model: "gpt-4",
      visibility: "public",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(agent),
    });

    const result = await updateAgent("agent1", { description: "Updated" });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/agents/agent1",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result).toEqual(agent);
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("Failed to update agent"));

    await expect(
      updateAgent("agent1", { description: "test" }),
    ).rejects.toThrow("Failed to update agent");
  });

  test("saves and publishes canonical Agent drafts by UUID", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ revision: 3 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ version: 2 }),
      });

    await updateAgent(resourceId, {
      description: "Updated",
      skills: ["22222222-2222-2222-2222-222222222222"],
      soul: "Soul",
      draft_revision: 2,
    });

    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8000/api/resources/${resourceId}/agent-draft`,
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining('"expected_revision":2'),
      }),
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8000/api/resources/${resourceId}/publish`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ── deleteAgent ──────────────────────────────────────────────────────────

describe("deleteAgent", () => {
  test("sends DELETE request", async () => {
    mockFetch.mockResolvedValue({ ok: true });

    await deleteAgent("agent1");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/agents/agent1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("Failed to delete agent"));

    await expect(deleteAgent("agent1")).rejects.toThrow(
      "Failed to delete agent",
    );
  });

  test("archives canonical Agents instead of hard deleting them", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    mockFetch.mockResolvedValue({ ok: true });

    await deleteAgent(resourceId);

    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/archive`,
      { method: "POST" },
    );
  });
});

describe("toggleAgentFavorite", () => {
  test("posts the agent name and returns favorite state", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, is_favorited: true }),
    });

    await expect(toggleAgentFavorite("agent one")).resolves.toEqual({
      success: true,
      is_favorited: true,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/agents/agent%20one/favorite",
      expect.objectContaining({ method: "POST" }),
    );
  });

  test("uses extractError when toggling favorite fails", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("favorite failed"));

    await expect(toggleAgentFavorite("agent1")).rejects.toThrow(
      "favorite failed",
    );
  });

  test("unfavorites canonical Agents with the user-scoped resource endpoint", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    mockFetch.mockResolvedValue({ ok: true });

    await expect(toggleAgentFavorite(resourceId, true)).resolves.toEqual({
      success: true,
      is_favorited: false,
    });
    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/favorite`,
      { method: "DELETE" },
    );
  });
});

// ── checkAgentName ───────────────────────────────────────────────────────

describe("checkAgentName", () => {
  test("returns availability check result", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ available: true, name: "my-agent" }),
    });

    const result = await checkAgentName("my-agent");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/check?name="),
    );
    expect(result.available).toBe(true);
    expect(result.name).toBe("my-agent");
  });

  test("throws AgentNameCheckError on network failure", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    await expect(checkAgentName("test")).rejects.toThrow(AgentNameCheckError);
    await expect(checkAgentName("test")).rejects.toThrow(
      "Could not reach the iDeer backend",
    );
  });

  test("throws AgentNameCheckError for backend_unreachable status (502)", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(checkAgentName("test")).rejects.toThrow(AgentNameCheckError);
  });

  test("throws AgentNameCheckError for 503 status", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(checkAgentName("test")).rejects.toThrow(AgentNameCheckError);
  });

  test("throws AgentNameCheckError for 504 status", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 504,
      statusText: "Gateway Timeout",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(checkAgentName("test")).rejects.toThrow(AgentNameCheckError);
  });

  test("throws AgentsApiDisabledError when API is disabled", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });
    mockParseErrorDetail.mockResolvedValue({
      detail: { code: "AGENTS_API_DISABLED" },
    });

    await expect(checkAgentName("test")).rejects.toThrow(
      AgentsApiDisabledError,
    );
  });

  test("throws AgentsApiDisabledError with legacy string detail", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });
    mockParseErrorDetail.mockResolvedValue({
      detail: "agents_api.enabled must be true",
    });

    await expect(checkAgentName("test")).rejects.toThrow(
      AgentsApiDisabledError,
    );
  });

  test("throws AgentNameCheckError with request_failed for other errors", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: "Invalid name" });

    try {
      await checkAgentName("test");
      expect.fail("Should have thrown");
    } catch (error) {
      expect(error).toBeInstanceOf(AgentNameCheckError);
      if (error instanceof AgentNameCheckError) {
        expect(error.reason).toBe("request_failed");
      }
    }
  });

  test("reports a canonical alias hit as unavailable when the legacy check is disabled (410)", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 410 })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "11111111-1111-1111-1111-111111111111",
            type: "agent",
            slug: "existing-agent",
            display_name: "existing-agent",
            owner_id: "owner",
            visibility: "private",
            scope_department_id: null,
            latest_version: 1,
            draft_revision: 1,
            system_owned: false,
            can_modify: true,
          }),
      });

    const result = await checkAgentName("existing-agent");

    expect(result).toEqual({ available: false, name: "existing-agent" });
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/resources/aliases/agent/existing-agent",
    );
  });

  test("reports a canonical alias miss as available when the legacy check is disabled (410)", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 410 })
      .mockResolvedValueOnce({ ok: false, status: 404 });

    const result = await checkAgentName("fresh-agent");

    expect(result).toEqual({ available: true, name: "fresh-agent" });
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/resources/aliases/agent/fresh-agent",
    );
  });

  test("throws AgentNameCheckError when the canonical alias lookup fails", async () => {
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 410 })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Server Error",
      });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(checkAgentName("test")).rejects.toThrow(AgentNameCheckError);
  });
});

// ── exportAgent ──────────────────────────────────────────────────────────

describe("exportAgent", () => {
  test("sends POST request and returns blob", async () => {
    const mockBlob = new Blob(["exported data"]);
    mockFetch.mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(mockBlob),
    });

    const result = await exportAgent("agent1");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/agent1/export"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toBe(mockBlob);
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("Failed to export agent"));

    await expect(exportAgent("agent1")).rejects.toThrow(
      "Failed to export agent",
    );
  });

  test("exports a canonical immutable Agent version by UUID", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    const mockBlob = new Blob(["canonical"]);
    mockFetch.mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(mockBlob),
    });

    await expect(exportAgent(resourceId)).resolves.toBe(mockBlob);
    expect(mockFetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/resources/${resourceId}/export`,
      { method: "GET" },
    );
  });
});

// ── importAgent ──────────────────────────────────────────────────────────

describe("importAgent", () => {
  test("imports a canonical ZIP and reloads its published UUID version", async () => {
    const resourceId = "11111111-1111-1111-1111-111111111111";
    const file = new File(["zip"], "reviewer-v1.zip", {
      type: "application/zip",
    });
    const resource = {
      id: resourceId,
      type: "agent",
      slug: "reviewer",
      display_name: "reviewer",
      owner_id: "owner",
      visibility: "private",
      scope_department_id: null,
      latest_version: 1,
      draft_revision: 1,
      system_owned: false,
      can_modify: true,
    };
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(resource),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            resource,
            version: { version: 1 },
            content: { config: { description: "Reviewer" }, soul: "Review" },
          }),
      });

    const result = await importAgent(file);

    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/resources/import/agent",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
    expect(result).toMatchObject({ resource_id: resourceId, slug: "reviewer" });
  });

  test("reads file, parses JSON, and sends POST request", async () => {
    const importData = { name: "imported-agent", description: "Imported" };
    const mockFile = new File([JSON.stringify(importData)], "agent.json", {
      type: "application/json",
    });

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(importData),
    });

    const result = await importAgent(mockFile);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/import"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(importData),
      }),
    );
    expect(result).toEqual(importData);
  });

  test("throws error for invalid JSON file", async () => {
    const mockFile = new File(["not json"], "bad.json", {
      type: "application/json",
    });

    await expect(importAgent(mockFile)).rejects.toThrow(
      "Invalid import file: must be valid JSON",
    );
  });

  test("throws AgentsApiDisabledError when API is disabled", async () => {
    const importData = { name: "agent", description: "" };
    const mockFile = new File([JSON.stringify(importData)], "agent.json", {
      type: "application/json",
    });

    mockFetch.mockResolvedValue({ ok: false, status: 403 });
    mockParseErrorDetail.mockResolvedValue({
      detail: { code: "AGENTS_API_DISABLED" },
    });

    await expect(importAgent(mockFile)).rejects.toThrow(AgentsApiDisabledError);
  });

  test("creates a canonical Agent from a JSON bundle when the legacy import is disabled (410)", async () => {
    const importData = {
      name: "imported-agent",
      config: { description: "Imported", model: "gpt-4o" },
      soul: "SOUL",
      visibility: "private",
    };
    const mockFile = new File([JSON.stringify(importData)], "agent.json", {
      type: "application/json",
    });
    const resourceId = "22222222-2222-2222-2222-222222222222";
    const resource = {
      id: resourceId,
      type: "agent",
      slug: "imported-agent",
      display_name: "imported-agent",
      owner_id: "owner",
      visibility: "private",
      scope_department_id: null,
      latest_version: 1,
      draft_revision: 1,
      system_owned: false,
      can_modify: true,
    };

    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 410 })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(resource),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ revision: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ version: { version: 1 } }),
      });

    const result = await importAgent(mockFile);

    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/api/agents/import"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/resources",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toMatchObject({
      resource_id: resourceId,
      slug: "imported-agent",
      name: "imported-agent",
    });
  });

  test("throws when the canonical creation path also fails after a 410", async () => {
    const importData = { name: "imported-agent" };
    const mockFile = new File([JSON.stringify(importData)], "agent.json", {
      type: "application/json",
    });

    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 410 })
      .mockResolvedValueOnce({ ok: false, status: 500 });
    mockExtractError.mockRejectedValue(
      new Error("Failed to create Agent resource"),
    );

    await expect(importAgent(mockFile)).rejects.toThrow(
      "Failed to create Agent resource",
    );
  });

  test("throws generic error on other import failures", async () => {
    const importData = { name: "agent" };
    const mockFile = new File([JSON.stringify(importData)], "agent.json", {
      type: "application/json",
    });

    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(importAgent(mockFile)).rejects.toThrow();
  });
});

// ── AgentNameCheckError ──────────────────────────────────────────────────

describe("AgentNameCheckError", () => {
  test("has correct name and reason", () => {
    const error = new AgentNameCheckError(
      "test message",
      "backend_unreachable",
    );
    expect(error.name).toBe("AgentNameCheckError");
    expect(error.message).toBe("test message");
    expect(error.reason).toBe("backend_unreachable");
  });

  test("is instance of Error", () => {
    const error = new AgentNameCheckError("msg", "request_failed");
    expect(error).toBeInstanceOf(Error);
  });
});

// ── AgentsApiDisabledError ───────────────────────────────────────────────

describe("AgentsApiDisabledError", () => {
  test("has correct name and message", () => {
    const error = new AgentsApiDisabledError("disabled");
    expect(error.name).toBe("AgentsApiDisabledError");
    expect(error.message).toBe("disabled");
  });

  test("is instance of Error", () => {
    const error = new AgentsApiDisabledError("msg");
    expect(error).toBeInstanceOf(Error);
  });
});
