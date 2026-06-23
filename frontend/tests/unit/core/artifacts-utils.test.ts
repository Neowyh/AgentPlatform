import { describe, expect, test, vi, beforeEach } from "vitest";

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => ""),
}));

vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: vi.fn(() => false),
}));

import {
  urlOfArtifact,
  extractArtifactsFromThread,
  resolveArtifactURL,
} from "@/core/artifacts/utils";
import { getBackendBaseURL } from "@/core/config";
import { isStaticWebsiteOnly } from "@/core/static-mode";
import type { AgentThread } from "@/core/threads/types";

const mockedBackendURL = vi.mocked(getBackendBaseURL);
const mockedStaticMode = vi.mocked(isStaticWebsiteOnly);

beforeEach(() => {
  vi.clearAllMocks();
  mockedBackendURL.mockReturnValue("");
  mockedStaticMode.mockReturnValue(false);
});

// ---------------------------------------------------------------------------
// urlOfArtifact
// ---------------------------------------------------------------------------
describe("urlOfArtifact", () => {
  // --- non-static, non-mock (standard) ------------------------------------
  describe("standard mode", () => {
    test("builds URL with leading slash filepath", () => {
      expect(
        urlOfArtifact({ filepath: "/reports/q1.pdf", threadId: "t-1" }),
      ).toBe("/api/threads/t-1/artifacts/reports/q1.pdf");
    });

    test("normalizes filepath without leading slash", () => {
      expect(
        urlOfArtifact({ filepath: "reports/q1.pdf", threadId: "t-1" }),
      ).toBe("/api/threads/t-1/artifacts/reports/q1.pdf");
    });

    test("produces identical URLs regardless of leading slash", () => {
      const withSlash = urlOfArtifact({
        filepath: "/a/b.txt",
        threadId: "t-1",
      });
      const withoutSlash = urlOfArtifact({
        filepath: "a/b.txt",
        threadId: "t-1",
      });
      expect(withSlash).toBe(withoutSlash);
    });

    test("appends ?download=true when download is true", () => {
      expect(
        urlOfArtifact({
          filepath: "/data.csv",
          threadId: "t-2",
          download: true,
        }),
      ).toBe("/api/threads/t-2/artifacts/data.csv?download=true");
    });

    test("omits download query when download is false", () => {
      const url = urlOfArtifact({
        filepath: "/data.csv",
        threadId: "t-2",
        download: false,
      });
      expect(url).not.toContain("download");
    });

    test("omits download query when download is omitted (default false)", () => {
      const url = urlOfArtifact({ filepath: "/data.csv", threadId: "t-2" });
      expect(url).not.toContain("download");
    });

    test("handles empty filepath", () => {
      expect(urlOfArtifact({ filepath: "", threadId: "t-1" })).toBe(
        "/api/threads/t-1/artifacts/",
      );
    });

    test("includes host when getBackendBaseURL returns a value", () => {
      mockedBackendURL.mockReturnValue("https://backend.example.com");
      expect(urlOfArtifact({ filepath: "/a.txt", threadId: "t-1" })).toBe(
        "https://backend.example.com/api/threads/t-1/artifacts/a.txt",
      );
    });

    test("uses backend base URL directly (trailing slash stripping is in getBackendBaseURL)", () => {
      // urlOfArtifact concatenates getBackendBaseURL() directly.
      // In production getBackendBaseURL already strips trailing slashes.
      mockedBackendURL.mockReturnValue("https://backend.example.com");
      expect(urlOfArtifact({ filepath: "/a.txt", threadId: "t-1" })).toBe(
        "https://backend.example.com/api/threads/t-1/artifacts/a.txt",
      );
    });
  });

  // --- mock mode ----------------------------------------------------------
  describe("mock mode", () => {
    test("inserts /mock/ segment in path", () => {
      expect(
        urlOfArtifact({
          filepath: "/chart.png",
          threadId: "t-3",
          isMock: true,
        }),
      ).toBe("/mock/api/threads/t-3/artifacts/chart.png");
    });

    test("normalizes filepath without leading slash in mock mode", () => {
      expect(
        urlOfArtifact({ filepath: "chart.png", threadId: "t-3", isMock: true }),
      ).toBe("/mock/api/threads/t-3/artifacts/chart.png");
    });

    test("combines mock and download flags", () => {
      expect(
        urlOfArtifact({
          filepath: "/chart.png",
          threadId: "t-3",
          isMock: true,
          download: true,
        }),
      ).toBe("/mock/api/threads/t-3/artifacts/chart.png?download=true");
    });

    test("mock mode with download false omits query", () => {
      const url = urlOfArtifact({
        filepath: "/x.txt",
        threadId: "t-1",
        isMock: true,
        download: false,
      });
      expect(url).not.toContain("download");
    });

    test("includes host in mock mode when backend URL is set", () => {
      mockedBackendURL.mockReturnValue("https://api.test.com");
      expect(
        urlOfArtifact({ filepath: "/a.txt", threadId: "t-1", isMock: true }),
      ).toBe("https://api.test.com/mock/api/threads/t-1/artifacts/a.txt");
    });
  });

  // --- static website mode ------------------------------------------------
  describe("static website mode", () => {
    beforeEach(() => {
      mockedStaticMode.mockReturnValue(true);
    });

    test("replaces /mnt/ prefix with /", () => {
      expect(
        urlOfArtifact({
          filepath: "/mnt/user-data/report.pdf",
          threadId: "t-10",
        }),
      ).toBe("/demo/threads/t-10/user-data/report.pdf");
    });

    test("keeps path unchanged when no /mnt/ prefix", () => {
      expect(
        urlOfArtifact({ filepath: "/home/user/file.txt", threadId: "t-10" }),
      ).toBe("/demo/threads/t-10/home/user/file.txt");
    });

    test("appends ?download=true in static mode", () => {
      expect(
        urlOfArtifact({
          filepath: "/mnt/data/report.pdf",
          threadId: "t-10",
          download: true,
        }),
      ).toBe("/demo/threads/t-10/data/report.pdf?download=true");
    });

    test("does NOT normalize filepath before passing to staticDemoArtifactURL", () => {
      // urlOfArtifact passes raw filepath to staticDemoArtifactURL (no normalizeArtifactPath).
      // "mnt/..." does not match /^\/mnt\//, so it stays as-is and concatenates directly.
      expect(
        urlOfArtifact({ filepath: "mnt/data/report.pdf", threadId: "t-10" }),
      ).toBe("/demo/threads/t-10mnt/data/report.pdf");
    });

    test("ignores isMock flag in static mode", () => {
      const url = urlOfArtifact({
        filepath: "/chart.png",
        threadId: "t-10",
        isMock: true,
      });
      expect(url).toBe("/demo/threads/t-10/chart.png");
      expect(url).not.toContain("/mock/");
    });

    test("static mode with host prefix", () => {
      mockedBackendURL.mockReturnValue("https://cdn.example.com");
      expect(urlOfArtifact({ filepath: "/mnt/a.txt", threadId: "t-1" })).toBe(
        "https://cdn.example.com/demo/threads/t-1/a.txt",
      );
    });

    test("handles filepath that is exactly /mnt/", () => {
      expect(urlOfArtifact({ filepath: "/mnt/", threadId: "t-1" })).toBe(
        "/demo/threads/t-1/",
      );
    });

    test("handles empty filepath in static mode", () => {
      // staticDemoArtifactURL receives raw empty string; demoPath stays "", no trailing slash
      expect(urlOfArtifact({ filepath: "", threadId: "t-1" })).toBe(
        "/demo/threads/t-1",
      );
    });
  });
});

