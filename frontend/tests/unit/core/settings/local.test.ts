import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  DEFAULT_LOCAL_SETTINGS,
  LOCAL_SETTINGS_KEY,
  THREAD_MODEL_KEY_PREFIX,
  applyThreadModelOverride,
  getLocalSettings,
  getThreadModelName,
  saveLocalSettings,
  saveThreadModelName,
  type LocalSettings,
} from "@/core/settings/local";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

const LEGACY_SETTINGS_KEY = "deerflow.local-settings";
const LEGACY_THREAD_MODEL_PREFIX = "deerflow.thread-model.";

function resetLocalStorage() {
  localStorage.clear();
}

// ---------------------------------------------------------------------------
// constants
// ---------------------------------------------------------------------------

describe("exported constants", () => {
  test("LOCAL_SETTINGS_KEY uses iDeer brand", () => {
    expect(LOCAL_SETTINGS_KEY).toBe("ideer.local-settings");
  });

  test("THREAD_MODEL_KEY_PREFIX uses iDeer brand", () => {
    expect(THREAD_MODEL_KEY_PREFIX).toBe("ideer.thread-model.");
  });

  test("DEFAULT_LOCAL_SETTINGS has correct structure and values", () => {
    expect(DEFAULT_LOCAL_SETTINGS).toEqual({
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    });
  });

  test("DEFAULT_LOCAL_SETTINGS.notification.enabled defaults to true", () => {
    expect(DEFAULT_LOCAL_SETTINGS.notification.enabled).toBe(true);
  });

  test("DEFAULT_LOCAL_SETTINGS.tokenUsage.headerTotal defaults to true", () => {
    expect(DEFAULT_LOCAL_SETTINGS.tokenUsage.headerTotal).toBe(true);
  });

  test("DEFAULT_LOCAL_SETTINGS.tokenUsage.inlineMode defaults to per_turn", () => {
    expect(DEFAULT_LOCAL_SETTINGS.tokenUsage.inlineMode).toBe("per_turn");
  });

  test("DEFAULT_LOCAL_SETTINGS.context.model_name defaults to undefined", () => {
    expect(DEFAULT_LOCAL_SETTINGS.context.model_name).toBeUndefined();
  });

  test("DEFAULT_LOCAL_SETTINGS.context.mode defaults to undefined", () => {
    expect(DEFAULT_LOCAL_SETTINGS.context.mode).toBeUndefined();
  });

  test("DEFAULT_LOCAL_SETTINGS.context.reasoning_effort defaults to undefined", () => {
    expect(DEFAULT_LOCAL_SETTINGS.context.reasoning_effort).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// getLocalSettings
// ---------------------------------------------------------------------------

describe("getLocalSettings", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("returns DEFAULT_LOCAL_SETTINGS when localStorage is empty", () => {
    expect(getLocalSettings()).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("returns settings from localStorage when valid JSON exists", () => {
    const custom: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: {
        model_name: "gpt-4",
        mode: "thinking",
        reasoning_effort: "high",
      },
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(custom));

    const result = getLocalSettings();
    expect(result).toEqual(custom);
  });

  test("merges partial settings from localStorage with defaults", () => {
    const partial = { notification: { enabled: false } };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(partial));

    const result = getLocalSettings();
    expect(result.notification.enabled).toBe(false);
    // Other sections should keep defaults
    expect(result.tokenUsage).toEqual(DEFAULT_LOCAL_SETTINGS.tokenUsage);
    expect(result.context).toEqual(DEFAULT_LOCAL_SETTINGS.context);
  });

  test("merges partial tokenUsage with defaults", () => {
    const partial = { tokenUsage: { inlineMode: "step_debug" as const } };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(partial));

    const result = getLocalSettings();
    expect(result.tokenUsage.inlineMode).toBe("step_debug");
    expect(result.tokenUsage.headerTotal).toBe(true); // default preserved
  });

  test("merges partial context with defaults", () => {
    const partial = { context: { mode: "ultra" as const } };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(partial));

    const result = getLocalSettings();
    expect(result.context.mode).toBe("ultra");
    expect(result.context.model_name).toBeUndefined();
    expect(result.context.reasoning_effort).toBeUndefined();
  });

  test("returns DEFAULT_LOCAL_SETTINGS when localStorage contains invalid JSON", () => {
    localStorage.setItem(LOCAL_SETTINGS_KEY, "not-valid-json{{{");

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("returns DEFAULT_LOCAL_SETTINGS when localStorage contains empty string", () => {
    localStorage.setItem(LOCAL_SETTINGS_KEY, "");

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("migrates from legacy key when new key is empty", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: { model_name: "claude-3", mode: "pro", reasoning_effort: "low" },
    };
    localStorage.setItem(LEGACY_SETTINGS_KEY, JSON.stringify(settings));

    const result = getLocalSettings();
    expect(result).toEqual(settings);
    // New key should now have the migrated value
    expect(localStorage.getItem(LOCAL_SETTINGS_KEY)).toBe(
      JSON.stringify(settings),
    );
    // Legacy key should be removed
    expect(localStorage.getItem(LEGACY_SETTINGS_KEY)).toBeNull();
  });

  test("uses legacy value directly when migration write fails (e.g. quota)", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: false },
    };
    localStorage.setItem(LEGACY_SETTINGS_KEY, JSON.stringify(settings));

    // Mock setItem to throw QuotaExceededError on the new key
    const originalSetItem = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn((key: string, value: string) => {
      if (key === LOCAL_SETTINGS_KEY) {
        callCount++;
        // Only throw on first call (migration attempt)
        if (callCount === 1) {
          throw new DOMException("QuotaExceededError", "QuotaExceededError");
        }
      }
      originalSetItem.call(localStorage, key, value);
    });

    try {
      const result = getLocalSettings();
      expect(result).toEqual(settings);
    } finally {
      Storage.prototype.setItem = originalSetItem;
    }
  });

  test("does not migrate when legacy key also has null", () => {
    // Both keys empty
    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
    expect(localStorage.getItem(LOCAL_SETTINGS_KEY)).toBeNull();
  });

  test("returns defaults when both new and legacy keys exist (new takes precedence)", () => {
    const newSettings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: false },
    };
    const legacySettings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: true },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(newSettings));
    localStorage.setItem(LEGACY_SETTINGS_KEY, JSON.stringify(legacySettings));

    const result = getLocalSettings();
    // New key takes precedence
    expect(result.notification.enabled).toBe(false);
    expect(result.tokenUsage).toEqual(DEFAULT_LOCAL_SETTINGS.tokenUsage);
  });

  test("handles settings with all context fields populated", () => {
    const settings: LocalSettings = {
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "step_debug" },
      context: {
        model_name: "deepseek-r1",
        mode: "thinking",
        reasoning_effort: "high",
      },
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(settings));

    const result = getLocalSettings();
    expect(result).toEqual(settings);
  });

  test("handles settings with all context fields undefined", () => {
    const settings: Partial<LocalSettings> = {
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(settings));

    const result = getLocalSettings();
    expect(result.context.model_name).toBeUndefined();
    expect(result.context.mode).toBeUndefined();
    expect(result.context.reasoning_effort).toBeUndefined();
  });

  test("handles empty object in localStorage (merges all defaults)", () => {
    localStorage.setItem(LOCAL_SETTINGS_KEY, "{}");

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("preserves non-standard JSON values in notification section", () => {
    const settings = { notification: { enabled: true, extraProp: "hello" } };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(settings));

    const result = getLocalSettings();
    expect(result.notification.enabled).toBe(true);
    // extraProp should be preserved through spread
    expect((result.notification as Record<string, unknown>).extraProp).toBe(
      "hello",
    );
  });

  test("returns defaults when JSON parse returns non-object", () => {
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify("just a string"));

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("returns defaults when JSON parse returns a number", () => {
    localStorage.setItem(LOCAL_SETTINGS_KEY, "42");

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });
});

