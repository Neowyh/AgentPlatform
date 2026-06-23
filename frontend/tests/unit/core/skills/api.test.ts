import { describe, test, expect, vi, afterEach } from "vitest";

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn(),
  formatErrorMessage: vi.fn(),
}));

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_BACKEND_BASE_URL: "http://localhost:8000",
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

describe("skills api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe("loadSkills", () => {
    test("returns skills list on success", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(
          JSON.stringify({
            skills: [
              {
                name: "test-skill",
                description: "A test skill",
                category: "testing",
                license: "MIT",
                enabled: true,
              },
            ],
          }),
          { status: 200 },
        ),
      );

      const { loadSkills } = await import("@/core/skills/api");
      const result = await loadSkills();

      expect(result).toHaveLength(1);
      expect(result[0]!.name).toBe("test-skill");
      expect(result[0]!.enabled).toBe(true);
    });

    test("calls extractError on non-ok response", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, statusText: "Not Found" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Not found"));

      const { loadSkills } = await import("@/core/skills/api");
      await expect(loadSkills()).rejects.toThrow("Not found");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to load skills",
      );
    });
  });

  describe("enableSkill", () => {
    test("sends PUT request with correct body", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(new Response(null, { status: 200 }));

      const { enableSkill } = await import("@/core/skills/api");
      await enableSkill("my-skill", true);

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/skills/my-skill",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ enabled: true }),
        }),
      );
    });

    test("calls extractError on failure", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const errorResponse = new Response(
        JSON.stringify({ detail: "Not found" }),
        { status: 404, statusText: "Not Found" },
      );
      vi.mocked(fetcher).mockResolvedValue(errorResponse);

      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("Not found"));

      const { enableSkill } = await import("@/core/skills/api");
      await expect(enableSkill("my-skill", false)).rejects.toThrow("Not found");

      expect(extractError).toHaveBeenCalledWith(
        errorResponse,
        "Failed to disable skill",
      );
    });
  });

  describe("installSkill", () => {
    test("returns success response on ok", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const successResponse = {
        success: true,
        skill_name: "new-skill",
        message: "Installed",
      };
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify(successResponse), { status: 200 }),
      );

      const { installSkill } = await import("@/core/skills/api");
      const result = await installSkill({
        thread_id: "t1",
        path: "/skills/new-skill",
      });

      expect(result.success).toBe(true);
      expect(result.skill_name).toBe("new-skill");
    });

    test("returns failure response on non-ok status", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ detail: "Conflict" }), {
          status: 409,
          statusText: "Conflict",
        }),
      );

      const { formatErrorMessage } = await import("@/core/api/errors");
      vi.mocked(formatErrorMessage).mockResolvedValue("Conflict error");

      const { installSkill } = await import("@/core/skills/api");
      const result = await installSkill({
        thread_id: "t1",
        path: "/skills/new-skill",
      });

      expect(result.success).toBe(false);
      expect(result.skill_name).toBe("");
      expect(result.message).toBe("Conflict error");
    });
  });
});
