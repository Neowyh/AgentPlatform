import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/memory/api", () => ({
  loadMemory: vi.fn(),
  clearMemory: vi.fn(),
  deleteMemoryFact: vi.fn(),
  importMemory: vi.fn(),
  createMemoryFact: vi.fn(),
  updateMemoryFact: vi.fn(),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

const MOCK_MEMORY = {
  version: "1.0",
  lastUpdated: "2026-01-01",
  user: {
    workContext: { summary: "work", updatedAt: "2026-01-01" },
    personalContext: { summary: "personal", updatedAt: "2026-01-01" },
    topOfMind: { summary: "mind", updatedAt: "2026-01-01" },
  },
  history: {
    recentMonths: { summary: "recent", updatedAt: "2026-01-01" },
    earlierContext: { summary: "earlier", updatedAt: "2026-01-01" },
    longTermBackground: { summary: "long", updatedAt: "2026-01-01" },
  },
  facts: [],
};

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

describe("useMemory", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns memory data on success", async () => {
    const { loadMemory } = await import("@/core/memory/api");
    vi.mocked(loadMemory).mockResolvedValue(MOCK_MEMORY);

    const { useMemory } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useMemory(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.memory).toBeDefined();
    expect(result.current.memory!.version).toBe("1.0");
    expect(result.current.error).toBeNull();
  });

  test("returns null memory on error", async () => {
    const { loadMemory } = await import("@/core/memory/api");
    vi.mocked(loadMemory).mockRejectedValue(new Error("Network error"));

    const { useMemory } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useMemory(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.memory).toBeNull();
    expect(result.current.error?.message).toContain("Network error");
  });
});

describe("useClearMemory", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls clearMemory on mutate", async () => {
    const { clearMemory } = await import("@/core/memory/api");
    vi.mocked(clearMemory).mockResolvedValue(MOCK_MEMORY);

    const { useClearMemory } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useClearMemory(), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(clearMemory).toHaveBeenCalled();
  });
});

describe("useDeleteMemoryFact", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls deleteMemoryFact with fact ID", async () => {
    const { deleteMemoryFact } = await import("@/core/memory/api");
    vi.mocked(deleteMemoryFact).mockResolvedValue(MOCK_MEMORY);

    const { useDeleteMemoryFact } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useDeleteMemoryFact(), {
      wrapper: createWrapper(),
    });

    result.current.mutate("f1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteMemoryFact).toHaveBeenCalledWith("f1");
  });
});

describe("useCreateMemoryFact", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls createMemoryFact with input", async () => {
    const { createMemoryFact } = await import("@/core/memory/api");
    vi.mocked(createMemoryFact).mockResolvedValue(MOCK_MEMORY);

    const { useCreateMemoryFact } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useCreateMemoryFact(), {
      wrapper: createWrapper(),
    });

    const input = { content: "new fact", category: "test", confidence: 0.9 };
    result.current.mutate(input);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createMemoryFact).toHaveBeenCalledWith(input);
  });
});

describe("useUpdateMemoryFact", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls updateMemoryFact with factId and input", async () => {
    const { updateMemoryFact } = await import("@/core/memory/api");
    vi.mocked(updateMemoryFact).mockResolvedValue(MOCK_MEMORY);

    const { useUpdateMemoryFact } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useUpdateMemoryFact(), {
      wrapper: createWrapper(),
    });

    const input = { content: "updated fact" };
    result.current.mutate({ factId: "f1", input });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateMemoryFact).toHaveBeenCalledWith("f1", input);
  });
});

describe("useImportMemory", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls importMemory with memory data", async () => {
    const { importMemory } = await import("@/core/memory/api");
    vi.mocked(importMemory).mockResolvedValue(MOCK_MEMORY);

    const { useImportMemory } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useImportMemory(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(MOCK_MEMORY);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(importMemory).toHaveBeenCalledWith(MOCK_MEMORY);
  });

  test("sets error on failure", async () => {
    const { importMemory } = await import("@/core/memory/api");
    vi.mocked(importMemory).mockRejectedValue(new Error("Import invalid"));

    const { useImportMemory } = await import("@/core/memory/hooks");
    const { result } = renderHook(() => useImportMemory(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(MOCK_MEMORY);

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toContain("Import invalid");
  });
});
