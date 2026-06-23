import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/workflows/api", () => ({
  listWorkflows: vi.fn(),
  getWorkflow: vi.fn(),
  createWorkflow: vi.fn(),
  updateWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  runWorkflow: vi.fn(),
  getRunStatus: vi.fn(),
  submitReview: vi.fn(),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

// ---------------------------------------------------------------
// useWorkflows
// ---------------------------------------------------------------
describe("useWorkflows", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns workflows list on success", async () => {
    const { listWorkflows } = await import("@/core/workflows/api");
    vi.mocked(listWorkflows).mockResolvedValue({
      workflows: [
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
      ],
      total: 2,
    });

    const { useWorkflows } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workflows).toHaveLength(2);
    expect(result.current.workflows[0]!.name).toBe("wf-1");
    expect(result.current.error).toBeNull();
  });

  test("returns empty array when data is undefined (loading)", async () => {
    const { listWorkflows } = await import("@/core/workflows/api");
    vi.mocked(listWorkflows).mockReturnValue(new Promise(() => {})); // never resolves

    const { useWorkflows } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    expect(result.current.workflows).toEqual([]);
    expect(result.current.isLoading).toBe(true);
  });

  test("sets error on failure", async () => {
    const { listWorkflows } = await import("@/core/workflows/api");
    vi.mocked(listWorkflows).mockRejectedValue(new Error("Network error"));

    const { useWorkflows } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workflows).toEqual([]);
    expect(result.current.error).toBeDefined();
  });

  test("exposes refetch function", async () => {
    const { listWorkflows } = await import("@/core/workflows/api");
    vi.mocked(listWorkflows).mockResolvedValue({ workflows: [], total: 0 });

    const { useWorkflows } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(typeof result.current.refetch).toBe("function");
  });
});

// ---------------------------------------------------------------
// useWorkflow
// ---------------------------------------------------------------
describe("useWorkflow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns workflow detail on success", async () => {
    const { getWorkflow } = await import("@/core/workflows/api");
    const detail = {
      name: "my-wf",
      description: "desc",
      version: "1.0",
      steps_count: 1,
      inputs: {},
      yaml_content: "name: my-wf",
      steps: [],
    };
    vi.mocked(getWorkflow).mockResolvedValue(detail);

    const { useWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflow("my-wf"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workflow).toEqual(detail);
    expect(result.current.error).toBeNull();
  });

  test("returns null when name is null (query disabled)", async () => {
    const { getWorkflow } = await import("@/core/workflows/api");

    const { useWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflow(null), {
      wrapper: createWrapper(),
    });

    // Should not call API when name is null
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getWorkflow).not.toHaveBeenCalled();
    expect(result.current.workflow).toBeNull();
  });

  test("returns null when name is undefined (query disabled)", async () => {
    const { getWorkflow } = await import("@/core/workflows/api");

    const { useWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflow(undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getWorkflow).not.toHaveBeenCalled();
    expect(result.current.workflow).toBeNull();
  });

  test("returns null when name is empty string (query disabled)", async () => {
    const { getWorkflow } = await import("@/core/workflows/api");

    const { useWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflow(""), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getWorkflow).not.toHaveBeenCalled();
    expect(result.current.workflow).toBeNull();
  });

  test("sets error on failure", async () => {
    const { getWorkflow } = await import("@/core/workflows/api");
    vi.mocked(getWorkflow).mockRejectedValue(new Error("Not found"));

    const { useWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useWorkflow("missing"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.workflow).toBeNull();
    expect(result.current.error).toBeDefined();
  });
});