// ---------------------------------------------------------------------------
// saveLocalSettings
// ---------------------------------------------------------------------------

describe("saveLocalSettings", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("persists settings to localStorage", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "step_debug" },
      context: {
        model_name: "gpt-4o",
        mode: "ultra",
        reasoning_effort: "medium",
      },
    };

    saveLocalSettings(settings);

    const stored = localStorage.getItem(LOCAL_SETTINGS_KEY);
    expect(stored).toBe(JSON.stringify(settings));
  });

  test("overwrites previous settings", () => {
    const first: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: false },
    };
    const second: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: true },
    };

    saveLocalSettings(first);
    saveLocalSettings(second);

    const stored = JSON.parse(localStorage.getItem(LOCAL_SETTINGS_KEY)!);
    expect(stored.notification.enabled).toBe(true);
  });

  test("saves settings with all fields", () => {
    const settings: LocalSettings = {
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "off" },
      context: { model_name: "claude-3", mode: "pro", reasoning_effort: "low" },
    };

    saveLocalSettings(settings);

    const stored = JSON.parse(localStorage.getItem(LOCAL_SETTINGS_KEY)!);
    expect(stored).toEqual(settings);
  });

  test("round-trips through getLocalSettings", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: {
        model_name: "deepseek-r1",
        mode: "thinking",
        reasoning_effort: "high",
      },
    };

    saveLocalSettings(settings);
    const loaded = getLocalSettings();
    expect(loaded).toEqual(settings);
  });
});

