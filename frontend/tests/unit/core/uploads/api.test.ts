import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

const mockExtractError = vi.fn();
vi.mock("@/core/api/errors", () => ({
  extractError: (...args: unknown[]) => mockExtractError(...args),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

import { fetch } from "@/core/api/fetcher";
import {
  uploadFiles,
  listUploadedFiles,
  deleteUploadedFile,
} from "@/core/uploads/api";

const mockFetch = fetch as ReturnType<typeof vi.fn>;

afterEach(() => {
  vi.clearAllMocks();
});

describe("uploadFiles", () => {
  test("sends POST request with FormData containing files", async () => {
    const mockResponse = {
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          files: [
            {
              filename: "test.txt",
              size: 100,
              path: "/uploads/test.txt",
              virtual_path: "/test.txt",
              artifact_url: "/api/artifacts/test.txt",
            },
          ],
          message: "Uploaded",
        }),
    };
    mockFetch.mockResolvedValue(mockResponse);

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    const result = await uploadFiles("thread-123", [file]);

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/thread-123/uploads",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.success).toBe(true);
    expect(result.files).toHaveLength(1);
    expect(result.files[0]?.filename).toBe("test.txt");
  });

  test("sends multiple files in FormData", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ success: true, files: [], message: "Uploaded" }),
    });

    const file1 = new File(["a"], "a.txt", { type: "text/plain" });
    const file2 = new File(["b"], "b.txt", { type: "text/plain" });
    await uploadFiles("thread-123", [file1, file2]);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/threads/thread-123/uploads"),
      expect.anything(),
    );
  });

  test("calls extractError when response is not ok", async () => {
    mockExtractError.mockRejectedValue(new Error("Upload failed"));
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    await expect(uploadFiles("thread-123", [file])).rejects.toThrow(
      "Upload failed",
    );

    expect(mockExtractError).toHaveBeenCalledWith(
      expect.anything(),
      "Upload failed",
    );
  });
});

describe("listUploadedFiles", () => {
  test("sends GET request to list endpoint", async () => {
    const mockData = {
      files: [
        {
          filename: "doc.pdf",
          size: 1024,
          path: "/uploads/doc.pdf",
          virtual_path: "/doc.pdf",
          artifact_url: "/api/artifacts/doc.pdf",
        },
      ],
      count: 1,
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const result = await listUploadedFiles("thread-456");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/thread-456/uploads/list",
    );
    expect(result.count).toBe(1);
    expect(result.files[0]?.filename).toBe("doc.pdf");
  });

  test("calls extractError when response is not ok", async () => {
    mockExtractError.mockRejectedValue(
      new Error("Failed to list uploaded files"),
    );
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(listUploadedFiles("thread-456")).rejects.toThrow(
      "Failed to list uploaded files",
    );

    expect(mockExtractError).toHaveBeenCalledWith(
      expect.anything(),
      "Failed to list uploaded files",
    );
  });

  test("returns empty files list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ files: [], count: 0 }),
    });

    const result = await listUploadedFiles("thread-789");
    expect(result.files).toEqual([]);
    expect(result.count).toBe(0);
  });
});

describe("deleteUploadedFile", () => {
  test("sends DELETE request for specific file", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, message: "Deleted" }),
    });

    const result = await deleteUploadedFile("thread-123", "test.txt");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/thread-123/uploads/test.txt",
      { method: "DELETE" },
    );
    expect(result.success).toBe(true);
    expect(result.message).toBe("Deleted");
  });

  test("calls extractError when response is not ok", async () => {
    mockExtractError.mockRejectedValue(new Error("Failed to delete file"));
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(
      deleteUploadedFile("thread-123", "missing.txt"),
    ).rejects.toThrow("Failed to delete file");

    expect(mockExtractError).toHaveBeenCalledWith(
      expect.anything(),
      "Failed to delete file",
    );
  });
});
