import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn((_res: Response, msg: string) => {
    throw new Error(msg);
  }),
}));

import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import {
  listVisibilityApplications,
  createVisibilityApplication,
  reviewVisibilityApplication,
  withdrawVisibilityApplication,
} from "@/core/visibility-applications/api";
import type {
  VisibilityApplication,
  ApplicationsResponse,
} from "@/core/visibility-applications/types";

const mockFetch = vi.mocked(fetch);
const mockExtractError = vi.mocked(extractError);

function okJson(data: unknown): Response {
  return {
    ok: true,
    json: async () => data,
  } as unknown as Response;
}

function notOkJson(status = 400, statusText = "Bad Request"): Response {
  return {
    ok: false,
    status,
    statusText,
    json: async () => ({ detail: "Something went wrong" }),
  } as unknown as Response;
}

const sampleApplication: VisibilityApplication = {
  id: "app-1",
  resource_type: "agent",
  resource_id: "agent-1",
  applicant_id: "user-1",
  current_visibility: "private",
  target_visibility: "public",
  department_id: "dept-1",
  reason: "Need public access",
  status: "pending",
  submitted_at: "2024-01-01T00:00:00Z",
  reviewed_by: null,
  reviewed_at: null,
  review_comment: null,
  version: 1,
};

const sampleListResponse: ApplicationsResponse = {
  applications: [sampleApplication],
  total: 1,
  page: 1,
  page_size: 20,
};

