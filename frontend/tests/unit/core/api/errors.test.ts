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

    test("formats visibility closure violations into a localized list", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        message:
          'Dependency violates visibility closure: agent "fault-zeroing" cannot be made public',
        violations: [
          {
            source: {
              slug: "fault-zeroing",
              display_name: "fault-zeroing",
              type: "agent",
            },
            target: {
              slug: "fault-zeroing-skill",
              display_name: "fault-zeroing",
              type: "skill",
              visibility: "private",
            },
            required_visibility: "public",
          },
        ],
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toContain("无法将智能体「fault-zeroing」提升为公开");
      expect(result).toContain(
        "Skill「fault-zeroing」（当前：私有）→ 需提升为公开",
      );
      expect(result).toContain("可行路径");
      expect(result).not.toContain("Dependency violates visibility closure");
    });

    test("renders each violation on its own line for multiple violations", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        violations: [
          { target: { slug: "skill-a", type: "skill", visibility: "private" } },
          {
            target: {
              slug: "skill-b",
              type: "skill",
              visibility: "department",
            },
          },
        ],
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toContain("- Skill「skill-a」（当前：私有）");
      expect(result).toContain("- Skill「skill-b」（当前：部门）");
      expect(result).toContain("可行路径");
    });

    test("suggests self-application path when dependency is owned by the actor", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        violations: [
          {
            source: { slug: "my-agent", type: "agent" },
            target: { slug: "my-skill", type: "skill", visibility: "private" },
            required_visibility: "public",
            owned_by_actor: true,
          },
        ],
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toContain("你拥有这些依赖");
      expect(result).toContain("提交可见性提升申请");
    });

    test("suggests contacting the owner when dependency is not owned by the actor", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        violations: [
          {
            source: { slug: "my-agent", type: "agent" },
            target: {
              slug: "their-skill",
              type: "skill",
              visibility: "private",
            },
            required_visibility: "public",
            owned_by_actor: false,
          },
        ],
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toContain("这些依赖由他人拥有");
      expect(result).toContain("联系其拥有者提升可见性");
    });

    test("formats department visibility closure with department-aware wording", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        violations: [
          {
            source: { slug: "my-agent", type: "agent" },
            target: { slug: "my-skill", type: "skill", visibility: "private" },
            required_visibility: "department",
            owned_by_actor: true,
          },
        ],
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toContain("无法将智能体「my-agent」提升为部门可见");
      expect(result).toContain("需为公开或与本资源同部门");
    });

    test("falls back to raw message when no violations are present", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "visibility_closure_violation",
        message: "raw closure message",
      };

      const result = formatDetail(detail, "Review", "Conflict");

      expect(result).toBe("raw closure message");
    });

    test("formats invalid_file_roots with violation lines and the fix path", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "invalid_file_roots",
        message: "无法启动工作流：2 个文件访问路径不在允许的挂载范围内",
        violations: [
          {
            node_id: "evidence_collection",
            access: "read",
            path: "/mnt/eval-cases/case_01",
          },
          {
            node_id: "evidence_collection",
            access: "write",
            path: "/mnt/fault-zeroing-outputs/out",
          },
        ],
      };

      const result = formatDetail(detail, "Create run", "Bad Request");

      expect(result).toContain("2 个文件访问路径不在允许的挂载范围内");
      expect(result).toContain(
        "节点「evidence_collection」：read /mnt/eval-cases/case_01",
      );
      expect(result).toContain(
        "节点「evidence_collection」：write /mnt/fault-zeroing-outputs/out",
      );
      expect(result).toContain("挂载配置");
      expect(result).not.toContain("提升为公开");
    });

    test("formats missing_input_roots with the missing-paths summary", async () => {
      const { formatDetail } = await import("@/core/api/errors");
      const detail = {
        code: "missing_input_roots",
        violations: [
          {
            node_id: "collect",
            access: "read",
            path: "/mnt/eval-cases/case_missing",
          },
        ],
      };

      const result = formatDetail(detail, "Create run", "Bad Request");

      expect(result).toContain("1 个输入路径缺失或为空");
      expect(result).toContain(
        "节点「collect」：read /mnt/eval-cases/case_missing",
      );
    });

    test("caps long violation lists at 20 with an overflow line", async () => {
      const { formatWorkflowRootViolations } =
        await import("@/core/api/errors");
      const violations = Array.from({ length: 25 }, (_, i) => ({
        node_id: `node-${i}`,
        access: "read",
        path: `/mnt/cases/case_${i}`,
      }));

      const result = formatWorkflowRootViolations({
        code: "invalid_file_roots",
        violations,
      });

      const rendered = result
        .split("\n")
        .filter((line) => line.startsWith("- 节点"));
      expect(rendered).toHaveLength(20);
      expect(result).toContain("另有 5 条");
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
