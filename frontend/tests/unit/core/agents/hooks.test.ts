import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/agents/api", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  createAgent: vi.fn(),
  updateAgent: vi.fn(),
  deleteAgent: vi.fn(),
  toggleAgentFavorite: vi.fn(),
}));

import {
  listAgents,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
  toggleAgentFavorite,
} from "@/core/agents/api";
import {
  useAgents,
  useAgent,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  useToggleAgentFavorite,
} from "@/core/agents/hooks";

const mockListAgents = listAgents as ReturnType<typeof vi.fn>;
const mockGetAgent = getAgent as ReturnType<typeof vi.fn>;
const mockCreateAgent = createAgent as ReturnType<typeof vi.fn>;
const mockUpdateAgent = updateAgent as ReturnType<typeof vi.fn>;
const mockDeleteAgent = deleteAgent as ReturnType<typeof vi.fn>;
const mockToggleAgentFavorite = toggleAgentFavorite as ReturnType<typeof vi.fn>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
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

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAgents", () => {
  test("returns agents list from API", async () => {
    const agents = [
      {
        name: "agent1",
        description: "Test",
        model: null,
        visibility: "public",
      },
    ];
    mockListAgents.mockResolvedValue(agents);

    const { result } = renderHook(() => useAgents(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.agents.length > 0).toBe(true));

    expect(result.current.agents).toEqual(agents);
    expect(result.current.isLoading).toBe(false);
  });

  test("returns empty array while loading", () => {
    mockListAgents.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAgents(), {
      wrapper: createWrapper(),
    });

    expect(result.current.agents).toEqual([]);
    expect(result.current.isLoading).toBe(true);
  });

  test("provides refetch function", async () => {
    mockListAgents.mockResolvedValue([]);

    const { result } = renderHook(() => useAgents(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(typeof result.current.refetch).toBe("function"));
  });
});

describe("useAgent", () => {
  test("fetches single agent by name", async () => {
    const agent = {
      name: "agent1",
      description: "Test",
      model: null,
      visibility: "public",
    };
    mockGetAgent.mockResolvedValue(agent);

    const { result } = renderHook(() => useAgent("agent1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.agent).toEqual(agent));
    expect(mockGetAgent).toHaveBeenCalledWith("agent1");
  });

  test("does not fetch when name is null", () => {
    const { result } = renderHook(() => useAgent(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.agent).toBeNull();
    expect(mockGetAgent).not.toHaveBeenCalled();
  });

  test("does not fetch when name is undefined", () => {
    const { result } = renderHook(() => useAgent(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.agent).toBeNull();
    expect(mockGetAgent).not.toHaveBeenCalled();
  });

  test("does not fetch when name is empty string", () => {
    const { result } = renderHook(() => useAgent(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.agent).toBeNull();
    expect(mockGetAgent).not.toHaveBeenCalled();
  });

  test("returns null agent while loading", () => {
    mockGetAgent.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAgent("agent1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.agent).toBeNull();
    expect(result.current.isLoading).toBe(true);
  });
});

describe("useCreateAgent", () => {
  test("creates agent and invalidates query cache", async () => {
    const agent = {
      name: "new-agent",
      description: "New",
      model: null,
      visibility: "public",
    };
    mockCreateAgent.mockResolvedValue(agent);

    const { result } = renderHook(() => useCreateAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        name: "new-agent",
        description: "New",
      });
    });

    expect(mockCreateAgent).toHaveBeenCalledWith({
      name: "new-agent",
      description: "New",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports error on failure", async () => {
    mockCreateAgent.mockRejectedValue(new Error("Create failed"));

    const { result } = renderHook(() => useCreateAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({ name: "test" });
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Create failed");
  });
});

describe("useUpdateAgent", () => {
  test("updates agent and invalidates query cache", async () => {
    const agent = {
      name: "agent1",
      description: "Updated",
      model: null,
      visibility: "public",
    };
    mockUpdateAgent.mockResolvedValue(agent);

    const { result } = renderHook(() => useUpdateAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync({
        name: "agent1",
        request: { description: "Updated" },
      });
    });

    expect(mockUpdateAgent).toHaveBeenCalledWith("agent1", {
      description: "Updated",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports error on failure", async () => {
    mockUpdateAgent.mockRejectedValue(new Error("Update failed"));

    const { result } = renderHook(() => useUpdateAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync({
          name: "agent1",
          request: { description: "test" },
        });
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Update failed");
  });
});

describe("useDeleteAgent", () => {
  test("deletes agent and invalidates query cache", async () => {
    mockDeleteAgent.mockResolvedValue(undefined);

    const { result } = renderHook(() => useDeleteAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync("agent1");
    });

    expect(mockDeleteAgent).toHaveBeenCalledWith("agent1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports error on failure", async () => {
    mockDeleteAgent.mockRejectedValue(new Error("Delete failed"));

    const { result } = renderHook(() => useDeleteAgent(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync("agent1");
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Delete failed");
  });
});

describe("useToggleAgentFavorite", () => {
  test("toggles favorite and invalidates agents query", async () => {
    mockToggleAgentFavorite.mockResolvedValue({
      name: "agent1",
      is_favorite: true,
    });

    const { result } = renderHook(() => useToggleAgentFavorite(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync("agent1");
    });

    expect(mockToggleAgentFavorite).toHaveBeenCalledWith("agent1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports favorite toggle errors", async () => {
    mockToggleAgentFavorite.mockRejectedValue(new Error("Favorite failed"));

    const { result } = renderHook(() => useToggleAgentFavorite(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync("agent1");
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Favorite failed");
  });
});
