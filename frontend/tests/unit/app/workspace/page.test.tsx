import { describe, expect, test, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- declared before component imports
// ---------------------------------------------------------------------------

const mockRedirect = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

import { DEMO_THREAD_IDS } from "@/core/threads/static-demo";

let mockStaticWebsiteOnly = false;

vi.mock("@/env", () => ({
  env: {
    get NEXT_PUBLIC_STATIC_WEBSITE_ONLY() {
      return mockStaticWebsiteOnly ? "true" : undefined;
    },
  },
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import WorkspacePage from "@/app/workspace/page";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WorkspacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStaticWebsiteOnly = false;
  });

  // ── Static website mode ────────────────────────────────────────────────

  test("redirects to the first demo thread when static website only", () => {
    mockStaticWebsiteOnly = true;

    WorkspacePage();

    expect(mockRedirect).toHaveBeenCalledTimes(1);
    expect(mockRedirect).toHaveBeenCalledWith(
      `/workspace/chats/${DEMO_THREAD_IDS[0]}`,
    );
  });

  test("still redirects to the demo thread when the flag is exactly 'true'", () => {
    mockStaticWebsiteOnly = true;

    WorkspacePage();

    expect(mockRedirect).toHaveBeenCalledWith(
      `/workspace/chats/${DEMO_THREAD_IDS[0]}`,
    );
  });

  // ── Normal mode ─────────────────────────────────────────────────────────

  test("redirects to /workspace/chats/new when not in static mode", () => {
    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("calls redirect exactly once in non-static mode", () => {
    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledTimes(1);
  });

  test("redirects to /workspace/chats/new when the flag is set but not 'true'", () => {
    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });
});
