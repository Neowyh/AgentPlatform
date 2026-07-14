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
// Access the internal handleStorage via the window "storage" event
// by simulating StorageEvent dispatches.

describe("settings store - handleStorage (storage event handler)", () => {
  let originalWindow: typeof globalThis.window | undefined;

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
    originalWindow = globalThis.window;
  });

  function dispatchStorageEvent(
    key: string | null,
    storageArea: Storage | null = localStorage,
  ) {
    const event = new StorageEvent("storage", {
      key,
      storageArea,
    });
    window.dispatchEvent(event);
  }

  it("reloads baseSettings and clears thread models when event.key is null (storage cleared)", () => {
    const listener = vi.fn();
    subscribe(listener);

    // Change the mock to return different settings to verify reload
    mockGetLocalSettings.mockReturnValue({
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: {
        model_name: "gpt-4",
        mode: "flash",
        reasoning_effort: "low",
      },
    });

    dispatchStorageEvent(null);

    // Should have reloaded settings and notified listener
    expect(listener).toHaveBeenCalled();
    expect(mockGetLocalSettings).toHaveBeenCalled();

    const settings = getBaseSettingsSnapshot();
    expect(settings.notification.enabled).toBe(false);
  });

  it("reloads baseSettings when LOCAL_SETTINGS_KEY changes", () => {
    const listener = vi.fn();
    subscribe(listener);

    mockGetLocalSettings.mockReturnValue({
      notification: { enabled: false },
      tokenUsage: { headerTotal: true, inlineMode: "summary" },
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    });

    dispatchStorageEvent("ideer.local-settings");

    expect(listener).toHaveBeenCalled();
    const settings = getBaseSettingsSnapshot();
    expect(settings.notification.enabled).toBe(false);
  });

  it("ignores storage events from non-localStorage (e.g. sessionStorage)", () => {
    const listener = vi.fn();
    subscribe(listener);

    // Dispatch event with sessionStorage as storageArea
    const event = new StorageEvent("storage", {
      key: "ideer.local-settings",
      storageArea: sessionStorage,
    });
    window.dispatchEvent(event);

    // Listener should not be called because storageArea !== localStorage
    expect(listener).not.toHaveBeenCalled();
  });

  it("updates thread model name when thread model key changes", () => {
    const threadId = "test-thread-123";
    const listener = vi.fn();
    subscribe(listener);

    mockGetThreadModelName.mockReturnValue("claude-3-opus");

    dispatchStorageEvent(`ideer.thread-model.${threadId}`);

    expect(listener).toHaveBeenCalled();
    expect(mockGetThreadModelName).toHaveBeenCalledWith(threadId);

    const model = getThreadModelSnapshot(threadId);
    expect(model).toBe("claude-3-opus");
  });

  it("ignores storage events with unrelated keys", () => {
    const listener = vi.fn();
    subscribe(listener);

    dispatchStorageEvent("some-other-key");

    // Only the subscribe call would trigger, not this event
    expect(listener).not.toHaveBeenCalled();
  });

  it("getThreadModelSnapshot caches and returns value for known thread", () => {
    mockGetThreadModelName.mockReturnValue("gpt-4-turbo");

    const model1 = getThreadModelSnapshot("thread-cache-test");
    expect(model1).toBe("gpt-4-turbo");

    // Second call should use cached value
    const model2 = getThreadModelSnapshot("thread-cache-test");
    expect(model2).toBe("gpt-4-turbo");
  });

  it("updateThreadSettings with context and model_name updates thread model cache", () => {
    const threadId = "thread-update-test";

    updateThreadSettings(threadId, "context", {
      model_name: "claude-3-sonnet",
    });

    expect(mockSaveThreadModelName).toHaveBeenCalledWith(
      threadId,
      "claude-3-sonnet",
    );
  });

  it("updateThreadSettings with context but without model_name does not save thread model", () => {
    mockSaveThreadModelName.mockClear();

    updateThreadSettings("thread-no-model", "context", {
      mode: "pro",
    });

    expect(mockSaveThreadModelName).not.toHaveBeenCalled();
  });

  it("updateThreadSettings notifies all listeners", () => {
    const listener1 = vi.fn();
    const listener2 = vi.fn();
    const listener3 = vi.fn();

    subscribe(listener1);
    subscribe(listener2);
    subscribe(listener3);

    updateThreadSettings("thread-notify", "notification", { enabled: false });

    expect(listener1).toHaveBeenCalledTimes(1);
    expect(listener2).toHaveBeenCalledTimes(1);
    expect(listener3).toHaveBeenCalledTimes(1);
  });

  it("unsubscribe removes listener and they stop being notified", () => {
    const listener1 = vi.fn();
    const listener2 = vi.fn();

    const unsub1 = subscribe(listener1);
    subscribe(listener2);

    unsub1();

    updateLocalSettings("notification", { enabled: false });

    expect(listener1).not.toHaveBeenCalled();
    expect(listener2).toHaveBeenCalledTimes(1);
  });
});