// ---------------------------------------------------------------------------
// getThreadModelName
// ---------------------------------------------------------------------------

describe("getThreadModelName", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("returns undefined when thread model is not stored", () => {
    expect(getThreadModelName("thread-123")).toBeUndefined();
  });

  test("returns the stored model name", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}thread-abc`, "gpt-4o");

    expect(getThreadModelName("thread-abc")).toBe("gpt-4o");
  });

  test("returns undefined for empty string thread ID with no stored value", () => {
    expect(getThreadModelName("")).toBeUndefined();
  });

  test("returns stored model for empty string thread ID", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}`, "some-model");

    expect(getThreadModelName("")).toBe("some-model");
  });

  test("migrates from legacy key when new key is empty", () => {
    localStorage.setItem(
      `${LEGACY_THREAD_MODEL_PREFIX}thread-x`,
      "deepseek-v3",
    );

    const result = getThreadModelName("thread-x");
    expect(result).toBe("deepseek-v3");
    // New key should have the migrated value
    expect(localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}thread-x`)).toBe(
      "deepseek-v3",
    );
    // Legacy key should be removed
    expect(
      localStorage.getItem(`${LEGACY_THREAD_MODEL_PREFIX}thread-x`),
    ).toBeNull();
  });

  test("uses legacy value directly when migration write fails", () => {
    localStorage.setItem(`${LEGACY_THREAD_MODEL_PREFIX}thread-y`, "qwen-72b");

    const originalSetItem = Storage.prototype.setItem;
    let callCount = 0;
    Storage.prototype.setItem = vi.fn((key: string, value: string) => {
      if (key === `${THREAD_MODEL_KEY_PREFIX}thread-y`) {
        callCount++;
        if (callCount === 1) {
          throw new DOMException("QuotaExceededError", "QuotaExceededError");
        }
      }
      originalSetItem.call(localStorage, key, value);
    });

    try {
      const result = getThreadModelName("thread-y");
      expect(result).toBe("qwen-72b");
    } finally {
      Storage.prototype.setItem = originalSetItem;
    }
  });

  test("returns new key value when both new and legacy keys exist", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}thread-z`, "new-model");
    localStorage.setItem(`${LEGACY_THREAD_MODEL_PREFIX}thread-z`, "old-model");

    const result = getThreadModelName("thread-z");
    expect(result).toBe("new-model");
  });

  test("returns stored value even when it is an empty string", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}thread-empty`, "");

    const result = getThreadModelName("thread-empty");
    // empty string is not null, so it should be returned as-is
    expect(result).toBe("");
  });

  test("handles special characters in thread ID", () => {
    const threadId = "thread/with/slashes&special=chars";
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}${threadId}`, "gpt-4");

    expect(getThreadModelName(threadId)).toBe("gpt-4");
  });
});

