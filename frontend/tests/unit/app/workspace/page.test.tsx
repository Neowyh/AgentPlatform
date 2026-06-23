import { describe, expect, test, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- declared before component imports
// ---------------------------------------------------------------------------

const mockRedirect = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => mockRedirect(...args),
}));

let mockStaticWebsiteOnly = false;

vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: () => mockStaticWebsiteOnly,
}));

vi.mock("@/env", () => ({
  env: {
    get NEXT_PUBLIC_STATIC_WEBSITE_ONLY() {
      return mockStaticWebsiteOnly ? "true" : undefined;
    },
  },
}));

// Mock fs and path for static mode
const mockReaddirSync = vi.fn();

vi.mock("fs", () => ({
  default: {
    readdirSync: (...args: unknown[]) => mockReaddirSync(...args),
  },
}));

const mockResolve = vi.fn((_cwd: string, p: string) => `/resolved/${p}`);

vi.mock("path", () => ({
  default: {
    resolve: (cwd: string, p: string) => mockResolve(cwd, p),
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
    // Default: resolve returns a sensible path
    mockResolve.mockImplementation(
      (_cwd: string, p: string) => `/resolved/${p}`,
    );
  });

  // ── Default (non-static) mode ─────────────────────────────────────────

  test("redirects to /workspace/chats/new when not in static mode", () => {
    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("calls redirect exactly once in non-static mode", () => {
    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledTimes(1);
  });

  // ── Static mode: no threads directory or empty ────────────────────────

  test("redirects to /workspace/chats/new when static mode but no threads found", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("redirects to /workspace/chats/new when static mode but only hidden dirs", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([
      { name: ".hidden", isDirectory: () => true },
      { name: ".git", isDirectory: () => true },
    ]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("redirects to /workspace/chats/new when static mode but only files (no dirs)", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([
      { name: "readme.md", isDirectory: () => false },
      { name: "config.json", isDirectory: () => false },
    ]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/new");
  });

  // ── Static mode: threads found ────────────────────────────────────────

  test("redirects to first non-hidden thread directory in static mode", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([
      { name: ".hidden", isDirectory: () => true },
      { name: "thread-abc", isDirectory: () => true },
      { name: "thread-def", isDirectory: () => true },
    ]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/thread-abc");
  });

  test("picks the first directory among multiple non-hidden ones", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([
      { name: "zzz-thread", isDirectory: () => true },
      { name: "aaa-thread", isDirectory: () => true },
    ]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/zzz-thread");
  });

  test("skips files and picks the first directory", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([
      { name: "notes.md", isDirectory: () => false },
      { name: "my-chat", isDirectory: () => true },
    ]);

    WorkspacePage();
    expect(mockRedirect).toHaveBeenCalledWith("/workspace/chats/my-chat");
  });

  // ── Static mode: directory reading ────────────────────────────────────

  test("reads from public/demo/threads in static mode", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([]);

    WorkspacePage();
    expect(mockReaddirSync).toHaveBeenCalledWith(
      "/resolved/public/demo/threads",
      {
        withFileTypes: true,
      },
    );
  });

  test("uses process.cwd() as base for path.resolve", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([]);

    WorkspacePage();
    expect(mockResolve).toHaveBeenCalledWith(
      expect.any(String),
      "public/demo/threads",
    );
  });

  // ── Static mode: edge cases ───────────────────────────────────────────

  test("only reads directory when NEXT_PUBLIC_STATIC_WEBSITE_ONLY is 'true'", () => {
    mockStaticWebsiteOnly = true;
    mockReaddirSync.mockReturnValue([]);

    WorkspacePage();
    expect(mockReaddirSync).toHaveBeenCalled();
  });

  test("does NOT read filesystem when NEXT_PUBLIC_STATIC_WEBSITE_ONLY is not 'true'", () => {
    mockStaticWebsiteOnly = false;

    WorkspacePage();
    expect(mockReaddirSync).not.toHaveBeenCalled();
  });
});
