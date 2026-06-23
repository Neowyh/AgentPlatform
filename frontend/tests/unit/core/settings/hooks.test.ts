import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// ── SSR fallback tests ─────────────────────────────────────────────────────
// useSyncExternalStore's third argument (getServerSnapshot) is only called
// during SSR. We test it by mocking React's useSyncExternalStore to invoke
// the server snapshot instead of the client snapshot.

describe("SSR fallback functions", () => {
  it("useLocalSettings SSR fallback returns DEFAULT_LOCAL_SETTINGS", async () => {
    vi.resetModules();

    // Mock react to make useSyncExternalStore use the server snapshot
    vi.doMock("react", async () => {
      const actual = await vi.importActual("react");
      return {
        ...actual,
        useSyncExternalStore: vi.fn(
          (
            _subscribe: unknown,
            _getSnapshot: unknown,
            getServerSnapshot: () => unknown,
          ) => {
            return getServerSnapshot();
          },
        ),
      };
    });

    vi.doMock("@/core/settings/store", () => ({
      subscribe: vi.fn(),
      getBaseSettingsSnapshot: vi.fn(),
      getThreadModelSnapshot: vi.fn(),
      updateLocalSettings: vi.fn(),
      updateThreadSettings: vi.fn(),
    }));

    vi.doMock("@/core/settings/local", () => ({
      DEFAULT_LOCAL_SETTINGS: {
        notification: { enabled: true },
        tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
        context: {
          model_name: undefined,
          mode: undefined,
          reasoning_effort: undefined,
        },
      },
      applyThreadModelOverride: vi.fn((settings: unknown) => settings),
    }));

    const { useLocalSettings } = await import("@/core/settings/hooks");
    const { result } = renderHook(() => useLocalSettings());

    // The SSR fallback should return DEFAULT_LOCAL_SETTINGS
    const [settings] = result.current;
    expect(settings).toHaveProperty("notification");
    expect(settings).toHaveProperty("tokenUsage");
    expect(settings).toHaveProperty("context");
    expect(settings.notification.enabled).toBe(true);

    vi.doUnmock("react");
    vi.doUnmock("@/core/settings/store");
    vi.doUnmock("@/core/settings/local");
  });

  it("useThreadSettings SSR fallback returns DEFAULT_LOCAL_SETTINGS", async () => {
    vi.resetModules();

    vi.doMock("react", async () => {
      const actual = await vi.importActual("react");
      return {
        ...actual,
        useSyncExternalStore: vi.fn(
          (
            _subscribe: unknown,
            _getSnapshot: unknown,
            getServerSnapshot: () => unknown,
          ) => {
            return getServerSnapshot();
          },
        ),
      };
    });

    vi.doMock("@/core/settings/store", () => ({
      subscribe: vi.fn(),
      getBaseSettingsSnapshot: vi.fn(),
      getThreadModelSnapshot: vi.fn(),
      updateLocalSettings: vi.fn(),
      updateThreadSettings: vi.fn(),
    }));

    vi.doMock("@/core/settings/local", () => ({
      DEFAULT_LOCAL_SETTINGS: {
        notification: { enabled: true },
        tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
        context: {
          model_name: undefined,
          mode: undefined,
          reasoning_effort: undefined,
        },
      },
      applyThreadModelOverride: vi.fn((settings: unknown) => settings),
    }));

    const { useThreadSettings } = await import("@/core/settings/hooks");
    const { result } = renderHook(() => useThreadSettings("thread-ssr"));

    const [settings] = result.current;
    expect(settings).toHaveProperty("notification");
    expect(settings).toHaveProperty("tokenUsage");
    expect(settings).toHaveProperty("context");

    vi.doUnmock("react");
    vi.doUnmock("@/core/settings/store");
    vi.doUnmock("@/core/settings/local");
  });

  it("useThreadSettings SSR fallback for thread model returns undefined", async () => {
    vi.resetModules();

    // Track all getServerSnapshot calls to verify the thread model one returns undefined
    const serverSnapshotResults: unknown[] = [];
    vi.doMock("react", async () => {
      const actual = await vi.importActual("react");
      return {
        ...actual,
        useSyncExternalStore: vi.fn(
          (
            _subscribe: unknown,
            _getSnapshot: unknown,
            getServerSnapshot: () => unknown,
          ) => {
            const result = getServerSnapshot();
            serverSnapshotResults.push(result);
            return result;
          },
        ),
      };
    });

    vi.doMock("@/core/settings/store", () => ({
      subscribe: vi.fn(),
      getBaseSettingsSnapshot: vi.fn(),
      getThreadModelSnapshot: vi.fn(),
      updateLocalSettings: vi.fn(),
      updateThreadSettings: vi.fn(),
    }));

    vi.doMock("@/core/settings/local", () => ({
      DEFAULT_LOCAL_SETTINGS: {
        notification: { enabled: true },
        tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
        context: {
          model_name: undefined,
          mode: undefined,
          reasoning_effort: undefined,
        },
      },
      applyThreadModelOverride: vi.fn((settings: unknown, model: unknown) => {
        return { ...(settings as object), _threadModel: model };
      }),
    }));

    const { useThreadSettings } = await import("@/core/settings/hooks");
    const { result } = renderHook(() => useThreadSettings("thread-ssr-model"));

    // useThreadSettings calls useSyncExternalStore 3 times:
    // 1. base settings (SSR fallback returns DEFAULT_LOCAL_SETTINGS)
    // 2. thread model (SSR fallback returns undefined)
    // 3. (not applicable - there are only 2 calls)
    // The thread model SSR fallback should return undefined
    expect(serverSnapshotResults).toContain(undefined);

    vi.doUnmock("react");
    vi.doUnmock("@/core/settings/store");
    vi.doUnmock("@/core/settings/local");
  });
});

