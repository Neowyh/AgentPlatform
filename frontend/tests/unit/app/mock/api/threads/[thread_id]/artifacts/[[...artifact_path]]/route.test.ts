import { describe, test, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

// The merged artifacts mock route validates the requested path against the
// static-demo allowlist (resolveStaticDemoArtifact) and proxies the file from
// the static /demo/threads/<id>/... origin path.
vi.mock("@/core/threads/static-demo", () => ({
  resolveStaticDemoArtifact: vi.fn(
    (threadId: string, segments: readonly string[]) => {
      if (segments[0] !== "mnt") return null;
      const artifactPath = segments.slice(1).join("/");
      // Allowlist: only file.txt / video.mp4 exist for thread-1, readme.md for t.
      if (threadId === "thread-1" && ["file.txt", "video.mp4"].includes(artifactPath)) {
        return `/demo/threads/${threadId}/${artifactPath}`;
      }
      if (threadId === "t" && artifactPath === "readme.md") {
        return `/demo/threads/${threadId}/${artifactPath}`;
      }
      return null;
    },
  ),
}));

import { GET } from "@/app/mock/api/threads/[thread_id]/artifacts/[[...artifact_path]]/route";

function makeRequest(url: string) {
  return new NextRequest(url);
}

function makeParams(threadId: string, artifactPath?: string[]) {
  return {
    params: Promise.resolve({
      thread_id: threadId,
      artifact_path: artifactPath,
    }),
  };
}

function mockUpstreamFile(
  content: string,
  { status = 200, headers = {} as Record<string, string> } = {},
) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(content, { status, headers: new Headers(headers) }),
      ),
    ),
  );
}

describe("mock artifacts route", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  test("GET returns 404 when file does not exist", async () => {
    const request = makeRequest("http://localhost/api/artifacts/nonexistent");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt/nonexistent.txt"]),
    );

    expect(response.status).toBe(404);
  });

  test("GET returns 404 when artifact path does not start with mnt/", async () => {
    const request = makeRequest("http://localhost/api/artifacts/other");
    const response = await GET(
      request,
      makeParams("thread-1", ["other", "file.txt"]),
    );

    expect(response.status).toBe(404);
  });

  test("GET returns 404 when no artifact path provided", async () => {
    const request = makeRequest("http://localhost/api/artifacts");
    const response = await GET(request, makeParams("thread-1"));

    expect(response.status).toBe(404);
  });

  test("GET returns file content when file exists", async () => {
    mockUpstreamFile("file content");

    const request = makeRequest("http://localhost/api/artifacts/file");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt", "file.txt"]),
    );

    expect(response.status).toBe(200);
    const body = await response.text();
    expect(body).toBe("file content");
  });

  test("GET sets Content-Disposition header for download requests", async () => {
    mockUpstreamFile("download content");

    const request = makeRequest(
      "http://localhost/api/artifacts/file?download=true",
    );
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt", "file.txt"]),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Disposition")).toContain(
      "attachment",
    );
    expect(response.headers.get("Content-Disposition")).toContain("file.txt");
  });

  test("GET returns video/mp4 content type for .mp4 files", async () => {
    mockUpstreamFile("video data", { headers: { "Content-Type": "video/mp4" } });

    const request = makeRequest("http://localhost/api/artifacts/video");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt", "video.mp4"]),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("video/mp4");
  });

  test("GET resolves mnt/ path to the static demo/threads origin path", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response("data", { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = makeRequest("http://localhost/api/artifacts/file");
    await GET(request, makeParams("thread-1", ["mnt", "file.txt"]));

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0]![0])).toBe(
      "http://localhost/demo/threads/thread-1/file.txt",
    );
  });

  test("GET returns response with 200 status for regular files", async () => {
    mockUpstreamFile("data");

    const request = makeRequest("http://localhost/api/artifacts/file");
    const response = await GET(request, makeParams("t", ["mnt", "readme.md"]));

    expect(response.status).toBe(200);
  });
});
