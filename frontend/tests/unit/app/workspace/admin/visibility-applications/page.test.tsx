import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockUser: {
  id: string;
  system_role: string;
  email: string;
} | null = {
  id: "user-1",
  system_role: "super_admin",
  email: "admin@test.com",
};

const mockApplications = [
  {
    id: "app-1",
    resource_type: "tool",
    resource_id: "web-search",
    applicant_id: "user-2",
    current_visibility: "private",
    target_visibility: "public",
    department_id: "dept-1",
    reason: "Need public access",
    status: "pending",
    submitted_at: "2025-01-15T10:00:00Z",
    reviewed_by: null,
    reviewed_at: null,
    review_comment: null,
    version: 1,
  },
  {
    id: "app-2",
    resource_type: "skill",
    resource_id: "code-review",
    applicant_id: "user-3",
    current_visibility: "private",
    target_visibility: "department",
    department_id: "dept-1",
    reason: "Share with department",
    status: "approved",
    submitted_at: "2025-01-14T10:00:00Z",
    reviewed_by: "admin-1",
    reviewed_at: "2025-01-14T12:00:00Z",
    review_comment: "Approved",
    version: 2,
  },
  {
    id: "app-3",
    resource_type: "workflow",
    resource_id: "data-pipeline",
    applicant_id: "user-1",
    current_visibility: "department",
    target_visibility: "public",
    department_id: "dept-1",
    reason: "Open source contribution",
    status: "pending",
    submitted_at: "2025-01-15T11:00:00Z",
    reviewed_by: null,
    reviewed_at: null,
    review_comment: null,
    version: 1,
  },
];

const mockListResponse = {
  applications: mockApplications,
  total: 3,
  page: 1,
  page_size: 20,
};

const mockFetchApplications = vi.fn();
const mockReviewApplication = vi.fn();
const mockWithdrawApplication = vi.fn();
const mockRouterReplace = vi.fn();
const mockListUsers = vi.fn();

const mockUsers = [
  { id: "user-2", username: "alice", role: "user" },
  { id: "user-3", username: "bob", role: "user" },
];

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock("@/core/visibility-applications/api", () => ({
  listVisibilityApplications: (...args: unknown[]) =>
    mockFetchApplications(...args),
  reviewVisibilityApplication: (...args: unknown[]) =>
    mockReviewApplication(...args),
  withdrawVisibilityApplication: (...args: unknown[]) =>
    mockWithdrawApplication(...args),
}));

