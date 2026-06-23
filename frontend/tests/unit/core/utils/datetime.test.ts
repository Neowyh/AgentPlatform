import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n", () => ({
  detectLocale: vi.fn(() => "en-US"),
}));

vi.mock("@/core/i18n/cookies", () => ({
  getLocaleFromCookie: vi.fn(() => null),
}));

import { detectLocale } from "@/core/i18n";
import { getLocaleFromCookie } from "@/core/i18n/cookies";
import { formatTimeAgo } from "@/core/utils/datetime";

describe("formatTimeAgo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-13T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  test("formats a recent Date object with English locale", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo);
    expect(result).toContain("5 minutes ago");
  });

  test("formats a string date with English locale", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    const result = formatTimeAgo("2026-06-13T11:55:00Z");
    expect(result).toContain("5 minutes ago");
  });

  test("formats a numeric timestamp with English locale", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    const ts = new Date("2026-06-13T11:55:00Z").getTime();
    const result = formatTimeAgo(ts);
    expect(result).toContain("5 minutes ago");
  });

  test("uses Chinese locale when explicitly passed", () => {
    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo, "zh-CN");
    expect(result).toContain("5 分钟");
  });

  test("uses English locale when explicitly passed", () => {
    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo, "en-US");
    expect(result).toContain("5 minutes ago");
  });

  test("prefers locale parameter over cookie locale", () => {
    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo, "zh-CN");
    expect(result).toContain("5 分钟");
    // detectLocale should NOT have been called since explicit locale takes precedence
    expect(detectLocale).not.toHaveBeenCalled();
  });

  test("falls back to detectLocale when cookie is null", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo);
    expect(detectLocale).toHaveBeenCalled();
    expect(result).toContain("5 minutes ago");
  });

  test("uses cookie locale when available", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue("zh-CN");

    const fiveMinAgo = new Date("2026-06-13T11:55:00Z");
    const result = formatTimeAgo(fiveMinAgo);
    expect(result).toContain("5 分钟");
    // detectLocale should NOT have been called since cookie locale takes precedence
    expect(detectLocale).not.toHaveBeenCalled();
  });

  test("formats a date just now (less than a minute ago)", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    // 10 seconds ago should show "less than a minute"
    const now = new Date("2026-06-13T11:59:50Z");
    const result = formatTimeAgo(now);
    expect(result).toContain("less than a minute");
  });

  test("formats a date several hours ago", () => {
    (getLocaleFromCookie as ReturnType<typeof vi.fn>).mockReturnValue(null);
    (detectLocale as ReturnType<typeof vi.fn>).mockReturnValue("en-US");

    const threeHoursAgo = new Date("2026-06-13T09:00:00Z");
    const result = formatTimeAgo(threeHoursAgo);
    expect(result).toContain("3 hours ago");
  });
});