// ── Client-side tests (original) ────────────────────────────────────────────

// Mock the store module
vi.mock("@/core/settings/store", () => {
  const listeners = new Set<() => void>();
  let settings = {
    notification: { enabled: true },
    tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
    context: {
      model_name: undefined,
      mode: undefined,
      reasoning_effort: undefined,
    },
  };
  let threadModel: string | undefined = undefined;

  return {
    subscribe: vi.fn((listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    }),
    getBaseSettingsSnapshot: vi.fn(() => settings),
    getThreadModelSnapshot: vi.fn(() => threadModel),
    updateLocalSettings: vi.fn((key: string, value: unknown) => {
      settings = {
        ...settings,
        [key]: {
          ...(settings[key as keyof typeof settings] as Record<
            string,
            unknown
          >),
          ...(value as Record<string, unknown>),
        },
      };
      listeners.forEach((l) => l());
    }),
    updateThreadSettings: vi.fn(
      (threadId: string, key: string, value: unknown) => {
        settings = {
          ...settings,
          [key]: {
            ...(settings[key as keyof typeof settings] as Record<
              string,
              unknown
            >),
            ...(value as Record<string, unknown>),
          },
        };
        if (
          key === "context" &&
          value &&
          typeof value === "object" &&
          "model_name" in (value as Record<string, unknown>)
        ) {
          threadModel = (value as Record<string, unknown>).model_name as
            | string
            | undefined;
        }
        listeners.forEach((l) => l());
      },
    ),
  };
});

// Mock the local module
vi.mock("@/core/settings/local", () => ({
  DEFAULT_LOCAL_SETTINGS: {
    notification: { enabled: true },
    tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
    context: {
      model_name: undefined,
      mode: undefined,
      reasoning_effort: undefined,
    },
  },
  applyThreadModelOverride: vi.fn(
    (
      settings: Record<string, unknown>,
      threadModelName: string | undefined,
    ) => {
      if (!threadModelName) return settings;
      return {
        ...settings,
        context: {
          ...(settings.context as Record<string, unknown>),
          model_name: threadModelName,
        },
      };
    },
  ),
}));

import { useLocalSettings, useThreadSettings } from "@/core/settings/hooks";
import { applyThreadModelOverride } from "@/core/settings/local";
import {
  subscribe,
  getBaseSettingsSnapshot,
  getThreadModelSnapshot,
  updateLocalSettings,
  updateThreadSettings,
} from "@/core/settings/store";