// ---------------------------------------------------------------------------
// saveThreadModelName
// ---------------------------------------------------------------------------

describe("saveThreadModelName", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("stores model name in localStorage", () => {
    saveThreadModelName("thread-1", "gpt-4o");

    expect(localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}thread-1`)).toBe(
      "gpt-4o",
    );
  });

  test("removes model name when undefined is passed", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}thread-2`, "old-model");

    saveThreadModelName("thread-2", undefined);

    expect(
      localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}thread-2`),
    ).toBeNull();
  });

  test("removes model name when empty string is passed (falsy)", () => {
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}thread-3`, "old-model");

    saveThreadModelName("thread-3", "");

    expect(
      localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}thread-3`),
    ).toBeNull();
  });

  test("overwrites existing model name", () => {
    saveThreadModelName("thread-4", "gpt-4");
    saveThreadModelName("thread-4", "claude-3");

    expect(localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}thread-4`)).toBe(
      "claude-3",
    );
  });

  test("stores with correct key prefix", () => {
    saveThreadModelName("my-thread", "deepseek-r1");

    const keys = Object.keys(localStorage);
    expect(keys).toContain("ideer.thread-model.my-thread");
  });

  test("handles empty string thread ID", () => {
    saveThreadModelName("", "gpt-4o");

    expect(localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}`)).toBe("gpt-4o");
  });

  test("handles special characters in thread ID", () => {
    const threadId = "thread/with/slashes&special=chars";
    saveThreadModelName(threadId, "gpt-4");

    expect(localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}${threadId}`)).toBe(
      "gpt-4",
    );
  });

  test("remove is idempotent when key does not exist", () => {
    // Should not throw
    saveThreadModelName("nonexistent", undefined);
    expect(
      localStorage.getItem(`${THREAD_MODEL_KEY_PREFIX}nonexistent`),
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// applyThreadModelOverride
// ---------------------------------------------------------------------------

describe("applyThreadModelOverride", () => {
  test("returns original settings when threadModelName is undefined", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: { model_name: "gpt-4", mode: "pro", reasoning_effort: "high" },
    };

    const result = applyThreadModelOverride(settings, undefined);
    expect(result).toBe(settings); // same reference
    expect(result.context.model_name).toBe("gpt-4");
  });

  test("returns original settings when threadModelName is empty string", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: { model_name: "gpt-4", mode: "pro", reasoning_effort: "high" },
    };

    const result = applyThreadModelOverride(settings, "");
    expect(result).toBe(settings); // same reference
  });

  test("overrides model_name while preserving other context fields", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: true, inlineMode: "off" },
      context: {
        model_name: "gpt-4",
        mode: "thinking",
        reasoning_effort: "high",
      },
    };

    const result = applyThreadModelOverride(settings, "deepseek-r1");
    expect(result.context.model_name).toBe("deepseek-r1");
    expect(result.context.mode).toBe("thinking");
    expect(result.context.reasoning_effort).toBe("high");
  });

  test("overrides model_name even when it was undefined", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    };

    const result = applyThreadModelOverride(settings, "claude-3");
    expect(result.context.model_name).toBe("claude-3");
    expect(result.context.mode).toBeUndefined();
  });

  test("preserves notification and tokenUsage sections", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "step_debug" },
      context: { model_name: "gpt-4", mode: "pro", reasoning_effort: "low" },
    };

    const result = applyThreadModelOverride(settings, "new-model");
    expect(result.notification).toEqual({ enabled: false });
    expect(result.tokenUsage).toEqual({
      headerTotal: false,
      inlineMode: "step_debug",
    });
  });

  test("returns a new object (does not mutate input)", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: {
        model_name: "old-model",
        mode: "pro",
        reasoning_effort: "high",
      },
    };

    const result = applyThreadModelOverride(settings, "new-model");
    expect(result).not.toBe(settings);
    expect(settings.context.model_name).toBe("old-model"); // original unchanged
  });

  test("handles settings with all context fields as undefined", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    };

    const result = applyThreadModelOverride(settings, "test-model");
    expect(result).toEqual({
      ...DEFAULT_LOCAL_SETTINGS,
      context: {
        model_name: "test-model",
        mode: undefined,
        reasoning_effort: undefined,
      },
    });
  });

  test("handles settings with partial context (missing reasoning_effort)", () => {
    const settings: Partial<LocalSettings> = {
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
      context: { model_name: undefined, mode: "flash" },
    };

    const result = applyThreadModelOverride(
      settings as LocalSettings,
      "gpt-4o",
    );
    expect(result.context.model_name).toBe("gpt-4o");
    expect(result.context.mode).toBe("flash");
  });
});

