import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/models/api", () => ({
  loadModels: vi.fn(),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
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

describe("useModels", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns models data on success", async () => {
    const { loadModels } = await import("@/core/models/api");
    vi.mocked(loadModels).mockResolvedValue({
      models: [
        {
          id: "gpt-4",
          name: "gpt-4",
          model: "gpt-4",
          display_name: "GPT-4",
        },
      ],
      token_usage: { enabled: true },
    });

    const { useModels } = await import("@/core/models/hooks");
    const { result } = renderHook(() => useModels(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.models).toHaveLength(1);
    expect(result.current.models[0]!.name).toBe("gpt-4");
    expect(result.current.tokenUsageEnabled).toBe(true);
    expect(result.current.error).toBeNull();
  });

  test("returns empty models on error", async () => {
    const { loadModels } = await import("@/core/models/api");
    vi.mocked(loadModels).mockRejectedValue(new Error("Network error"));

    const { useModels } = await import("@/core/models/hooks");
    const { result } = renderHook(() => useModels(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.models).toEqual([]);
    expect(result.current.error).toBeDefined();
  });

  test("does not fetch when enabled is false", async () => {
    const { loadModels } = await import("@/core/models/api");
    vi.mocked(loadModels).mockClear();

    const { useModels } = await import("@/core/models/hooks");
    renderHook(() => useModels({ enabled: false }), {
      wrapper: createWrapper(),
    });

    // wait a tick for any potential query to fire
    await new Promise((r) => setTimeout(r, 100));

    expect(loadModels).not.toHaveBeenCalled();
  });
});
