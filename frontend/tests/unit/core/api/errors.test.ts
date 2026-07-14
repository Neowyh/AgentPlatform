import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

describe("errors", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("parseErrorDetail", () => {
    test("returns parsed body and detail on valid JSON", async () => {
      const { parseErrorDetail } = await import("@/core/api/errors");
      const res = new Response(
        JSON.stringify({ detail: "Something went wrong" }),
        { status: 400 },
      );

      const result = await parseErrorDetail(res);

      expect(result).toBeDefined();
      expect(result!.detail).toBe("Something went wrong");
      expect(result!.body).toEqual({ detail: "Something went wrong" });
    });

    test("returns undefined when body is not valid JSON", async () => {
      const { parseErrorDetail } = await import("@/core/api/errors");
      const res = new Response("not json", { status: 500 });

      const result = await parseErrorDetail(res);

      expect(result).toBeUndefined();
    });

    test("handles missing detail field", async () => {
      const { parseErrorDetail } = await import("@/core/api/errors");
      const res = new Response(JSON.stringify({ other: "field" }), {
        status: 400,
      });

      const result = await parseErrorDetail(res);

      expect(result).toBeDefined();
      expect(result!.detail).toBeUndefined();
    });
  });

  describe("formatDetail", () => {
    test("formats array of validation errors", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = [
        { msg: "field required", loc: ["body", "name"] },
        { msg: "invalid type", loc: ["body", "age"] },
      ];

      const result = formatDetail(detail, "Test action", "Bad Request");

      expect(result).toContain("body.name: field required");
      expect(result).toContain("body.age: invalid type");
    });

    test("formats array errors without loc", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = [{ msg: "some error" }];

      const result = formatDetail(detail, "Test action", "Bad Request");

      expect(result).toBe("some error");
    });

    test("formats object detail with message property", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = { message: "Custom error message" };

      const result = formatDetail(detail, "Test action", "Bad Request");

      expect(result).toBe("Custom error message");
    });

    test("formats object detail without message property", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = { code: "ERR_001" };

      const result = formatDetail(detail, "Test action", "Bad Request");

      expect(result).toBe('{"code":"ERR_001"}');
    });

    test("formats string detail directly", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const result = formatDetail("Simple error", "Test action", "Bad Request");

      expect(result).toBe("Simple error");
    });

    test("falls back to action: statusText for undefined detail", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const result = formatDetail(undefined, "Test action", "Bad Request");

      expect(result).toBe("Test action: Bad Request");
    });
  });

  describe("formatErrorMessage", () => {
    test("returns formatted message from valid JSON response", async () => {
      const { formatErrorMessage } = await import("@/core/api/errors");
      const res = new Response(JSON.stringify({ detail: "Not found" }), {
        status: 404,
        statusText: "Not Found",
      });

      const result = await formatErrorMessage(res, "Load item");

      expect(result).toBe("Not found");
    });

    test("falls back to statusText when JSON parse fails", async () => {
      const { formatErrorMessage } = await import("@/core/api/errors");
      const res = new Response("not json", {
        status: 500,
        statusText: "Internal Server Error",
      });

      const result = await formatErrorMessage(res, "Load item");

      expect(result).toBe("Load item: Internal Server Error");
    });

    test("formats validation errors from FastAPI", async () => {
      const { formatErrorMessage } = await import("@/core/api/errors");
      const res = new Response(
        JSON.stringify({
          detail: [{ msg: "field required", loc: ["body", "email"] }],
        }),
        { status: 422, statusText: "Unprocessable Entity" },
      );

      const result = await formatErrorMessage(res, "Create user");

      expect(result).toContain("body.email: field required");
    });

    test("uses the custom error message when detail is absent", async () => {
      const { formatErrorMessage } = await import("@/core/api/errors");
      const res = new Response(
        JSON.stringify({
          success: false,
          error: { message: "Quota exceeded" },
        }),
        { status: 429, statusText: "Too Many Requests" },
      );

      await expect(formatErrorMessage(res, "Create run")).resolves.toBe(
        "Quota exceeded",
      );
    });

    test("uses the action and status when no detail or custom message exists", async () => {
      const { formatErrorMessage } = await import("@/core/api/errors");
      const res = new Response(JSON.stringify({ success: false }), {
        status: 500,
        statusText: "Internal Server Error",
      });

      await expect(formatErrorMessage(res, "Create run")).resolves.toBe(
        "Create run: Internal Server Error",
      );
    });
  });

  describe("extractError", () => {
    test("throws Error with formatted message", async () => {
      const { extractError } = await import("@/core/api/errors");
      const res = new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
        statusText: "Forbidden",
      });

      await expect(extractError(res, "Delete resource")).rejects.toThrow(
        "Forbidden",
      );
    });

    test("throws Error with statusText fallback on parse failure", async () => {
      const { extractError } = await import("@/core/api/errors");
      const res = new Response("not json", {
        status: 500,
        statusText: "Internal Server Error",
      });

      await expect(extractError(res, "Load data")).rejects.toThrow(
        "Load data: Internal Server Error",
      );
    });
  });
});
