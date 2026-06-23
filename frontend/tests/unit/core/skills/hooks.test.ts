import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/skills/api", () => ({
  enableSkill: vi.fn(),
}));

vi.mock("@/core/skills", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...({} as any).actual,
    loadSkills: vi.fn(),
  };
});

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

describe("useSkills", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("returns skills data on success", async () => {
    const { loadSkills } = await import("@/core/skills");
    vi.mocked(loadSkills).mockResolvedValue([
      {
        name: "skill-1",
        description: "First skill",
        category: "test",
        license: "MIT",
        enabled: true,
      },
      {
        name: "skill-2",
        description: "Second skill",
        category: "test",
        license: "MIT",
        enabled: false,
      },
    ]);

    const { useSkills } = await import("@/core/skills/hooks");
    const { result } = renderHook(() => useSkills(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.skills).toHaveLength(2);
    expect(result.current.skills[0]!.name).toBe("skill-1");
    expect(result.current.error).toBeNull();
  });

  test("returns empty array on error", async () => {
    const { loadSkills } = await import("@/core/skills");
    vi.mocked(loadSkills).mockRejectedValue(new Error("Network error"));

    const { useSkills } = await import("@/core/skills/hooks");
    const { result } = renderHook(() => useSkills(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.skills).toEqual([]);
    expect(result.current.error).toBeDefined();
  });
});

describe("useEnableSkill", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("calls enableSkill with correct params", async () => {
    const { enableSkill } = await import("@/core/skills/api");
    vi.mocked(enableSkill).mockResolvedValue(undefined);

    const { useEnableSkill } = await import("@/core/skills/hooks");
    const { result } = renderHook(() => useEnableSkill(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ skillName: "my-skill", enabled: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(enableSkill).toHaveBeenCalledWith("my-skill", true);
  });
});