// ---------------------------------------------------------------------------
// round-trip integration: save then load
// ---------------------------------------------------------------------------

describe("round-trip integration", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("saveLocalSettings -> getLocalSettings preserves all fields", () => {
    const settings: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: {
        model_name: "deepseek-r1",
        mode: "ultra",
        reasoning_effort: "high",
      },
    };

    saveLocalSettings(settings);
    const loaded = getLocalSettings();
    expect(loaded).toEqual(settings);
  });

  test("saveThreadModelName -> getThreadModelName preserves value", () => {
    saveThreadModelName("t1", "claude-3");
    expect(getThreadModelName("t1")).toBe("claude-3");
  });

  test("saveThreadModelName(undefined) -> getThreadModelName returns undefined", () => {
    saveThreadModelName("t2", "gpt-4");
    saveThreadModelName("t2", undefined);
    expect(getThreadModelName("t2")).toBeUndefined();
  });

  test("multiple threads have independent model names", () => {
    saveThreadModelName("t-a", "gpt-4");
    saveThreadModelName("t-b", "claude-3");

    expect(getThreadModelName("t-a")).toBe("gpt-4");
    expect(getThreadModelName("t-b")).toBe("claude-3");

    saveThreadModelName("t-a", undefined);
    expect(getThreadModelName("t-a")).toBeUndefined();
    expect(getThreadModelName("t-b")).toBe("claude-3"); // unaffected
  });

  test("applyThreadModelOverride -> saveLocalSettings -> getLocalSettings round-trip", () => {
    const base: LocalSettings = {
      notification: { enabled: true },
      tokenUsage: { headerTotal: true, inlineMode: "per_turn" },
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    };

    const overridden = applyThreadModelOverride(base, "gpt-4o");
    saveLocalSettings(overridden);
    const loaded = getLocalSettings();

    expect(loaded.context.model_name).toBe("gpt-4o");
    expect(loaded.notification).toEqual({ enabled: true });
    expect(loaded.tokenUsage).toEqual({
      headerTotal: true,
      inlineMode: "per_turn",
    });
  });
});

// ---------------------------------------------------------------------------
// edge cases & boundary conditions
// ---------------------------------------------------------------------------

