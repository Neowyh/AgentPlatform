import { describe, test, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("fs", () => ({
  default: {
    existsSync: vi.fn(),
    readFileSync: vi.fn(),
  },
}));

vi.mock("path", () => ({
  default: {
    resolve: vi.fn((...args: string[]) => args.join("/")),
  },
}));

import fs from "fs";
import path from "path";

import { GET } from "@/app/mock/api/threads/[thread_id]/artifacts/[[...artifact_path]]/route";

const mockExistsSync = vi.mocked(fs.existsSync);
const mockReadFileSync = vi.mocked(fs.readFileSync);
const mockPathResolve = vi.mocked(path.resolve);

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

describe("mock artifacts route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathResolve.mockImplementation((...args: string[]) => args.join("/"));
  });

  test("GET returns 404 when file does not exist", async () => {
    mockExistsSync.mockReturnValueOnce(false);

    const request = makeRequest("http://localhost/api/artifacts/nonexistent");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt/file.txt"]),
    );

    expect(response.status).toBe(404);
  });

  test("GET returns 404 when artifact path does not start with mnt/", async () => {
    const request = makeRequest("http://localhost/api/artifacts/other");
    const response = await GET(
      request,
      makeParams("thread-1", ["other/file.txt"]),
    );

    expect(response.status).toBe(404);
  });

  test("GET returns 404 when no artifact path provided", async () => {
    const request = makeRequest("http://localhost/api/artifacts");
    const response = await GET(request, makeParams("thread-1"));

    expect(response.status).toBe(404);
  });

  test("GET returns file content when file exists", async () => {
    mockExistsSync.mockReturnValueOnce(true);
    mockReadFileSync.mockReturnValueOnce(Buffer.from("file content"));

    const request = makeRequest("http://localhost/api/artifacts/file");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt/file.txt"]),
    );

    expect(response.status).toBe(200);
    const body = await response.text();
    expect(body).toBe("file content");
  });

  test("GET sets Content-Disposition header for download requests", async () => {
    mockExistsSync.mockReturnValueOnce(true);
    mockReadFileSync.mockReturnValueOnce(Buffer.from("download content"));

    const request = makeRequest(
      "http://localhost/api/artifacts/file?download=true",
    );
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt/file.txt"]),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Disposition")).toContain("attachment");
  });

  test("GET returns video/mp4 content type for .mp4 files", async () => {
    mockExistsSync.mockReturnValueOnce(true);
    mockReadFileSync.mockReturnValueOnce(Buffer.from("video data"));

    const request = makeRequest("http://localhost/api/artifacts/video");
    const response = await GET(
      request,
      makeParams("thread-1", ["mnt/video.mp4"]),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("video/mp4");
  });

  test("GET resolves mnt/ path to public/demo/threads path", async () => {
    mockExistsSync.mockReturnValueOnce(true);
    mockReadFileSync.mockReturnValueOnce(Buffer.from("data"));

    const request = makeRequest("http://localhost/api/artifacts/file");
    await GET(request, makeParams("thread-1", ["mnt/file.txt"]));

    expect(mockPathResolve).toHaveBeenCalled();
    // path.resolve receives (cwd, "public/demo/threads/thread-1/file.txt")
    const args = mockPathResolve.mock.calls[0]!;
    expect(args[1]).toContain("public/demo/threads/thread-1/");
    expect(args[1]).toContain("file.txt");
  });

  test("GET returns response with 200 status for regular files", async () => {
    mockExistsSync.mockReturnValueOnce(true);
    mockReadFileSync.mockReturnValueOnce(Buffer.from("data"));

    const request = makeRequest("http://localhost/api/artifacts/file");
    const response = await GET(request, makeParams("t", ["mnt/readme.md"]));

    expect(response.status).toBe(200);
  });
});