describe("visibility-applications API", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  // ── listVisibilityApplications ──────────────────────────────────

  describe("listVisibilityApplications", () => {
    test("sends GET request with clean URL when no params", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      const result = await listVisibilityApplications();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications",
      );
      expect(result).toEqual(sampleListResponse);
    });

    test("includes status in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ status: "approved" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("status")).toBe("approved");
    });

    test("includes resource_type in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ resource_type: "agent" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("resource_type")).toBe("agent");
    });

    test("includes target_visibility in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ target_visibility: "public" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("target_visibility")).toBe("public");
    });

    test("includes applicant_id in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ applicant_id: "user-1" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("applicant_id")).toBe("user-1");
    });

    test("includes page and page_size in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ page: 2, page_size: 10 });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("page")).toBe("2");
      expect(url.searchParams.get("page_size")).toBe("10");
    });

    test("includes all params at once", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({
        status: "pending",
        resource_type: "thread",
        target_visibility: "department",
        applicant_id: "user-1",
        page: 3,
        page_size: 5,
      });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("status")).toBe("pending");
      expect(url.searchParams.get("resource_type")).toBe("thread");
      expect(url.searchParams.get("target_visibility")).toBe("department");
      expect(url.searchParams.get("applicant_id")).toBe("user-1");
      expect(url.searchParams.get("page")).toBe("3");
      expect(url.searchParams.get("page_size")).toBe("5");
    });

    test("omits empty-string params from query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ status: "" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications",
      );
    });

    test("omits page=0 from query string (falsy)", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ page: 0 });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications",
      );
    });

    test("omits empty object params from query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({});

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications",
      );
    });

    test("URL-encodes special characters in query params", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ status: "a/b=c&d" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toContain("status=" + encodeURIComponent("a/b=c&d"));
    });
  });

  // ── createVisibilityApplication ─────────────────────────────────

  describe("createVisibilityApplication", () => {
    test("routes all resources through the canonical approval service", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));
      const resourceId = "11111111-1111-1111-1111-111111111111";

      await createVisibilityApplication({
        resource_type: "workflow",
        resource_id: resourceId,
        target_visibility: "department",
        reason: "Share with department",
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/resources/${resourceId}/visibility-applications`,
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_visibility: "department",
            reason: "Share with department",
          }),
        }),
      );
    });
  });

  // ── reviewVisibilityApplication ─────────────────────────────────

  describe("reviewVisibilityApplication", () => {
    test("sends PUT request with correct URL, body and method", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));

      const result = await reviewVisibilityApplication(
        "app-1",
        "approved",
        "Looks good",
        2,
      );

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications/app-1",
      );
      const calledInit = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(calledInit.method).toBe("PUT");
      expect(JSON.parse(calledInit.body as string)).toEqual({
        action: "approved",
        comment: "Looks good",
        version: 2,
      });
      expect(result).toEqual(sampleApplication);
    });

    test("sends rejected action correctly", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));

      await reviewVisibilityApplication(
        "app-1",
        "rejected",
        "Not justified",
        3,
      );

      const calledInit = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(JSON.parse(calledInit.body as string)).toEqual({
        action: "rejected",
        comment: "Not justified",
        version: 3,
      });
    });

    test("URL-encodes special characters in applicationId", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));

      await reviewVisibilityApplication("a/b=c", "approved", "ok", 1);

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications/a%2Fb%3Dc",
      );
    });
  });

  // ── withdrawVisibilityApplication ───────────────────────────────

  describe("withdrawVisibilityApplication", () => {
    test("sends PUT request to withdraw endpoint with version", async () => {
      mockFetch.mockResolvedValue(okJson({ success: true }));

      const result = await withdrawVisibilityApplication("app-1", 1);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications/app-1/withdraw",
      );
      const calledInit = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(calledInit.method).toBe("PUT");
      expect(JSON.parse(calledInit.body as string)).toEqual({ version: 1 });
      expect(result).toEqual({ success: true });
    });

    test("URL-encodes special characters in applicationId", async () => {
      mockFetch.mockResolvedValue(okJson({ success: true }));

      await withdrawVisibilityApplication("a/b=c", 2);

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/visibility-applications/a%2Fb%3Dc/withdraw",
      );
    });
  });

  // ── success path: extractError should NOT be called ──────────────

  describe("success path", () => {
    test("does not call extractError when listVisibilityApplications succeeds", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listVisibilityApplications({ status: "approved" });

      expect(mockExtractError).not.toHaveBeenCalled();
    });

    test("does not call extractError when createVisibilityApplication succeeds", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));

      await createVisibilityApplication({
        resource_type: "agent",
        resource_id: "agent-1",
        target_visibility: "public",
        reason: "test",
      });

      expect(mockExtractError).not.toHaveBeenCalled();
    });

    test("does not call extractError when reviewVisibilityApplication succeeds", async () => {
      mockFetch.mockResolvedValue(okJson(sampleApplication));

      await reviewVisibilityApplication("app-1", "approved", "ok", 1);

      expect(mockExtractError).not.toHaveBeenCalled();
    });

    test("does not call extractError when withdrawVisibilityApplication succeeds", async () => {
      mockFetch.mockResolvedValue(okJson({ success: true }));

      await withdrawVisibilityApplication("app-1", 1);

      expect(mockExtractError).not.toHaveBeenCalled();
    });
  });

  // ── error handling ──────────────────────────────────────────────

  describe("error handling", () => {
    test("calls extractError when listVisibilityApplications returns non-ok", async () => {
      const res = notOkJson(403, "Forbidden");
      mockFetch.mockResolvedValue(res);

      await expect(listVisibilityApplications()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to list visibility applications",
      );
    });

    test("calls extractError when createVisibilityApplication returns non-ok", async () => {
      const res = notOkJson(422, "Unprocessable Entity");
      mockFetch.mockResolvedValue(res);

      await expect(
        createVisibilityApplication({
          resource_type: "agent",
          resource_id: "agent-1",
          target_visibility: "public",
          reason: "test",
        }),
      ).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to submit visibility application",
      );
    });

    test("calls extractError when reviewVisibilityApplication returns non-ok", async () => {
      const res = notOkJson(404, "Not Found");
      mockFetch.mockResolvedValue(res);

      await expect(
        reviewVisibilityApplication("app-1", "approved", "ok", 1),
      ).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to review visibility application",
      );
    });

    test("calls extractError when withdrawVisibilityApplication returns non-ok", async () => {
      const res = notOkJson(409, "Conflict");
      mockFetch.mockResolvedValue(res);

      await expect(withdrawVisibilityApplication("app-1", 1)).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to withdraw visibility application",
      );
    });
  });

  // ── fetch failure (network error) ──────────────────────────────

  describe("fetch failure", () => {
    test("propagates fetch rejection for listVisibilityApplications", async () => {
      mockFetch.mockRejectedValue(new Error("Network error"));

      await expect(listVisibilityApplications()).rejects.toThrow(
        "Network error",
      );
    });

    test("propagates fetch rejection for createVisibilityApplication", async () => {
      mockFetch.mockRejectedValue(new Error("Network error"));

      await expect(
        createVisibilityApplication({
          resource_type: "agent",
          resource_id: "agent-1",
          target_visibility: "public",
          reason: "test",
        }),
      ).rejects.toThrow("Network error");
    });

    test("propagates fetch rejection for reviewVisibilityApplication", async () => {
      mockFetch.mockRejectedValue(new Error("Network error"));

      await expect(
        reviewVisibilityApplication("app-1", "approved", "ok", 1),
      ).rejects.toThrow("Network error");
    });

    test("propagates fetch rejection for withdrawVisibilityApplication", async () => {
      mockFetch.mockRejectedValue(new Error("Network error"));

      await expect(withdrawVisibilityApplication("app-1", 1)).rejects.toThrow(
        "Network error",
      );
    });
  });
});
