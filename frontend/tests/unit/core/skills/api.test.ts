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
    test("returns canonical skills on success", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "11111111-1111-1111-1111-111111111111",
                type: "skill",
                slug: "test-skill",
                display_name: "test-skill",
                owner_id: "owner",
                visibility: "public",
                scope_department_id: null,
                system_owned: false,
                can_modify: true,
              },
            ],
            total: 1,
          }),
          { status: 200 },
        ),
      );

      const { loadSkills } = await import("@/core/skills/api");
      const result = await loadSkills();

      expect(fetcher).toHaveBeenCalledTimes(1);
      expect(result).toHaveLength(1);
      expect(result[0]!.name).toBe("test-skill");
      expect(result[0]!.enabled).toBe(true);
      expect(result[0]!.category).toBe("custom");
    });

    test("maps canonical Skills and keeps UUID identity separate from display name", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "11111111-1111-1111-1111-111111111111",
                type: "skill",
                slug: "review-skill",
                display_name: "Review Skill",
                owner_id: "owner",
                visibility: "public",
                scope_department_id: null,
                can_modify: false,
              },
            ],
            total: 1,
          }),
          { status: 200 },
        ),
      );

      const { loadSkills } = await import("@/core/skills/api");

      await expect(loadSkills()).resolves.toEqual([
        expect.objectContaining({
          resource_id: "11111111-1111-1111-1111-111111111111",
          name: "Review Skill",
          slug: "review-skill",
          category: "public",
          read_only: true,
        }),
      ]);
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
        "Failed to load canonical skills",
      );
    });
  });

  describe("enableSkill", () => {
    test("throws a readable lifecycle error and never calls the legacy endpoint", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockClear();

      const { enableSkill } = await import("@/core/skills/api");
      await expect(
        enableSkill("11111111-1111-1111-1111-111111111111", false),
      ).rejects.toThrow(/canonical/i);

      expect(fetcher).not.toHaveBeenCalled();
    });
  });

  describe("canonical Skill management", () => {
    test("imports a .skill archive through the canonical endpoint", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(new Response(null, { status: 201 }));

      const { importSkill } = await import("@/core/skills/api");
      await importSkill(new File(["archive"], "review.skill"));

      expect(fetcher).toHaveBeenCalledWith(
        "http://localhost:8000/api/resources/import/skill",
        expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
      );
    });

    test("archives, exports, and favorites canonical Skills by resource id", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockClear();
      vi.mocked(fetcher)
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockResolvedValueOnce(new Response("archive", { status: 200 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 }));
      const { archiveSkill, exportSkill, toggleSkillFavorite } =
        await import("@/core/skills/api");

      await archiveSkill("skill/id");
      await exportSkill("skill/id");
      await toggleSkillFavorite("skill/id", false);
      await toggleSkillFavorite("skill/id", true);

      expect(fetcher).toHaveBeenNthCalledWith(
        1,
        "http://localhost:8000/api/resources/skill%2Fid/archive",
        { method: "POST" },
      );
      expect(fetcher).toHaveBeenNthCalledWith(
        2,
        "http://localhost:8000/api/resources/skill%2Fid/export",
      );
      expect(fetcher).toHaveBeenNthCalledWith(
        3,
        "http://localhost:8000/api/resources/skill%2Fid/favorite",
        { method: "POST" },
      );
      expect(fetcher).toHaveBeenNthCalledWith(
        4,
        "http://localhost:8000/api/resources/skill%2Fid/favorite",
        { method: "DELETE" },
      );
    });
  });

  describe("visibility application requests", () => {
    test("submits a skill visibility application through the canonical resource endpoint", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "app-1",
            resource_type: "skill",
            resource_id: "11111111-1111-1111-1111-111111111111",
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
          resource_id: "11111111-1111-1111-1111-111111111111",
          target_visibility: "department",
          reason: "share",
        }),
      ).resolves.toEqual({
        id: "app-1",
        resource_type: "skill",
        resource_id: "11111111-1111-1111-1111-111111111111",
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
        "http://localhost:8000/api/resources/11111111-1111-1111-1111-111111111111/visibility-applications",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
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
    test("returns a canonical-mode degradation message without calling the network", async () => {
      const { fetch: fetcher } = await import("@/core/api/fetcher");
      vi.mocked(fetcher).mockClear();

      const { installSkill } = await import("@/core/skills/api");
      const result = await installSkill({
        thread_id: "t1",
        path: "/skills/new-skill",
      });

      expect(result.success).toBe(false);
      expect(result.skill_name).toBe("");
      expect(result.message).toMatch(/canonical mode/i);
      expect(fetcher).not.toHaveBeenCalled();
    });
  });
});
