import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

const { exportSkill, toastError } = vi.hoisted(() => ({
  exportSkill: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ skill_id: "skill-1" }),
}));
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading" },
      settings: {
        skills: {
          notFound: "Not found",
          backToSkills: "Back",
          use: "Use",
          edit: "Edit",
          export: "Export",
          exportFailed: "Export failed",
          applyVisibility: "Apply",
          information: "Information",
          license: "License",
          allowedTools: "Tools",
          internet: "Internet",
          required: "Required",
          notRequired: "Not required",
          version: "Version",
          skillMd: "SKILL.md",
          notSpecified: "Not specified",
          readOnly: "Read only",
        },
      },
    },
  }),
}));
vi.mock("sonner", () => ({ toast: { error: toastError, success: vi.fn() } }));
vi.mock("@/core/skills", () => ({
  exportSkill,
  useSkill: () => ({
    skill: {
      resource_id: "skill-1",
      slug: "demo",
      name: "Demo",
      description: "Demo skill",
      summary: "Demo skill",
      category: "custom",
      license: "MIT",
      enabled: true,
      visibility: "private",
      can_modify: true,
      read_only: false,
      allowed_tools: [],
      requires_internet: false,
      latest_version: 1,
      skill_md: "---\nname: demo\ndescription: Demo\n---",
    },
    isLoading: false,
    error: null,
  }),
}));
vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => null,
}));
vi.mock("@/components/workspace/settings/skill-apply-dialog", () => ({
  SkillApplyDialog: () => null,
}));

import SkillDetailPage from "@/app/workspace/capabilities/skills/[skill_id]/page";

describe("SkillDetailPage export", () => {
  beforeEach(() => vi.clearAllMocks());

  test("shows a localized error when export fails", async () => {
    exportSkill.mockRejectedValueOnce(new Error("network"));
    render(<SkillDetailPage />);

    await userEvent.click(screen.getByRole("button", { name: "Export" }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Export failed"),
    );
  });
});
