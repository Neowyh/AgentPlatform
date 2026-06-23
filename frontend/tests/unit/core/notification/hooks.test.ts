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

// Mock useLocalSettings
vi.mock("@/core/settings", () => ({
  useLocalSettings: () => mockUseLocalSettings(),
}));

import { useNotification } from "@/core/notification/hooks";

describe("useNotification", () => {
  const originalNotification = globalThis.Notification;
  const notificationDescriptor = Object.getOwnPropertyDescriptor(
    globalThis,
    "Notification",
  );

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-01T00:00:00Z"));
    // Reset the mock to default (enabled)
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
  });

  afterEach(() => {
    vi.useRealTimers();
    // Restore Notification
    if (notificationDescriptor) {
      Object.defineProperty(globalThis, "Notification", notificationDescriptor);
    }
  });

  describe("when Notification API is supported", () => {
    beforeEach(() => {
      const MockNotificationConstructor = vi.fn();
      const MockNotification = Object.assign(MockNotificationConstructor, {
        permission: "granted" as NotificationPermission,
        requestPermission: vi
          .fn()
          .mockResolvedValue("granted" as NotificationPermission),
      });

      Object.defineProperty(globalThis, "Notification", {
        value: MockNotification,
        writable: true,
        configurable: true,
      });
    });

    it("reports isSupported as true", () => {
      const { result } = renderHook(() => useNotification());
      expect(result.current.isSupported).toBe(true);
    });

    it("reports permission as granted", () => {
      const { result } = renderHook(() => useNotification());
      expect(result.current.permission).toBe("granted");
    });

    it("requestPermission calls Notification.requestPermission", async () => {
      const { result } = renderHook(() => useNotification());

      let permission: NotificationPermission | undefined;
      await act(async () => {
        permission = await result.current.requestPermission();
      });

      expect(permission).toBe("granted");
      expect(Notification.requestPermission).toHaveBeenCalled();
    });

    it("showNotification creates a Notification when permission is granted", () => {
      const { result } = renderHook(() => useNotification());

      // Advance time past the 1-second throttle
      act(() => {
        vi.advanceTimersByTime(1100);
      });

      act(() => {
        result.current.showNotification("Test Title", { body: "Test Body" });
      });

      expect(Notification).toHaveBeenCalledWith("Test Title", {
        body: "Test Body",
      });
    });

    it("showNotification throttles rapid calls", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      const { result } = renderHook(() => useNotification());

      // First call after throttle period
      act(() => {
        vi.advanceTimersByTime(1100);
      });

      act(() => {
        result.current.showNotification("First");
      });

      // Second call within throttle period (less than 1 second)
      act(() => {
        vi.advanceTimersByTime(500);
      });

      act(() => {
        result.current.showNotification("Second");
      });

      // Should have warned about sending too soon
      expect(consoleSpy).toHaveBeenCalledWith("Notification sent too soon");
      consoleSpy.mockRestore();
    });
  });

  describe("when Notification API is not supported", () => {
    beforeEach(() => {
      // Delete Notification from globalThis so "Notification" in window is false
      // @ts-expect-error deleting for test
      delete globalThis.Notification;
    });

    afterEach(() => {
      // Restore
      if (originalNotification) {
        Object.defineProperty(globalThis, "Notification", {
          value: originalNotification,
          writable: true,
          configurable: true,
        });
      }
    });

    it("reports isSupported as false", () => {
      const { result } = renderHook(() => useNotification());
      expect(result.current.isSupported).toBe(false);
    });

    it("requestPermission returns denied", async () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      const { result } = renderHook(() => useNotification());

      let permission: NotificationPermission | undefined;
      await act(async () => {
        permission = await result.current.requestPermission();
      });

      expect(permission).toBe("denied");
      expect(consoleSpy).toHaveBeenCalledWith(
        "Notification API is not supported in this browser",
      );
      consoleSpy.mockRestore();
    });

    it("showNotification warns and returns early", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification("Test");
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        "Notification API is not supported",
      );
      consoleSpy.mockRestore();
    });
  });

  describe("when notification is disabled in settings", () => {
    beforeEach(() => {
      const MockNotificationConstructor = vi.fn();
      const MockNotification = Object.assign(MockNotificationConstructor, {
        permission: "granted" as NotificationPermission,
        requestPermission: vi
          .fn()
          .mockResolvedValue("granted" as NotificationPermission),
      });

      Object.defineProperty(globalThis, "Notification", {
        value: MockNotification,
        writable: true,
        configurable: true,
      });

      // Override the mock to return disabled notifications
      mockUseLocalSettings.mockReturnValue([
        {
          notification: { enabled: false },
          tokenUsage: { headerTotal: true, inlineMode: "per_turn" as const },
          context: {
            model_name: undefined,
            mode: undefined as
              | "flash"
              | "thinking"
              | "pro"
              | "ultra"
              | undefined,
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
    });

    it("showNotification warns when disabled", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      const { result } = renderHook(() => useNotification());

      act(() => {
        vi.advanceTimersByTime(1100);
      });

      act(() => {
        result.current.showNotification("Test");
      });

      expect(consoleSpy).toHaveBeenCalledWith("Notification is disabled");
      consoleSpy.mockRestore();
    });
  });

  describe("when permission is denied", () => {
    beforeEach(() => {
      const MockNotificationConstructor = vi.fn();
      const MockNotification = Object.assign(MockNotificationConstructor, {
        permission: "denied" as NotificationPermission,
        requestPermission: vi
          .fn()
          .mockResolvedValue("denied" as NotificationPermission),
      });

      Object.defineProperty(globalThis, "Notification", {
        value: MockNotification,
        writable: true,
        configurable: true,
      });
    });

    it("reports permission as denied", () => {
      const { result } = renderHook(() => useNotification());
      expect(result.current.permission).toBe("denied");
    });

    it("showNotification warns when permission not granted", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      const { result } = renderHook(() => useNotification());

      act(() => {
        vi.advanceTimersByTime(1100);
      });

      act(() => {
        result.current.showNotification("Test");
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        "Notification permission not granted",
      );
      consoleSpy.mockRestore();
    });
  });
});
