import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/uploads/api", () => ({
  uploadFiles: vi.fn(),
  listUploadedFiles: vi.fn(),
  deleteUploadedFile: vi.fn(),
}));

import {
  uploadFiles,
  listUploadedFiles,
  deleteUploadedFile,
} from "@/core/uploads/api";
import {
  useUploadFiles,
  useUploadedFiles,
  useDeleteUploadedFile,
  useUploadFilesOnSubmit,
} from "@/core/uploads/hooks";

const mockUploadFiles = uploadFiles as ReturnType<typeof vi.fn>;
const mockListUploadedFiles = listUploadedFiles as ReturnType<typeof vi.fn>;
const mockDeleteUploadedFile = deleteUploadedFile as ReturnType<typeof vi.fn>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("useUploadFiles", () => {
  test("calls uploadFiles API and invalidates queries on success", async () => {
    mockUploadFiles.mockResolvedValue({
      success: true,
      files: [
        {
          filename: "test.txt",
          size: 100,
          path: "/",
          virtual_path: "/",
          artifact_url: "/",
        },
      ],
      message: "Uploaded",
    });

    const { result } = renderHook(() => useUploadFiles("thread-1"), {
      wrapper: createWrapper(),
    });

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    await act(async () => {
      await result.current.mutateAsync([file]);
    });

    expect(mockUploadFiles).toHaveBeenCalledWith("thread-1", [file]);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports error on failure", async () => {
    mockUploadFiles.mockRejectedValue(new Error("Upload failed"));

    const { result } = renderHook(() => useUploadFiles("thread-1"), {
      wrapper: createWrapper(),
    });

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    await act(async () => {
      try {
        await result.current.mutateAsync([file]);
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Upload failed");
  });
});

describe("useUploadedFiles", () => {
  test("fetches uploaded files list", async () => {
    const mockData = {
      files: [
        {
          filename: "a.txt",
          size: 50,
          path: "/",
          virtual_path: "/",
          artifact_url: "/",
        },
      ],
      count: 1,
    };
    mockListUploadedFiles.mockResolvedValue(mockData);

    const { result } = renderHook(() => useUploadedFiles("thread-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(mockListUploadedFiles).toHaveBeenCalledWith("thread-1");
  });

  test("does not fetch when threadId is empty", () => {
    const { result } = renderHook(() => useUploadedFiles(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockListUploadedFiles).not.toHaveBeenCalled();
  });

  test("fetches when threadId is provided", async () => {
    mockListUploadedFiles.mockResolvedValue({ files: [], count: 0 });

    const { result } = renderHook(() => useUploadedFiles("thread-abc"), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(mockListUploadedFiles).toHaveBeenCalledWith("thread-abc"),
    );
  });
});

describe("useDeleteUploadedFile", () => {
  test("calls deleteUploadedFile API and invalidates queries on success", async () => {
    mockDeleteUploadedFile.mockResolvedValue({
      success: true,
      message: "Deleted",
    });

    const { result } = renderHook(() => useDeleteUploadedFile("thread-1"), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync("file.txt");
    });

    expect(mockDeleteUploadedFile).toHaveBeenCalledWith("thread-1", "file.txt");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  test("reports error on failure", async () => {
    mockDeleteUploadedFile.mockRejectedValue(new Error("Delete failed"));

    const { result } = renderHook(() => useDeleteUploadedFile("thread-1"), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      try {
        await result.current.mutateAsync("file.txt");
      } catch {
        // expected
      }
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Delete failed");
  });
});

describe("useUploadFilesOnSubmit", () => {
  test("returns empty array when no files provided", async () => {
    mockUploadFiles.mockResolvedValue({
      success: true,
      files: [],
      message: "No files",
    });

    const { result } = renderHook(() => useUploadFilesOnSubmit("thread-1"), {
      wrapper: createWrapper(),
    });

    const uploadResult = await result.current([]);
    expect(uploadResult).toEqual([]);
    expect(mockUploadFiles).not.toHaveBeenCalled();
  });

  test("uploads files and returns file info", async () => {
    const mockFiles = [
      {
        filename: "uploaded.txt",
        size: 200,
        path: "/uploads/uploaded.txt",
        virtual_path: "/uploaded.txt",
        artifact_url: "/api/artifacts/uploaded.txt",
      },
    ];
    mockUploadFiles.mockResolvedValue({
      success: true,
      files: mockFiles,
      message: "Uploaded",
    });

    const { result } = renderHook(() => useUploadFilesOnSubmit("thread-1"), {
      wrapper: createWrapper(),
    });

    const file = new File(["content"], "uploaded.txt", { type: "text/plain" });
    const uploadResult = await result.current([file]);

    expect(mockUploadFiles).toHaveBeenCalledWith("thread-1", [file]);
    expect(uploadResult).toEqual(mockFiles);
  });

  test("propagates errors from upload mutation", async () => {
    mockUploadFiles.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useUploadFilesOnSubmit("thread-1"), {
      wrapper: createWrapper(),
    });

    const file = new File(["content"], "test.txt", { type: "text/plain" });
    await expect(result.current([file])).rejects.toThrow("Network error");
  });
});