// ---------------------------------------------------------------
// useCreateWorkflow
// ---------------------------------------------------------------
describe("useCreateWorkflow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls createWorkflow API and succeeds", async () => {
    const { createWorkflow } = await import("@/core/workflows/api");
    const created = {
      name: "new-wf",
      description: "",
      version: "1",
      steps_count: 1,
      inputs: {},
    };
    vi.mocked(createWorkflow).mockResolvedValue(created);

    const { useCreateWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useCreateWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ yaml_content: "name: new-wf\nsteps: []" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createWorkflow).toHaveBeenCalledWith({
      yaml_content: "name: new-wf\nsteps: []",
    });
    expect(result.current.data).toEqual(created);
  });

  test("sets error on failure", async () => {
    const { createWorkflow } = await import("@/core/workflows/api");
    vi.mocked(createWorkflow).mockRejectedValue(new Error("Validation error"));

    const { useCreateWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useCreateWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({});

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});

// ---------------------------------------------------------------
// useUpdateWorkflow
// ---------------------------------------------------------------
describe("useUpdateWorkflow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls updateWorkflow API with name and data", async () => {
    const { updateWorkflow } = await import("@/core/workflows/api");
    const updated = {
      name: "wf",
      description: "updated",
      version: "2",
      steps_count: 1,
      inputs: {},
    };
    vi.mocked(updateWorkflow).mockResolvedValue(updated);

    const { useUpdateWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useUpdateWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ name: "wf", data: { description: "updated" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateWorkflow).toHaveBeenCalledWith("wf", {
      description: "updated",
    });
    expect(result.current.data).toEqual(updated);
  });

  test("sets error on failure", async () => {
    const { updateWorkflow } = await import("@/core/workflows/api");
    vi.mocked(updateWorkflow).mockRejectedValue(new Error("Not found"));

    const { useUpdateWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useUpdateWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ name: "missing", data: {} });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});

// ---------------------------------------------------------------
// useDeleteWorkflow
// ---------------------------------------------------------------
describe("useDeleteWorkflow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls deleteWorkflow API with name", async () => {
    const { deleteWorkflow } = await import("@/core/workflows/api");
    vi.mocked(deleteWorkflow).mockResolvedValue(undefined);

    const { useDeleteWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useDeleteWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate("wf-to-delete");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteWorkflow).toHaveBeenCalledWith("wf-to-delete");
  });

  test("sets error on failure", async () => {
    const { deleteWorkflow } = await import("@/core/workflows/api");
    vi.mocked(deleteWorkflow).mockRejectedValue(new Error("Forbidden"));

    const { useDeleteWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useDeleteWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate("wf");

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});

// ---------------------------------------------------------------
// useRunWorkflow
// ---------------------------------------------------------------
describe("useRunWorkflow", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls runWorkflow API with name and inputs", async () => {
    const { runWorkflow } = await import("@/core/workflows/api");
    const runResult = { run_id: "run-123", status: "running", workflow: "wf" };
    vi.mocked(runWorkflow).mockResolvedValue(runResult);

    const { useRunWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ name: "wf", inputs: { query: "test" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(runWorkflow).toHaveBeenCalledWith("wf", { query: "test" });
    expect(result.current.data).toEqual(runResult);
  });

  test("sets error on failure", async () => {
    const { runWorkflow } = await import("@/core/workflows/api");
    vi.mocked(runWorkflow).mockRejectedValue(new Error("Run failed"));

    const { useRunWorkflow } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunWorkflow(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ name: "wf", inputs: {} });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});

// ---------------------------------------------------------------
// useRunStatus
// ---------------------------------------------------------------
describe("useRunStatus", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns run status on success", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");
    const status = {
      run_id: "run-1",
      workflow: "wf",
      status: "completed",
      current_step: null,
      error: null,
      steps: {},
    };
    vi.mocked(getRunStatus).mockResolvedValue(status);

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("wf", "run-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.runStatus).toEqual(status);
    expect(result.current.error).toBeNull();
  });

  test("returns null when name is null (query disabled)", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus(null, "run-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getRunStatus).not.toHaveBeenCalled();
    expect(result.current.runStatus).toBeNull();
  });

  test("returns null when runId is null (query disabled)", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("wf", null), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getRunStatus).not.toHaveBeenCalled();
    expect(result.current.runStatus).toBeNull();
  });

  test("returns null when both name and runId are null", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus(null, null), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getRunStatus).not.toHaveBeenCalled();
    expect(result.current.runStatus).toBeNull();
  });

  test("sets error on failure", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");
    vi.mocked(getRunStatus).mockRejectedValue(new Error("Not found"));

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("wf", "bad-id"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.runStatus).toBeNull();
    expect(result.current.error).toBeDefined();
  });

  test("exposes refetch function", async () => {
    const { getRunStatus } = await import("@/core/workflows/api");
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: "r1",
      workflow: "wf",
      status: "running",
      current_step: "step1",
      error: null,
      steps: {},
    });

    const { useRunStatus } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useRunStatus("wf", "r1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(typeof result.current.refetch).toBe("function");
  });
});

// ---------------------------------------------------------------
// useSubmitReview
// ---------------------------------------------------------------
describe("useSubmitReview", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls submitReview API with correct params", async () => {
    const { submitReview } = await import("@/core/workflows/api");
    vi.mocked(submitReview).mockResolvedValue({
      success: true,
      run_id: "run-1",
    });

    const { useSubmitReview } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useSubmitReview(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      name: "wf",
      runId: "run-1",
      data: { approved: true, comment: "Looks good" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(submitReview).toHaveBeenCalledWith("wf", "run-1", {
      approved: true,
      comment: "Looks good",
    });
    expect(result.current.data).toEqual({ success: true, run_id: "run-1" });
  });

  test("calls submitReview with rejection (approved=false)", async () => {
    const { submitReview } = await import("@/core/workflows/api");
    vi.mocked(submitReview).mockResolvedValue({
      success: true,
      run_id: "run-2",
    });

    const { useSubmitReview } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useSubmitReview(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      name: "wf",
      runId: "run-2",
      data: { approved: false, comment: "Needs changes" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(submitReview).toHaveBeenCalledWith("wf", "run-2", {
      approved: false,
      comment: "Needs changes",
    });
  });

  test("sets error on failure", async () => {
    const { submitReview } = await import("@/core/workflows/api");
    vi.mocked(submitReview).mockRejectedValue(new Error("Conflict"));

    const { useSubmitReview } = await import("@/core/workflows/hooks");
    const { result } = renderHook(() => useSubmitReview(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      name: "wf",
      runId: "run-1",
      data: { approved: true },
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeDefined();
  });
});