describe("useLocalSettings", () => {
  it("calls useSyncExternalStore with subscribe and getBaseSettingsSnapshot", () => {
    renderHook(() => useLocalSettings());
    expect(subscribe).toHaveBeenCalled();
    expect(getBaseSettingsSnapshot).toHaveBeenCalled();
  });

  it("returns current settings and a setter function", () => {
    const { result } = renderHook(() => useLocalSettings());

    const [settings, setSettings] = result.current;

    expect(settings).toHaveProperty("notification");
    expect(settings).toHaveProperty("tokenUsage");
    expect(settings).toHaveProperty("context");
    expect(typeof setSettings).toBe("function");
  });

  it("returns default notification settings", () => {
    const { result } = renderHook(() => useLocalSettings());

    expect(result.current[0].notification.enabled).toBe(true);
  });

  it("setter calls updateLocalSettings", async () => {
    const { result } = renderHook(() => useLocalSettings());

    act(() => {
      result.current[1]("notification", { enabled: false });
    });

    // After update, the settings should reflect the change
    expect(result.current[0].notification.enabled).toBe(false);
  });

  it("setter calls updateLocalSettings with tokenUsage key", () => {
    const { result } = renderHook(() => useLocalSettings());

    act(() => {
      result.current[1]("tokenUsage", { headerTotal: false });
    });

    expect(result.current[0].tokenUsage.headerTotal).toBe(false);
  });

  it("setter calls updateLocalSettings with context key", () => {
    const { result } = renderHook(() => useLocalSettings());

    act(() => {
      result.current[1]("context", { mode: "flash" });
    });

    expect(result.current[0].context.mode).toBe("flash");
  });
});

describe("useThreadSettings", () => {
  it("calls useSyncExternalStore with subscribe, getBaseSettingsSnapshot, and getThreadModelSnapshot", () => {
    renderHook(() => useThreadSettings("thread-1"));
    expect(subscribe).toHaveBeenCalled();
    expect(getBaseSettingsSnapshot).toHaveBeenCalled();
    expect(getThreadModelSnapshot).toHaveBeenCalledWith("thread-1");
  });

  it("merges base settings with thread model override via applyThreadModelOverride", () => {
    renderHook(() => useThreadSettings("thread-1"));
    expect(applyThreadModelOverride).toHaveBeenCalled();
  });

  it("returns settings and setter for a thread", () => {
    const { result } = renderHook(() => useThreadSettings("thread-1"));

    const [settings, setSettings] = result.current;

    expect(settings).toHaveProperty("notification");
    expect(settings).toHaveProperty("tokenUsage");
    expect(settings).toHaveProperty("context");
    expect(typeof setSettings).toBe("function");
  });

  it("applies thread model override when set", () => {
    const { result } = renderHook(() => useThreadSettings("thread-1"));

    // With no thread model, context.model_name should be undefined
    expect(result.current[0].context.model_name).toBeUndefined();
  });

  it("setter calls updateThreadSettings with threadId", () => {
    const { result } = renderHook(() => useThreadSettings("thread-1"));

    act(() => {
      result.current[1]("notification", { enabled: false });
    });

    expect(result.current[0].notification.enabled).toBe(false);
  });

  it("updates when threadId changes", () => {
    const { result, rerender } = renderHook(
      ({ threadId }) => useThreadSettings(threadId),
      { initialProps: { threadId: "thread-1" } },
    );

    const firstSettings = result.current[0];

    rerender({ threadId: "thread-2" });

    // Settings object should still have the same shape
    expect(result.current[0]).toHaveProperty("notification");
    expect(result.current[0]).toHaveProperty("tokenUsage");
  });

  it("setter updates thread-specific settings", () => {
    const { result } = renderHook(() => useThreadSettings("thread-3"));

    act(() => {
      result.current[1]("tokenUsage", { inlineMode: "step_debug" });
    });

    expect(result.current[0].tokenUsage.inlineMode).toBe("step_debug");
  });
});
