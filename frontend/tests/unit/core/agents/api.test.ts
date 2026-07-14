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
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ agents }),
    });

    const result = await listAgents();

    expect(mockFetch).toHaveBeenCalledWith("http://localhost:8000/api/agents");
    expect(result).toEqual(agents);
  });

  test("calls extractError on failure", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    mockExtractError.mockRejectedValue(new Error("Failed to load agents"));

    await expect(listAgents()).rejects.toThrow("Failed to load agents");
    expect(mockExtractError).toHaveBeenCalledWith(
      expect.anything(),
      "Failed to load agents",
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
});

// ── createAgent ──────────────────────────────────────────────────────────

describe("createAgent", () => {
  test("sends POST request with agent data", async () => {
    const agent = {
      name: "new-agent",
      description: "New",
      model: "gpt-4",
      visibility: "public",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(agent),
    });

    const result = await createAgent({ name: "new-agent", description: "New" });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/agents",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(result).toEqual(agent);
  });

  test("throws AgentsApiDisabledError when API is disabled", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 403 });
    mockParseErrorDetail.mockResolvedValue({
      detail: { code: "AGENTS_API_DISABLED" },
    });

    await expect(createAgent({ name: "test" })).rejects.toThrow(
      AgentsApiDisabledError,
    );
  });

  test("throws generic error on other failures", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });
    mockParseErrorDetail.mockResolvedValue({ detail: undefined });

    await expect(createAgent({ name: "test" })).rejects.toThrow();
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
});

// ── importAgent ──────────────────────────────────────────────────────────

describe("importAgent", () => {
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
