import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockUser = {
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
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
  mockFetchApplications.mockResolvedValue(mockListResponse);
  mockReviewApplication.mockResolvedValue({ id: "app-1", version: 2 });
  mockWithdrawApplication.mockResolvedValue({ success: true });

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

  test("shows status filter buttons", async () => {
    render(<VisibilityApplicationsPage />);
    await waitFor(() => {
      expect(screen.getByText("web-search")).toBeInTheDocument();
    });
    expect(screen.getAllByText("待审批").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("已批准").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("已拒绝").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("已撤回").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("全部").length).toBeGreaterThanOrEqual(1);
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
});
