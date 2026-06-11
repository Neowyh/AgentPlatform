import { describe, expect, test } from "vitest";

import {
  DEFAULT_LOCAL_SETTINGS,
  LOCAL_SETTINGS_KEY,
  THREAD_MODEL_KEY_PREFIX,
} from "@/core/settings/local";

test("defaults token usage to header total plus per-turn breakdown", () => {
  expect(DEFAULT_LOCAL_SETTINGS.tokenUsage).toEqual({
    headerTotal: true,
    inlineMode: "per_turn",
  });
});

describe("local settings constants", () => {
  test("LOCAL_SETTINGS_KEY uses iDeer brand", () => {
    expect(LOCAL_SETTINGS_KEY).toBe("ideer.local-settings");
  });

  test("THREAD_MODEL_KEY_PREFIX uses iDeer brand", () => {
    expect(THREAD_MODEL_KEY_PREFIX).toBe("ideer.thread-model.");
  });

  test("DEFAULT_LOCAL_SETTINGS has expected structure", () => {
    expect(DEFAULT_LOCAL_SETTINGS).toHaveProperty("notification.enabled");
    expect(DEFAULT_LOCAL_SETTINGS).toHaveProperty("tokenUsage.headerTotal");
    expect(DEFAULT_LOCAL_SETTINGS).toHaveProperty("tokenUsage.inlineMode");
    expect(DEFAULT_LOCAL_SETTINGS).toHaveProperty("context");
    expect(DEFAULT_LOCAL_SETTINGS.notification.enabled).toBe(true);
    expect(DEFAULT_LOCAL_SETTINGS.tokenUsage.headerTotal).toBe(true);
  });
});
