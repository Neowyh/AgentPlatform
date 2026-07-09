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

import {
  listUsers,
  updateUserRole,
  listDepartments,
  createDepartment,
  updateDepartment,
  deleteDepartment,
  getAdminStats,
  listTools,
  testTool,
} from "@/core/admin/api";
import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";

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

describe("admin API", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // ── listUsers ───────────────────────────────────────────────────

  describe("listUsers", () => {
    test("sends GET request with clean URL when no params", async () => {
      const payload = { users: [], total: 0, limit: 20, offset: 0 };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await listUsers();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/users");
      expect(result).toEqual(payload);
    });

    test("includes query params when provided", async () => {
      mockFetch.mockResolvedValue(
        okJson({ users: [], total: 0, limit: 10, offset: 5 }),
      );

      await listUsers({
        department_id: "d1",
        role: "admin",
        limit: 10,
        offset: 5,
      });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("department_id")).toBe("d1");
      expect(url.searchParams.get("role")).toBe("admin");
      expect(url.searchParams.get("limit")).toBe("10");
      expect(url.searchParams.get("offset")).toBe("5");
    });
  });

  // ── updateUserRole ──────────────────────────────────────────────

  describe("updateUserRole", () => {
    test("sends PUT request with correct body", async () => {
      const payload = { success: true, user_id: "u1", new_role: "admin" };
      mockFetch.mockResolvedValue(okJson(payload));

      await updateUserRole("u1", "admin");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/users/u1/role");

      const init = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(init.method).toBe("PUT");
      expect(JSON.parse(init.body as string)).toEqual({ role: "admin" });
    });
  });

  // ── listDepartments ─────────────────────────────────────────────

  describe("listDepartments", () => {
    test("sends GET request with clean URL when no params", async () => {
      const payload = { departments: [], total: 0, limit: 20, offset: 0 };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await listDepartments();

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/departments");
      expect(result).toEqual(payload);
    });

    test("includes limit and offset in query string", async () => {
      mockFetch.mockResolvedValue(
        okJson({ departments: [], total: 0, limit: 20, offset: 10 }),
      );

      await listDepartments({ limit: 20, offset: 10 });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("limit")).toBe("20");
      expect(url.searchParams.get("offset")).toBe("10");
    });
  });

  // ── createDepartment ────────────────────────────────────────────

  describe("createDepartment", () => {
    test("sends POST request with body", async () => {
      const payload = {
        id: "new-id",
        name: "Test",
        description: "Desc",
        member_count: 0,
        agent_count: 0,
        skill_count: 0,
        created_at: "2024-01-01T00:00:00Z",
      };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await createDepartment({
        name: "Test",
        description: "Desc",
      });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/departments");

      const init = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(init.method).toBe("POST");
      expect(JSON.parse(init.body as string)).toEqual({
        name: "Test",
        description: "Desc",
      });
      expect(result).toEqual(payload);
    });
  });

  // ── updateDepartment ────────────────────────────────────────────

  describe("updateDepartment", () => {
    test("sends PUT request with body", async () => {
      mockFetch.mockResolvedValue(okJson({ success: true }));

      await updateDepartment("dept-1", { name: "Updated" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/admin/departments/dept-1",
      );

      const init = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(init.method).toBe("PUT");
      expect(JSON.parse(init.body as string)).toEqual({ name: "Updated" });
    });
  });

  // ── deleteDepartment ────────────────────────────────────────────

  describe("deleteDepartment", () => {
    test("sends DELETE request", async () => {
      mockFetch.mockResolvedValue(okJson(undefined));

      await deleteDepartment("dept-1");

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe(
        "http://localhost:8000/api/admin/departments/dept-1",
      );

      const init = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(init.method).toBe("DELETE");
    });
  });

  // ── getAdminStats ───────────────────────────────────────────────

  describe("getAdminStats", () => {
    test("sends GET request", async () => {
      const payload = {
        total_users: 10,
        total_departments: 3,
        total_agents: 5,
        total_skills: 8,
      };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await getAdminStats();

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/admin/stats");
      expect(result).toEqual(payload);
    });
  });

  // ── listTools ───────────────────────────────────────────────────

  describe("listTools", () => {
    test("sends GET request with clean URL when no params", async () => {
      const payload = { tools: [], total: 0 };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await listTools();

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/tools");
      expect(result).toEqual(payload);
    });

    test("includes group and search in query string", async () => {
      mockFetch.mockResolvedValue(okJson({ tools: [], total: 0 }));

      await listTools({ group: "g1", search: "q" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      const url = new URL(calledUrl);
      expect(url.searchParams.get("group")).toBe("g1");
      expect(url.searchParams.get("search")).toBe("q");
    });
  });

  // ── testTool ────────────────────────────────────────────────────

  describe("testTool", () => {
    test("sends POST request with body", async () => {
      const payload = { success: true, tool: "myTool", result: "ok" };
      mockFetch.mockResolvedValue(okJson(payload));

      const result = await testTool("myTool", { param: "value" });

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/tools/myTool/test");

      const init = mockFetch.mock.calls[0]![1] as RequestInit;
      expect(init.method).toBe("POST");
      expect(JSON.parse(init.body as string)).toEqual({
        params: { param: "value" },
      });
      expect(result).toEqual(payload);
    });

    test("URL-encodes tool name", async () => {
      mockFetch.mockResolvedValue(okJson({ success: true, tool: "a/b" }));

      await testTool("a/b", {});

      const calledUrl = mockFetch.mock.calls[0]![0] as string;
      expect(calledUrl).toBe("http://localhost:8000/api/tools/a%2Fb/test");
    });
  });

  // ── error cases ─────────────────────────────────────────────────

  describe("error handling", () => {
    test("calls extractError when listUsers returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(listUsers()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledTimes(1);
      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to list users",
      );
    });

    test("calls extractError when updateUserRole returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(updateUserRole("u1", "admin")).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to update user role",
      );
    });

    test("calls extractError when listDepartments returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(listDepartments()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to list departments",
      );
    });

    test("calls extractError when createDepartment returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(createDepartment({ name: "X" })).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to create department",
      );
    });

    test("calls extractError when updateDepartment returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(updateDepartment("d1", { name: "X" })).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to update department",
      );
    });

    test("calls extractError when deleteDepartment returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(deleteDepartment("d1")).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to delete department",
      );
    });

    test("calls extractError when getAdminStats returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(getAdminStats()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to get admin stats",
      );
    });

    test("calls extractError when listTools returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(listTools()).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to list tools",
      );
    });

    test("calls extractError when testTool returns non-ok", async () => {
      mockFetch.mockResolvedValue(notOkJson());

      await expect(testTool("tool", {})).rejects.toThrow();

      expect(mockExtractError).toHaveBeenCalledWith(
        expect.anything(),
        "Failed to test tool",
      );
    });
  });
});
