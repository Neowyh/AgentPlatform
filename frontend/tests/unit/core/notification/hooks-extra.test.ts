import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const mockUseLocalSettings = vi.fn(() => [
  {
    notification: { enabled: true },
    tokenUsage: { headerTotal: true, inlineMode: "per_turn" as const },
    context: {
      model_name: undefined,
      mode: undefined as "flash" | "thinking" | "pro" | "ultra" | undefined,
      reasoning_effort: undefined as
        | "minimal"
        | "low"
        | "medium"
        | "high"
        | undefined,
    },
  },
  vi.fn(),
]);

vi.mock("@/core/settings", () => ({
  useLocalSettings: (...args: unknown[]) =>
    mockUseLocalSettings(...(args as [])),
}));

import { useNotification } from "@/core/notification/hooks";

describe("useNotification - onclick and onerror handlers", () => {
  const originalNotification = globalThis.Notification;
  const notificationDescriptor = Object.getOwnPropertyDescriptor(
    globalThis,
    "Notification",
  );

  let mockInstances: Array<{
    onclick: (() => void) | null;
    onerror: ((error: Event) => void) | null;
    close: ReturnType<typeof vi.fn>;
  }> = [];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));
    mockInstances = [];

    mockUseLocalSettings.mockReturnValue([
      {
        notification: { enabled: true },
        tokenUsage: { headerTotal: true, inlineMode: "per_turn" as const },
        context: {
          model_name: undefined,
          mode: undefined as "flash" | "thinking" | "pro" | "ultra" | undefined,
          reasoning_effort: undefined as
            | "minimal"
            | "low"
            | "medium"
            | "high"
            | undefined,
        },
      },
      vi.fn(),
    ]);

    const MockNotification = vi.fn(function (
      this: (typeof mockInstances)[number],
    ) {
      this.onclick = null;
      this.onerror = null;
      this.close = vi.fn();
      mockInstances.push(this);
    });
    (MockNotification as unknown as { permission: string }).permission =
      "granted";
    (
      MockNotification as unknown as {
        requestPermission: () => Promise<string>;
      }
    ).requestPermission = vi.fn().mockResolvedValue("granted");

    Object.defineProperty(globalThis, "Notification", {
      value: MockNotification,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    if (notificationDescriptor) {
      Object.defineProperty(globalThis, "Notification", notificationDescriptor);
    }
  });

  it("sets onclick handler that calls window.focus() and notification.close()", () => {
    const focusSpy = vi.spyOn(window, "focus").mockImplementation(() => {});

    const { result } = renderHook(() => useNotification());

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    act(() => {
      result.current.showNotification("Test Title");
    });

    expect(mockInstances.length).toBe(1);
    const notification = mockInstances[0];
    expect(notification!.onclick).not.toBeNull();

    // Simulate click
    if (notification!.onclick) {
      (notification!.onclick as () => void)();
    }

    expect(focusSpy).toHaveBeenCalled();
    expect(notification!.close).toHaveBeenCalled();

    focusSpy.mockRestore();
  });

  it("sets onerror handler that logs the error", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { result } = renderHook(() => useNotification());

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    act(() => {
      result.current.showNotification("Test Title");
    });

    expect(mockInstances.length).toBe(1);
    const notification = mockInstances[0];
    expect(notification!.onerror).not.toBeNull();

    // Simulate error event
    const errorEvent = new Event("error");
    if (notification!.onerror) {
      notification!.onerror(errorEvent);
    }

    expect(consoleSpy).toHaveBeenCalledWith("Notification error:", errorEvent);

    consoleSpy.mockRestore();
  });

  it("creates notification with correct title and options", () => {
    const { result } = renderHook(() => useNotification());

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    act(() => {
      result.current.showNotification("My Title", {
        body: "My Body",
        icon: "/icon.png",
      });
    });

    expect(Notification).toHaveBeenCalledWith("My Title", {
      body: "My Body",
      icon: "/icon.png",
    });
  });

  it("returns correct initial state", () => {
    const { result } = renderHook(() => useNotification());

    expect(result.current.permission).toBe("granted");
    expect(result.current.isSupported).toBe(true);
    expect(typeof result.current.requestPermission).toBe("function");
    expect(typeof result.current.showNotification).toBe("function");
  });
});
