import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useAgent: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  exportAgent: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ agent_name: "fault-zeroing" }),
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));
vi.mock("sonner", () => ({
  toast: { error: mocks.toastError, success: vi.fn() },
}));
vi.mock("@/core/agents", () => ({ useAgent: mocks.useAgent }));
vi.mock("@/core/skills", () => ({
  useSkills: () => ({
    skills: [{ slug: "code-review", name: "代码变更评审" }],
  }),
}));
vi.mock("@/core/agents/api", () => ({ exportAgent: mocks.exportAgent }));
vi.mock("@/core/visibility-applications/api", () => ({
  changeResourceVisibility: vi.fn(),
  createVisibilityApplication: vi.fn(),
}));
vi.mock("@/components/workspace/workspace-breadcrumb", () => ({
  WorkspaceBreadcrumb: () => <div data-testid="breadcrumb" />,
}));
vi.mock("@/components/workspace/resources/visibility-impact-panel", () => ({
  VisibilityImpactPanel: () => null,
}));
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      common: { loading: "Loading", cancel: "Cancel", edit: "Edit" },
      resources: { experts: "Experts" },
      agents: {
        startChatting: "Chat",
        detailChat: "Chat",
        applyVisibility: "Change visibility",
        changeVisibility: "Change visibility",
        edit: "Edit",
        export: "Export",
        notFound: "Expert not found",
        configuration: "Basic information",
        model: "Model",
        defaultModel: "Default model",
        toolGroups: "Tool groups",
        skills: "Skills",
        source: "Source definition",
        notSpecified: "Not specified",
        exportFailed: "Export failed",
        visibility: "Visibility",
        visibilityPrivate: "Private",
        visibilityDepartment: "Department",
        visibilityPublic: "Public",
        applyVisibilityDescription: "Apply",
        targetVisibility: "Target",
        reason: "Reason",
        reasonPlaceholder: "Reason",
        submit: "Submit",
        confirm: "Confirm",
        downgradeConfirmTitle: "Confirm",
        downgradeConfirmDescription: "Confirm",
        visibilityReasonRequired: "Required",
        applicationSubmitted: "Submitted",
        visibilityUpdated: "Updated",
      },
    },
  }),
}));

import AgentDetailPage from "@/app/workspace/capabilities/experts/[agent_name]/page";

const agent = {
  resource_id: "agent-1",
  slug: "fault-zeroing",
  name: "故障归零专家",
  description: "基于证据构建故障报告",
  model: "gpt-4",
  tool_groups: ["file:read"],
  skills: ["code-review"],
  soul: "Be evidence-led.",
  read_only: false,
  visibility: "private",
};

describe("AgentDetailPage unified resource detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useAgent.mockReturnValue({ agent, isLoading: false, error: null });
  });

  test("renders the shared resource identity and localized actions", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("故障归零专家")).toBeInTheDocument();
    expect(screen.queryByText("Experts")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
  });

  test("shows real configuration and source without placeholder statistics", () => {
    render(<AgentDetailPage />);
    expect(screen.getByText("Basic information")).toBeInTheDocument();
    expect(screen.getByText("代码变更评审")).toBeInTheDocument();
    expect(screen.queryByText("How to use")).not.toBeInTheDocument();
    expect(screen.getByText("Be evidence-led.")).toBeInTheDocument();
    expect(screen.queryByText("Conversations")).not.toBeInTheDocument();
    expect(screen.queryByText("--")).not.toBeInTheDocument();
  });

  test("hides modification actions for read-only experts", () => {
    mocks.useAgent.mockReturnValue({
      agent: { ...agent, read_only: true },
      isLoading: false,
      error: null,
    });
    render(<AgentDetailPage />);
    expect(
      screen.queryByRole("link", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Export" }),
    ).not.toBeInTheDocument();
  });

  test("uses the canonical resource id for export", async () => {
    mocks.exportAgent.mockResolvedValue(new Blob(["zip"]));
    render(<AgentDetailPage />);
    await userEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(mocks.exportAgent).toHaveBeenCalledWith("agent-1");
  });
});
