import { afterEach, describe, expect, it, vi } from "vitest";

// Mock the fetcher and config modules
vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => ""),
}));

describe("workflows API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("listWorkflows sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockResponse = { workflows: [], total: 0 };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { listWorkflows } = await import("@/core/workflows/api");
    const result = await listWorkflows();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/workflows"),
    );
    expect(result).toEqual(mockResponse);
  });

  it("createWorkflow sends POST with yaml_content", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ name: "new-wf", steps_count: 1, inputs: {} }),
    });

    const { createWorkflow } = await import("@/core/workflows/api");
    await createWorkflow({ yaml_content: "name: new-wf\nsteps: []" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/workflows"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ yaml_content: "name: new-wf\nsteps: []" }),
      }),
    );
  });

  it("deleteWorkflow sends DELETE request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
    });

    const { deleteWorkflow } = await import("@/core/workflows/api");
    await deleteWorkflow("my-workflow");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/workflows/my-workflow"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("runWorkflow sends POST with inputs", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ run_id: "run-1", status: "running", workflow: "wf" }),
    });

    const { runWorkflow } = await import("@/core/workflows/api");
    const result = await runWorkflow("my-wf", { query: "test" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/workflows/my-wf/run"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ inputs: { query: "test" } }),
      }),
    );
    expect(result).toHaveProperty("run_id");
  });

  it("getRunStatus sends GET request", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    const mockStatus = {
      run_id: "run-1",
      workflow: "wf",
      status: "completed",
      steps: {},
    };
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatus),
    });

    const { getRunStatus } = await import("@/core/workflows/api");
    const result = await getRunStatus("my-wf", "run-1");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/workflows/my-wf/runs/run-1"),
    );
    expect(result).toEqual(mockStatus);
  });

  it("throws on non-ok response", async () => {
    const { fetch: mockFetch } = await import("@/core/api/fetcher");
    (mockFetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      statusText: "Not Found",
      json: () => Promise.resolve({}),
    });

    const { getWorkflow } = await import("@/core/workflows/api");
    await expect(getWorkflow("nonexistent")).rejects.toThrow();
  });
});
