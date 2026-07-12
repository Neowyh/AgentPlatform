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

      expect(fetcher).toHaveBeenLastCalledWith(
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

  describe("visibility application requests", () => {
    test("submits a skill visibility application using the current API contract", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "app-1",
            resource_type: "skill",
            resource_id: "my-skill",
            applicant_id: "user-1",
            current_visibility: "private",
            target_visibility: "department",
            department_id: "dept-1",
            reason: "share",
            status: "pending",
            submitted_at: "2024-01-01T00:00:00Z",
            reviewed_by: null,
            reviewed_at: null,
            review_comment: null,
            version: 1,
          }),
          { status: 200 },
        ),
      );
      const { createVisibilityApplication } =
        await import("@/core/visibility-applications/api");

      await expect(
        createVisibilityApplication({
          resource_type: "skill",
          resource_id: "my-skill",
          target_visibility: "department",
          reason: "share",
        }),
      ).resolves.toEqual({
        id: "app-1",
        resource_type: "skill",
        resource_id: "my-skill",
        applicant_id: "user-1",
        current_visibility: "private",
        target_visibility: "department",
        department_id: "dept-1",
        reason: "share",
        status: "pending",
        submitted_at: "2024-01-01T00:00:00Z",
        reviewed_by: null,
        reviewed_at: null,
        review_comment: null,
        version: 1,
      });
      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/visibility-applications",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resource_type: "skill",
            resource_id: "my-skill",
            target_visibility: "department",
            reason: "share",
          }),
        },
      );
    });
  });

  describe("listSkillApplications", () => {
    test("lists skill applications with optional status", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ applications: [] }), { status: 200 }),
      );

      const { listSkillApplications } = await import("@/core/skills/api");
      const result = await listSkillApplications("pending");

      expect(result).toEqual({ applications: [] });
      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/visibility-applications?status=pending&resource_type=skill",
      );
    });

    test("lists skill applications without status", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ applications: [] }), { status: 200 }),
      );

      const { listSkillApplications } = await import("@/core/skills/api");
      await listSkillApplications();

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/visibility-applications?resource_type=skill",
      );
    });

    test("delegates list failures to extractError", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const response = new Response("{}", { status: 500 });
      vi.mocked(fetcher).mockResolvedValue(response);
      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("list failed"));

      const { listSkillApplications } = await import("@/core/skills/api");

      await expect(listSkillApplications()).rejects.toThrow("list failed");
      expect(extractError).toHaveBeenCalledWith(
        response,
        "Failed to list skill applications",
      );
    });
  });

  describe("reviewSkillApplication", () => {
    test("reviews an application with encoded id", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(JSON.stringify({ message: "ok" }), { status: 200 }),
      );

      const { reviewSkillApplication } = await import("@/core/skills/api");
      const result = await reviewSkillApplication(
        "app/1",
        "approved",
        "looks good",
      );

      expect(result).toEqual({ message: "ok" });
      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/visibility-applications/app%2F1",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            action: "approved",
            comment: "looks good",
            version: 1,
          }),
        }),
      );
    });

    test("delegates review failures to extractError", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      const response = new Response("{}", { status: 400 });
      vi.mocked(fetcher).mockResolvedValue(response);
      const { extractError } = await import("@/core/api/errors");
      vi.mocked(extractError).mockRejectedValue(new Error("review failed"));

      const { reviewSkillApplication } = await import("@/core/skills/api");

      await expect(reviewSkillApplication("app-1", "rejected")).rejects.toThrow(
        "review failed",
      );
      expect(extractError).toHaveBeenCalledWith(
        response,
        "Failed to review skill application",
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