vi.mock("@/core/admin/api", () => ({
  listUsers: (...args: unknown[]) => mockListUsers(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let VisibilityApplicationsPage: typeof import("@/app/workspace/admin/visibility-applications/page").default;

beforeEach(async () => {
  vi.clearAllMocks();
  mockUser = {
    id: "user-1",
    system_role: "super_admin",
    email: "admin@test.com",
  };
  mockFetchApplications.mockResolvedValue(mockListResponse);
  mockReviewApplication.mockResolvedValue({ id: "app-1", version: 2 });
  mockWithdrawApplication.mockResolvedValue({ success: true });
  mockListUsers.mockResolvedValue({
    users: mockUsers,
    total: 2,
    limit: 500,
    offset: 0,
  });

  const mod =
    await import("@/app/workspace/admin/visibility-applications/page");
  VisibilityApplicationsPage = mod.default;
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("VisibilityApplicationsPage", () => {
  test("renders page title and header", async () => {
    render(<VisibilityApplicationsPage />);
    expect(screen.getByText("统一审批中心")).toBeInTheDocument();
    expect(
      screen.getByText("审批所有资源的可见性变更申请"),
    ).toBeInTheDocument();
  });

  test("shows loading state initially", () => {
    mockFetchApplications.mockReturnValue(new Promise(() => {}));
    render(<VisibilityApplicationsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
  });

  test("renders application cards after loading", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(screen.getByText("code-review")).toBeInTheDocument();
    expect(screen.getByText("data-pipeline")).toBeInTheDocument();
  });

  test("shows status filter select defaulting to pending", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(
      screen.getAllByRole("combobox")[0]!.querySelector("span"),
    ).toHaveTextContent("待审批");
    await user.click(screen.getAllByRole("combobox")[0]!);
    expect(screen.getByRole("option", { name: "待审批" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "已批准" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "已拒绝" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "已撤回" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "全部状态" }),
    ).toBeInTheDocument();
  });

  test("shows resource type filter", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(screen.getByText("全部类型")).toBeInTheDocument();
  });

  test("shows total count", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });
  });

  test("shows review button for pending applications", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    const reviewButtons = screen.getAllByText("审核");
    expect(reviewButtons.length).toBe(2);
  });

  test("shows withdraw button for own pending applications", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });
    expect(screen.getByText("撤回")).toBeInTheDocument();
  });

  test("shows only review button for others' applications", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    const allWithdrawButtons = screen.getAllByText("撤回");
    expect(allWithdrawButtons.length).toBe(1);
  });

  test("opens review dialog when review button is clicked", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    const reviewButtons = screen.getAllByText("审核");
    await user.click(reviewButtons[0]!);

    expect(screen.getByText("审核可见性变更申请")).toBeInTheDocument();
    expect(screen.getByText("资源ID: web-search")).toBeInTheDocument();
  });

  test("calls review API when approve is clicked", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    const reviewButtons = screen.getAllByText("审核");
    await user.click(reviewButtons[0]!);

    const approveButton = screen.getByRole("button", { name: "通过" });
    await user.click(approveButton);

    await waitFor(() => {
      expect(mockReviewApplication).toHaveBeenCalledWith(
        "app-1",
        "approved",
        "",
        1,
      );
    });
  });

  test("calls review API with comment when reject is clicked", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    const reviewButtons = screen.getAllByText("审核");
    await user.click(reviewButtons[0]!);

    const commentInput = screen.getByPlaceholderText("请输入审批意见...");
    await user.type(commentInput, "Needs more info");

    const rejectButton = screen.getByRole("button", { name: "驳回" });
    await user.click(rejectButton);

    await waitFor(() => {
      expect(mockReviewApplication).toHaveBeenCalledWith(
        "app-1",
        "rejected",
        "Needs more info",
        1,
      );
    });
  });

  test("opens withdraw confirm dialog", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });

    await user.click(screen.getByText("撤回"));
    expect(
      screen.getByRole("heading", { name: "确认撤回" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("确定要撤回此申请吗？撤回后无法恢复。"),
    ).toBeInTheDocument();
  });

  test("calls withdraw API when confirmed", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });

    await user.click(screen.getByText("撤回"));
    const confirmButton = screen.getByRole("button", { name: "确认撤回" });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockWithdrawApplication).toHaveBeenCalledWith("app-3", 1);
    });
  });

  test("shows empty state when no applications", async () => {
    mockFetchApplications.mockResolvedValue({
      applications: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("没有待审批的申请")).toBeInTheDocument();
    });
  });

  test("shows pagination when more than one page", async () => {
    mockFetchApplications.mockResolvedValue({
      applications: mockApplications,
      total: 40,
      page: 1,
      page_size: 20,
    });
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("1 / 2")).toBeInTheDocument();
    });
    expect(screen.getByText("上一页")).toBeInTheDocument();
    expect(screen.getByText("下一页")).toBeInTheDocument();
  });

  test("uses status and resource filters when fetching", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "已批准" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "approved",
      });
    });

    mockFetchApplications.mockClear();
    await user.click(screen.getAllByRole("combobox")[1]!);
    await user.click(screen.getByRole("option", { name: "工作流" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "approved",
        resource_type: "workflow",
      });
    });
  });

  test("uses visibility filter when fetching", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getAllByRole("combobox")[2]!);
    await user.click(screen.getByRole("option", { name: "部门" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "pending",
        target_visibility: "department",
      });
    });
  });

  test("uses applicant filter when fetching", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getAllByRole("combobox")[3]!);
    await user.click(screen.getByRole("option", { name: "alice" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "pending",
        applicant_id: "user-2",
      });
    });
  });

  test("combines all filters when fetching", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "已批准" }));
    await user.click(screen.getAllByRole("combobox")[1]!);
    await user.click(screen.getByRole("option", { name: "工作流" }));
    await user.click(screen.getAllByRole("combobox")[2]!);
    await user.click(screen.getByRole("option", { name: "部门" }));
    await user.click(screen.getAllByRole("combobox")[3]!);
    await user.click(screen.getByRole("option", { name: "alice" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "approved",
        resource_type: "workflow",
        target_visibility: "department",
        applicant_id: "user-2",
      });
    });
  });

  test("sends status=all when 全部状态 is selected", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "全部状态" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "all",
      });
    });
  });

  test("shows applicant username in cards", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(screen.getByText(/申请人: alice/)).toBeInTheDocument();
    expect(screen.getByText(/申请人: bob/)).toBeInTheDocument();
  });

  test("requests next and previous pages", async () => {
    const user = userEvent.setup();
    mockFetchApplications.mockResolvedValue({
      applications: mockApplications,
      total: 41,
      page: 1,
      page_size: 20,
    });
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("1 / 3")).toBeInTheDocument();
    });
    mockFetchApplications.mockClear();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 2,
        page_size: 20,
        status: "pending",
      });
    });

    mockFetchApplications.mockClear();
    await user.click(screen.getByRole("button", { name: "上一页" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "pending",
      });
    });
  });

  test("shows non-pending empty state", async () => {
    const user = userEvent.setup();
    mockFetchApplications.mockResolvedValue({
      applications: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("没有待审批的申请")).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "全部状态" }));
    await waitFor(() => {
      expect(screen.getByText("没有找到申请记录")).toBeInTheDocument();
    });
  });

  test("shows stringified fetch errors", async () => {
    mockFetchApplications.mockRejectedValue("fetch failed");
    render(<VisibilityApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("fetch failed")).toBeInTheDocument();
    });
  });

  test("shows review errors without closing dialog", async () => {
    const user = userEvent.setup();
    mockReviewApplication.mockRejectedValue(new Error("review failed"));
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    await user.click(screen.getAllByText("审核")[0]!);
    await user.click(screen.getByRole("button", { name: "通过" }));

    await waitFor(() => {
      expect(screen.getByText("review failed")).toBeInTheDocument();
    });
  });

  test("closes review dialog when cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    await user.click(screen.getAllByText("审核")[0]!);
    expect(screen.getByText("审核可见性变更申请")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.queryByText("审核可见性变更申请")).not.toBeInTheDocument();
    });
  });

  test("closes review dialog from dialog open change", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    await user.click(screen.getAllByText("审核")[0]!);
    expect(screen.getByText("审核可见性变更申请")).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByText("审核可见性变更申请")).not.toBeInTheDocument();
    });
  });

  test("shows withdraw errors and resets pending state", async () => {
    const user = userEvent.setup();
    mockWithdrawApplication.mockRejectedValue("withdraw failed");
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });

    await user.click(screen.getByText("撤回"));
    await user.click(screen.getByRole("button", { name: "确认撤回" }));

    await waitFor(() => {
      expect(screen.getByText("withdraw failed")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "确认撤回" }),
      ).not.toBeDisabled();
    });
  });

  test("closes withdraw confirm dialog when cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });

    await user.click(screen.getByText("撤回"));
    expect(
      screen.getByRole("heading", { name: "确认撤回" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: "确认撤回" }),
      ).not.toBeInTheDocument();
    });
  });

  test("closes withdraw confirm dialog from dialog open change", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("data-pipeline")).toBeInTheDocument();
    });

    await user.click(screen.getByText("撤回"));
    expect(
      screen.getByRole("heading", { name: "确认撤回" }),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: "确认撤回" }),
      ).not.toBeInTheDocument();
    });
  });

  test("does not fetch applications outside the admin route boundary", () => {
    mockUser = {
      id: "viewer",
      system_role: "user",
      email: "viewer@test.com",
    };

    render(<VisibilityApplicationsPage />);

    expect(mockFetchApplications).not.toHaveBeenCalled();
  });

  test("shows resource type badges", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("工具")).toBeInTheDocument();
    });
    expect(screen.getByText("Skill")).toBeInTheDocument();
    expect(screen.getByText("工作流")).toBeInTheDocument();
  });

  test("shows visibility change info", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(screen.getByText(/私有 → 公开/)).toBeInTheDocument();
    expect(screen.getByText(/私有 → 部门/)).toBeInTheDocument();
  });

  test("shows review comment and time for reviewed applications", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("code-review")).toBeInTheDocument();
    });
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  test("fetches rejected and withdrawn status filters", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    mockFetchApplications.mockClear();
    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "已拒绝" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "rejected",
      });
    });

    mockFetchApplications.mockClear();
    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "已撤回" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "withdrawn",
      });
    });
  });

  test("fetches pending status after changing away from it", async () => {
    const user = userEvent.setup();
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "已批准" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "approved",
      });
    });

    mockFetchApplications.mockClear();
    await user.click(screen.getAllByRole("combobox")[0]!);
    await user.click(screen.getByRole("option", { name: "待审批" }));
    await waitFor(() => {
      expect(mockFetchApplications).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        status: "pending",
      });
    });
  });

  test("falls back to raw resource and visibility labels", async () => {
    const user = userEvent.setup();
    mockFetchApplications.mockResolvedValue({
      applications: [
        {
          ...mockApplications[0],
          id: "app-custom",
          resource_type: "dataset",
          current_visibility: "team",
          target_visibility: "enterprise",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
    render(<VisibilityApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("dataset")).toBeInTheDocument();
    });
    await user.click(screen.getByText("审核"));
    expect(screen.getByText("资源类型: dataset")).toBeInTheDocument();
    expect(
      screen.getByText(/可见性变更: team\s+→\s+enterprise/),
    ).toBeInTheDocument();
  });
});
