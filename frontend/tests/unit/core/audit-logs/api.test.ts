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
import { listAuditLogs, getAuditLogDetail } from "@/core/audit-logs/api";
import type { AuditLog, AuditLogListResponse } from "@/core/audit-logs/types";

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

const sampleLog: AuditLog = {
  id: "log-1",
  actor_id: "user-1",
  action: "create",
  resource_type: "agent",
  resource_id: "agent-1",
  detail: "Created agent",
  ip_address: "127.0.0.1",
  created_at: "2024-01-01T00:00:00Z",
};

const sampleListResponse: AuditLogListResponse = {
  items: [sampleLog],
  total: 1,
  page: 1,
  page_size: 20,
};

describe("audit-logs API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // ── listAuditLogs ────────────────────────────────────────────────

  describe("listAuditLogs", () => {
    test("sends GET request with clean URL when no params", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      const result = await listAuditLogs();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/audit-logs");
      expect(result).toEqual(sampleListResponse);
    });

    test("includes actor_id in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ actor_id: "user-1" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("actor_id")).toBe("user-1");
    });

    test("includes action in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ action: "delete" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("action")).toBe("delete");
    });

    test("includes resource_type in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ resource_type: "agent" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("resource_type")).toBe("agent");
    });

    test("includes start_date and end_date in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({
        start_date: "2024-01-01",
        end_date: "2024-12-31",
      });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("start_date")).toBe("2024-01-01");
      expect(url.searchParams.get("end_date")).toBe("2024-12-31");
    });

    test("includes page and page_size in query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ page: 2, page_size: 10 });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("page")).toBe("2");
      expect(url.searchParams.get("page_size")).toBe("10");
    });

    test("URL-encodes special characters in query params", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ actor_id: "a/b=c&d" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toContain("actor_id=" + encodeURIComponent("a/b=c&d"));
    });

    test("includes all params at once", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({
        actor_id: "u1",
        action: "update",
        resource_type: "thread",
        start_date: "2024-06-01",
        end_date: "2024-06-30",
        page: 3,
        page_size: 5,
      });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("actor_id")).toBe("u1");
      expect(url.searchParams.get("action")).toBe("update");
      expect(url.searchParams.get("resource_type")).toBe("thread");
      expect(url.searchParams.get("start_date")).toBe("2024-06-01");
      expect(url.searchParams.get("end_date")).toBe("2024-06-30");
      expect(url.searchParams.get("page")).toBe("3");
      expect(url.searchParams.get("page_size")).toBe("5");
    });

    test("omits empty-string params from query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ actor_id: "" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/audit-logs");
    });

    test("omits page=0 from query string (falsy)", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ page: 0 });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/audit-logs");
    });

    test("omits empty object params from query string", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({});

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/audit-logs");
    });
  });

  // ── getAuditLogDetail ────────────────────────────────────────────

  describe("getAuditLogDetail", () => {
    test("sends GET request with encoded logId", async () => {
      mockFetch.mockResolvedValue(okJson(sampleLog));

      const result = await getAuditLogDetail("log-1");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/admin/audit-logs/log-1",
      );
      expect(result).toEqual(sampleLog);
    });

    test("URL-encodes special characters in logId", async () => {
      mockFetch.mockResolvedValue(okJson(sampleLog));

      await getAuditLogDetail("a/b=c");

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/admin/audit-logs/a%2Fb%3Dc",
      );
    });
  });

  // ── success path: extractError should NOT be called ────────────────

  describe("success path", () => {
    test("does not call extractError when listAuditLogs succeeds", async () => {
      mockFetch.mockResolvedValue(okJson(sampleListResponse));

      await listAuditLogs({ actor_id: "u1" });

      expect(mockExtractError).not.toHaveBeenCalled();
    });

    test("does not call extractError when getAuditLogDetail succeeds", async () => {
      mockFetch.mockResolvedValue(okJson(sampleLog));

      await getAuditLogDetail("log-1");

      expect(mockExtractError).not.toHaveBeenCalled();
    });
  });

  // ── error handling ───────────────────────────────────────────────

  describe("error handling", () => {
    test("calls extractError with response and message when listAuditLogs returns non-ok", async () => {
      const res = notOkJson(403, "Forbidden");
      mockFetch.mockResolvedValue(res);

      await expect(listAuditLogs()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to list audit logs",
      );
    });

    test("calls extractError with response and message when getAuditLogDetail returns non-ok", async () => {
      const res = notOkJson(404, "Not Found");
      mockFetch.mockResolvedValue(res);

      await expect(getAuditLogDetail("log-1")).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        res,
        "Failed to get audit log detail",
      );
    });
  });

  // ── type exports ─────────────────────────────────────────────────

  describe("type exports", () => {
    test("AuditLog type is exported", () => {
      // Compile-time check: if this builds, the type is correctly exported
      const log: AuditLog = {
        id: "t1",
        actor_id: null,
        action: "login",
        resource_type: null,
        resource_id: null,
        detail: null,
        ip_address: null,
        created_at: "2024-01-01T00:00:00Z",
      };
      expect(log.id).toBe("t1");
    });

    test("AuditLogListResponse type is exported", () => {
      const resp: AuditLogListResponse = {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      };
      expect(resp.items).toEqual([]);
    });
  });
});
