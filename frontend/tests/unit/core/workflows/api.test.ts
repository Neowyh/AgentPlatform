import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

// Import after mocks are set up
const getMockFetch = async () => {
  const mod = await import("@/core/api/fetcher");
  return mod.fetch as unknown as ReturnType<typeof vi.fn>;
};

const okResponse = (body: unknown) => ({
  ok: true,
  json: () => Promise.resolve(body),
});

const errorResponse = (statusText = "Internal Server Error") => ({
  ok: false,
  statusText,
  json: () => Promise.resolve({ detail: statusText }),
});

describe("workflows API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---------------------------------------------------------------
  // listWorkflows
  // ---------------------------------------------------------------
  describe("listWorkflows", () => {
    it("sends GET to /api/workflows", async () => {
      const mockFetch = await getMockFetch();
      const payload = { workflows: [], total: 0 };
      mockFetch.mockResolvedValue(okResponse(payload));

      const { listWorkflows } = await import("@/core/workflows/api");
      const result = await listWorkflows();

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows",
      );
      expect(result).toEqual(payload);
    });

    it("returns workflow list and total count", async () => {
      const mockFetch = await getMockFetch();
      const workflows = [
        {
          name: "wf-1",
          description: "first",
          version: "1",
          steps_count: 2,
          inputs: {},
        },
        {
          name: "wf-2",
          description: "second",
          version: "2",
          steps_count: 3,
          inputs: {},
        },
      ];
      mockFetch.mockResolvedValue(okResponse({ workflows, total: 2 }));

      const { listWorkflows } = await import("@/core/workflows/api");
      const result = await listWorkflows();

      expect(result.workflows).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Service Unavailable"));

      const { listWorkflows } = await import("@/core/workflows/api");
      await expect(listWorkflows()).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // getWorkflow
  // ---------------------------------------------------------------
  describe("getWorkflow", () => {
    it("sends GET to /api/workflows/:name", async () => {
      const mockFetch = await getMockFetch();
      const detail = {
        name: "my-wf",
        description: "desc",
        version: "1.0",
        steps_count: 1,
        inputs: {},
        yaml_content: "name: my-wf\nsteps: []",
        steps: [],
      };
      mockFetch.mockResolvedValue(okResponse(detail));

      const { getWorkflow } = await import("@/core/workflows/api");
      const result = await getWorkflow("my-wf");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/my-wf",
      );
      expect(result).toEqual(detail);
    });

    it("encodes special characters in name", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(
        okResponse({ name: "a/b", yaml_content: "", steps: [] }),
      );

      const { getWorkflow } = await import("@/core/workflows/api");
      await getWorkflow("a/b");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/a%2Fb",
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Not Found"));

      const { getWorkflow } = await import("@/core/workflows/api");
      await expect(getWorkflow("missing")).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // createWorkflow
  // ---------------------------------------------------------------
  describe("createWorkflow", () => {
    it("sends POST with JSON body to /api/workflows", async () => {
      const mockFetch = await getMockFetch();
      const created = {
        name: "new-wf",
        description: "",
        version: "1",
        steps_count: 1,
        inputs: {},
      };
      mockFetch.mockResolvedValue(okResponse(created));

      const { createWorkflow } = await import("@/core/workflows/api");
      const data = { yaml_content: "name: new-wf\nsteps: []" };
      const result = await createWorkflow(data);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
      );
      expect(result).toEqual(created);
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Validation Error"));

      const { createWorkflow } = await import("@/core/workflows/api");
      await expect(createWorkflow({})).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // updateWorkflow
  // ---------------------------------------------------------------
  describe("updateWorkflow", () => {
    it("sends PUT with JSON body to /api/workflows/:name", async () => {
      const mockFetch = await getMockFetch();
      const updated = {
        name: "wf",
        description: "updated",
        version: "2",
        steps_count: 1,
        inputs: {},
      };
      mockFetch.mockResolvedValue(okResponse(updated));

      const { updateWorkflow } = await import("@/core/workflows/api");
      const data = { yaml_content: "name: wf\nsteps: []" };
      const result = await updateWorkflow("wf", data);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf",
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
      );
      expect(result).toEqual(updated);
    });

    it("encodes special characters in name", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(okResponse({ name: "a b" }));

      const { updateWorkflow } = await import("@/core/workflows/api");
      await updateWorkflow("a b", {});

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/a%20b",
        expect.any(Object),
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse());

      const { updateWorkflow } = await import("@/core/workflows/api");
      await expect(updateWorkflow("wf", {})).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // deleteWorkflow
  // ---------------------------------------------------------------
  describe("deleteWorkflow", () => {
    it("sends DELETE to /api/workflows/:name", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue({ ok: true });

      const { deleteWorkflow } = await import("@/core/workflows/api");
      await deleteWorkflow("wf-to-delete");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf-to-delete",
        { method: "DELETE" },
      );
    });

    it("returns void on success", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue({ ok: true });

      const { deleteWorkflow } = await import("@/core/workflows/api");
      const result = await deleteWorkflow("wf");

      expect(result).toBeUndefined();
    });

    it("encodes special characters in name", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue({ ok: true });

      const { deleteWorkflow } = await import("@/core/workflows/api");
      await deleteWorkflow("wf/special");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf%2Fspecial",
        expect.any(Object),
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Forbidden"));

      const { deleteWorkflow } = await import("@/core/workflows/api");
      await expect(deleteWorkflow("wf")).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // runWorkflow
  // ---------------------------------------------------------------
  describe("runWorkflow", () => {
    it("sends POST with inputs to /api/workflows/:name/run", async () => {
      const mockFetch = await getMockFetch();
      const runResult = {
        run_id: "run-123",
        status: "running",
        workflow: "wf",
      };
      mockFetch.mockResolvedValue(okResponse(runResult));

      const { runWorkflow } = await import("@/core/workflows/api");
      const inputs = { query: "hello", context: "test" };
      const result = await runWorkflow("wf", inputs);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs }),
        },
      );
      expect(result).toEqual(runResult);
    });

    it("encodes special characters in name", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(
        okResponse({ run_id: "r1", status: "pending", workflow: "a/b" }),
      );

      const { runWorkflow } = await import("@/core/workflows/api");
      await runWorkflow("a/b", {});

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/a%2Fb/run",
        expect.any(Object),
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse());

      const { runWorkflow } = await import("@/core/workflows/api");
      await expect(runWorkflow("wf", {})).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // getRunStatus
  // ---------------------------------------------------------------
  describe("getRunStatus", () => {
    it("sends GET to /api/workflows/:name/runs/:runId", async () => {
      const mockFetch = await getMockFetch();
      const status = {
        run_id: "run-1",
        workflow: "wf",
        status: "completed",
        current_step: null,
        error: null,
        steps: {},
      };
      mockFetch.mockResolvedValue(okResponse(status));

      const { getRunStatus } = await import("@/core/workflows/api");
      const result = await getRunStatus("wf", "run-1");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf/runs/run-1",
      );
      expect(result).toEqual(status);
    });

    it("encodes special characters in name and runId", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(
        okResponse({
          run_id: "a/b",
          workflow: "c/d",
          status: "running",
          steps: {},
        }),
      );

      const { getRunStatus } = await import("@/core/workflows/api");
      await getRunStatus("c/d", "a/b");

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/c%2Fd/runs/a%2Fb",
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Not Found"));

      const { getRunStatus } = await import("@/core/workflows/api");
      await expect(getRunStatus("wf", "bad-id")).rejects.toThrow();
    });
  });

  // ---------------------------------------------------------------
  // submitReview
  // ---------------------------------------------------------------
  describe("submitReview", () => {
    it("sends POST with approved and comment to review endpoint", async () => {
      const mockFetch = await getMockFetch();
      const reviewResult = { success: true, run_id: "run-1" };
      mockFetch.mockResolvedValue(okResponse(reviewResult));

      const { submitReview } = await import("@/core/workflows/api");
      const data = { approved: true, comment: "Looks good" };
      const result = await submitReview("wf", "run-1", data);

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/wf/runs/run-1/review",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved: true,
            data: { comment: "Looks good" },
          }),
        },
      );
      expect(result).toEqual(reviewResult);
    });

    it("sends approved=false without comment", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(
        okResponse({ success: true, run_id: "run-2" }),
      );

      const { submitReview } = await import("@/core/workflows/api");
      await submitReview("wf", "run-2", { approved: false });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({
            approved: false,
            data: { comment: undefined },
          }),
        }),
      );
    });

    it("encodes special characters in name and runId", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(okResponse({ success: true, run_id: "r" }));

      const { submitReview } = await import("@/core/workflows/api");
      await submitReview("a/b", "c/d", { approved: true });

      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/workflows/a%2Fb/runs/c%2Fd/review",
        expect.any(Object),
      );
    });

    it("throws on non-ok response", async () => {
      const mockFetch = await getMockFetch();
      mockFetch.mockResolvedValue(errorResponse("Conflict"));

      const { submitReview } = await import("@/core/workflows/api");
      await expect(
        submitReview("wf", "run-1", { approved: true }),
      ).rejects.toThrow();
    });
  });
});
