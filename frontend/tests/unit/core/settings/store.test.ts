import { describe, expect, it, vi, beforeEach } from "vitest";

// Use vi.hoisted so the mock references are available when vi.mock is hoisted
const {
  mockGetLocalSettings,
  mockGetThreadModelName,
  mockSaveLocalSettings,
  mockSaveThreadModelName,
} = vi.hoisted(() => ({
  mockGetLocalSettings: vi.fn().mockReturnValue({
    notification: { enabled: true },
    tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
    context: {
      model_name: undefined,
      mode: undefined,
      reasoning_effort: undefined,
    },
  }),
  mockGetThreadModelName: vi.fn().mockReturnValue(undefined),
  mockSaveLocalSettings: vi.fn(),
  mockSaveThreadModelName: vi.fn(),
}));

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
  LOCAL_SETTINGS_KEY: "ideer.local-settings",
  THREAD_MODEL_KEY_PREFIX: "ideer.thread-model.",
  getLocalSettings: mockGetLocalSettings,
  getThreadModelName: mockGetThreadModelName,
  saveLocalSettings: mockSaveLocalSettings,
  saveThreadModelName: mockSaveThreadModelName,
}));

import {
  subscribe,
  getBaseSettingsSnapshot,
  getThreadModelSnapshot,
  updateLocalSettings,
  updateThreadSettings,
} from "@/core/settings/store";

describe("settings store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetLocalSettings.mockReturnValue({
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    });
    mockGetThreadModelName.mockReturnValue(undefined);
  });

  describe("subscribe", () => {
    it("returns an unsubscribe function", () => {
      const listener = vi.fn();
      const unsubscribe = subscribe(listener);
      expect(typeof unsubscribe).toBe("function");
      unsubscribe();
    });

    it("calls listener when settings change", () => {
      const listener = vi.fn();
      subscribe(listener);

      updateLocalSettings("notification", { enabled: false });

      expect(listener).toHaveBeenCalled();
    });

    it("does not call listener after unsubscribe", () => {
      const listener = vi.fn();
      const unsubscribe = subscribe(listener);
      unsubscribe();

      updateLocalSettings("notification", { enabled: false });

      expect(listener).not.toHaveBeenCalled();
    });

    it("supports multiple listeners", () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();
      subscribe(listener1);
      subscribe(listener2);

      updateLocalSettings("notification", { enabled: false });

      expect(listener1).toHaveBeenCalled();
      expect(listener2).toHaveBeenCalled();
    });
  });

  describe("getBaseSettingsSnapshot", () => {
    it("returns settings with expected structure", () => {
      const settings = getBaseSettingsSnapshot();
      expect(settings).toHaveProperty("notification");
      expect(settings).toHaveProperty("tokenUsage");
      expect(settings).toHaveProperty("context");
      expect(settings.notification).toHaveProperty("enabled");
    });
  });

  describe("getThreadModelSnapshot", () => {
    it("returns undefined for unknown thread", () => {
      mockGetThreadModelName.mockReturnValue(undefined);
      const result = getThreadModelSnapshot("thread-unknown-" + Date.now());
      expect(result).toBeUndefined();
    });

    it("returns model name when set for thread", () => {
      const threadId = "thread-" + Date.now();
      mockGetThreadModelName.mockReturnValue("gpt-4");
      const result = getThreadModelSnapshot(threadId);
      expect(result).toBe("gpt-4");
    });
  });

  describe("updateLocalSettings", () => {
    it("merges notification settings", () => {
      updateLocalSettings("notification", { enabled: false });

      const settings = getBaseSettingsSnapshot();
      expect(settings.notification.enabled).toBe(false);
    });

    it("saves settings to localStorage", () => {
      updateLocalSettings("notification", { enabled: false });

      expect(mockSaveLocalSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          notification: { enabled: false },
        }),
      );
    });

    it("merges tokenUsage settings", () => {
      updateLocalSettings("tokenUsage", { headerTotal: false });

      const settings = getBaseSettingsSnapshot();
      expect(settings.tokenUsage.headerTotal).toBe(false);
    });

    it("notifies listeners on update", () => {
      const listener = vi.fn();
      subscribe(listener);

      updateLocalSettings("notification", { enabled: false });

      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe("updateThreadSettings", () => {
    it("updates base settings and saves to localStorage", () => {
      updateThreadSettings("thread-1", "notification", { enabled: false });

      const settings = getBaseSettingsSnapshot();
      expect(settings.notification.enabled).toBe(false);
      expect(mockSaveLocalSettings).toHaveBeenCalled();
    });

    it("saves thread model name when updating context.model_name", () => {
      updateThreadSettings("thread-1", "context", {
        model_name: "gpt-4",
      });

      expect(mockSaveThreadModelName).toHaveBeenCalledWith("thread-1", "gpt-4");
    });

    it("does not save thread model name when model_name is not in value", () => {
      mockSaveThreadModelName.mockClear();

      updateThreadSettings("thread-1", "context", {
        mode: "thinking",
      });

      expect(mockSaveThreadModelName).not.toHaveBeenCalled();
    });

    it("notifies listeners on update", () => {
      const listener = vi.fn();
      subscribe(listener);

      updateThreadSettings("thread-1", "notification", { enabled: false });

      expect(listener).toHaveBeenCalledTimes(1);
    });
  });
});