// ---------------------------------------------------------------------------
// extractArtifactsFromThread
// ---------------------------------------------------------------------------
describe("extractArtifactsFromThread", () => {
  function makeThread(artifacts: string[] | undefined | null): AgentThread {
    return {
      values: {
        artifacts,
        title: "Test",
        messages: [],
      },
    } as unknown as AgentThread;
  }

  test("returns artifacts array when present", () => {
    expect(
      extractArtifactsFromThread(makeThread(["/a.txt", "/b.txt"])),
    ).toEqual(["/a.txt", "/b.txt"]);
  });

  test("returns empty array when artifacts is undefined", () => {
    expect(extractArtifactsFromThread(makeThread(undefined))).toEqual([]);
  });

  test("returns empty array when artifacts is null", () => {
    expect(extractArtifactsFromThread(makeThread(null))).toEqual([]);
  });

  test("returns empty array when artifacts is empty", () => {
    expect(extractArtifactsFromThread(makeThread([]))).toEqual([]);
  });

  test("preserves order of artifacts", () => {
    const artifacts = ["/z.txt", "/a.txt", "/m.txt"];
    expect(extractArtifactsFromThread(makeThread(artifacts))).toEqual(
      artifacts,
    );
  });
});

// ---------------------------------------------------------------------------
// resolveArtifactURL
// ---------------------------------------------------------------------------
describe("resolveArtifactURL", () => {
  describe("standard mode", () => {
    test("builds URL from absolute path", () => {
      expect(resolveArtifactURL("/data/output.csv", "thread-1")).toBe(
        "/api/threads/thread-1/artifacts/data/output.csv",
      );
    });

    test("normalizes path without leading slash", () => {
      expect(resolveArtifactURL("data/output.csv", "thread-1")).toBe(
        "/api/threads/thread-1/artifacts/data/output.csv",
      );
    });

    test("produces identical URLs regardless of leading slash", () => {
      const withSlash = resolveArtifactURL("/a/b.txt", "t-1");
      const withoutSlash = resolveArtifactURL("a/b.txt", "t-1");
      expect(withSlash).toBe(withoutSlash);
    });

    test("handles empty filepath", () => {
      expect(resolveArtifactURL("", "t-1")).toBe("/api/threads/t-1/artifacts/");
    });

    test("includes host when backend URL is set", () => {
      mockedBackendURL.mockReturnValue("https://api.prod.com");
      expect(resolveArtifactURL("/x.txt", "t-1")).toBe(
        "https://api.prod.com/api/threads/t-1/artifacts/x.txt",
      );
    });
  });

  describe("static website mode", () => {
    beforeEach(() => {
      mockedStaticMode.mockReturnValue(true);
    });

    test("replaces /mnt/ prefix with /", () => {
      expect(resolveArtifactURL("/mnt/data/file.pdf", "thread-2")).toBe(
        "/demo/threads/thread-2/data/file.pdf",
      );
    });

    test("keeps path unchanged when no /mnt/ prefix", () => {
      expect(resolveArtifactURL("/home/file.txt", "thread-2")).toBe(
        "/demo/threads/thread-2/home/file.txt",
      );
    });

    test("does NOT normalize filepath before passing to staticDemoArtifactURL", () => {
      // resolveArtifactURL passes raw filepath to staticDemoArtifactURL.
      // "mnt/..." does not match /^\/mnt\//, so it stays as-is and concatenates directly.
      expect(resolveArtifactURL("mnt/data/file.pdf", "thread-2")).toBe(
        "/demo/threads/thread-2mnt/data/file.pdf",
      );
    });

    test("handles empty filepath in static mode", () => {
      // staticDemoArtifactURL receives raw empty string; demoPath stays "", no trailing slash
      expect(resolveArtifactURL("", "t-1")).toBe("/demo/threads/t-1");
    });

    test("static mode with host prefix", () => {
      mockedBackendURL.mockReturnValue("https://cdn.example.com");
      expect(resolveArtifactURL("/mnt/a.txt", "t-1")).toBe(
        "https://cdn.example.com/demo/threads/t-1/a.txt",
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Integration / cross-cutting
// ---------------------------------------------------------------------------
describe("cross-cutting concerns", () => {
  test("urlOfArtifact and resolveArtifactURL produce same standard path", () => {
    const filepath = "/reports/annual.pdf";
    const threadId = "t-99";
    expect(urlOfArtifact({ filepath, threadId })).toBe(
      resolveArtifactURL(filepath, threadId),
    );
  });

  test("urlOfArtifact and resolveArtifactURL produce same static demo path", () => {
    mockedStaticMode.mockReturnValue(true);
    const filepath = "/mnt/data/report.pdf";
    const threadId = "t-99";
    expect(urlOfArtifact({ filepath, threadId })).toBe(
      resolveArtifactURL(filepath, threadId),
    );
  });

  test("all functions handle deeply nested paths", () => {
    const deep = "/a/b/c/d/e/f/g.txt";
    expect(urlOfArtifact({ filepath: deep, threadId: "t-1" })).toBe(
      "/api/threads/t-1/artifacts/a/b/c/d/e/f/g.txt",
    );
    expect(resolveArtifactURL(deep, "t-1")).toBe(
      "/api/threads/t-1/artifacts/a/b/c/d/e/f/g.txt",
    );
  });

  test("all functions handle special characters in threadId", () => {
    const tid = "thread-with-dashes_and_underscores";
    expect(urlOfArtifact({ filepath: "/f.txt", threadId: tid })).toContain(tid);
    expect(resolveArtifactURL("/f.txt", tid)).toContain(tid);
  });
});
