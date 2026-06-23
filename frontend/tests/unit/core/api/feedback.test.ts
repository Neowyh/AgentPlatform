import { describe, expect, test, vi, afterEach } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

import { upsertFeedback, deleteFeedback } from "@/core/api/feedback";
import { fetch } from "@/core/api/fetcher";

const mockFetch = fetch as ReturnType<typeof vi.fn>;

afterEach(() => {
  vi.clearAllMocks();
});

describe("upsertFeedback", () => {
  test("sends PUT request with rating and comment", async () => {
    const mockData = {
      feedback_id: "fb-1",
      rating: 5,
      comment: "Great answer",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const result = await upsertFeedback("thread-1", "run-1", 5, "Great answer");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/thread-1/runs/run-1/feedback",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: 5, comment: "Great answer" }),
      },
    );
    expect(result).toEqual(mockData);
  });

  test("sends null comment when comment is omitted", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ feedback_id: "fb-2", rating: 3, comment: null }),
    });

    await upsertFeedback("thread-1", "run-1", 3);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        body: JSON.stringify({ rating: 3, comment: null }),
      }),
    );
  });

  test("encodes threadId and runId in URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ feedback_id: "fb-3", rating: 1, comment: null }),
    });

    await upsertFeedback("thread/with/slashes", "run/with/slashes", 1);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent("thread/with/slashes")),
      expect.anything(),
    );
  });

  test("throws on non-ok response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    await expect(
      upsertFeedback("thread-1", "run-1", 5, "Good"),
    ).rejects.toThrow("Failed to submit feedback: 500");
  });
});

describe("deleteFeedback", () => {
  test("sends DELETE request", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
    });

    await deleteFeedback("thread-1", "run-1");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/threads/thread-1/runs/run-1/feedback",
      { method: "DELETE" },
    );
  });

  test("does not throw on 404 response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(deleteFeedback("thread-1", "run-1")).resolves.toBeUndefined();
  });

  test("throws on non-ok response that is not 404", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    await expect(deleteFeedback("thread-1", "run-1")).rejects.toThrow(
      "Failed to delete feedback: 500",
    );
  });

  test("encodes threadId and runId in URL", async () => {
    mockFetch.mockResolvedValue({ ok: true });

    await deleteFeedback("t/1", "r/1");

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent("t/1")),
      expect.anything(),
    );
  });
});