describe("edge cases", () => {
  beforeEach(() => {
    resetLocalStorage();
  });

  test("getLocalSettings handles very large JSON payload", () => {
    const bigContext: Record<string, string> = {};
    for (let i = 0; i < 1000; i++) {
      bigContext[`key${i}`] = `value${i}`;
    }
    const settings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: { ...DEFAULT_LOCAL_SETTINGS.context, ...bigContext },
    };
    localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(settings));

    const result = getLocalSettings();
    expect(result.context).toEqual(settings.context);
  });

  test("getThreadModelName with very long thread ID", () => {
    const longId = "x".repeat(500);
    localStorage.setItem(`${THREAD_MODEL_KEY_PREFIX}${longId}`, "model");

    expect(getThreadModelName(longId)).toBe("model");
  });

  test("saveThreadModelName with unicode model name", () => {
    saveThreadModelName("t-unicode", "модель-7Б");
    expect(getThreadModelName("t-unicode")).toBe("модель-7Б");
  });

  test("saveLocalSettings with unicode characters", () => {
    const settings: LocalSettings = {
      ...DEFAULT_LOCAL_SETTINGS,
      context: {
        model_name: "测试模型",
        mode: "thinking",
        reasoning_effort: "medium",
      },
    };
    saveLocalSettings(settings);

    const loaded = getLocalSettings();
    expect(loaded.context.model_name).toBe("测试模型");
  });

  test("consecutive saveLocalSettings calls are independent", () => {
    saveLocalSettings({
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: false },
    });
    saveLocalSettings({
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: true },
    });

    expect(getLocalSettings().notification.enabled).toBe(true);
  });

  test("localStorage with malformed legacy key triggers fallback to defaults", () => {
    localStorage.setItem(LEGACY_SETTINGS_KEY, "}{invalid json");
    localStorage.setItem(LOCAL_SETTINGS_KEY, ""); // empty so it tries legacy

    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("applyThreadModelOverride with model_name containing special chars", () => {
    const settings: LocalSettings = { ...DEFAULT_LOCAL_SETTINGS };
    const result = applyThreadModelOverride(
      settings,
      "model/with:special@chars",
    );

    expect(result.context.model_name).toBe("model/with:special@chars");
  });

  test("saveLocalSettings then getLocalSettings with minimal valid settings", () => {
    const minimal: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "off" },
      context: {
        model_name: undefined,
        mode: undefined,
        reasoning_effort: undefined,
      },
    };
    saveLocalSettings(minimal);
    expect(getLocalSettings()).toEqual(minimal);
  });

  test("getLocalSettings handles legacy key with partial JSON", () => {
    localStorage.setItem(
      LEGACY_SETTINGS_KEY,
      JSON.stringify({ notification: { enabled: false } }),
    );

    const result = getLocalSettings();
    // Should merge with defaults
    expect(result.notification.enabled).toBe(false);
    expect(result.tokenUsage).toEqual(DEFAULT_LOCAL_SETTINGS.tokenUsage);
  });

  test("getLocalSettings handles deeply nested legacy settings", () => {
    const legacy: LocalSettings = {
      notification: { enabled: false },
      tokenUsage: { headerTotal: false, inlineMode: "step_debug" },
      context: { model_name: "model-1", mode: "pro", reasoning_effort: "high" },
    };
    localStorage.setItem(LEGACY_SETTINGS_KEY, JSON.stringify(legacy));

    const result = getLocalSettings();
    expect(result).toEqual(legacy);
    // Verify migration happened
    expect(localStorage.getItem(LOCAL_SETTINGS_KEY)).toBe(
      JSON.stringify(legacy),
    );
    expect(localStorage.getItem(LEGACY_SETTINGS_KEY)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// SSR (server-side rendering) branches — isBrowser() returns false
// ---------------------------------------------------------------------------

describe("SSR branches (isBrowser returns false)", () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    delete (globalThis as Record<string, unknown>).window;
  });

  afterEach(() => {
    globalThis.window = originalWindow;
  });

  test("getLocalSettings returns DEFAULT_LOCAL_SETTINGS when window is undefined", () => {
    const result = getLocalSettings();
    expect(result).toEqual(DEFAULT_LOCAL_SETTINGS);
  });

  test("saveLocalSettings does nothing when window is undefined", () => {
    // Should not throw
    saveLocalSettings({
      ...DEFAULT_LOCAL_SETTINGS,
      notification: { enabled: false },
    });
  });

  test("getThreadModelName returns undefined when window is undefined", () => {
    expect(getThreadModelName("thread-ssr")).toBeUndefined();
  });

  test("saveThreadModelName does nothing when window is undefined", () => {
    // Should not throw
    saveThreadModelName("thread-ssr", "gpt-4");
  });
});
