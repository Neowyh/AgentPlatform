import {
  render,
  screen,
  cleanup,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockReplace = vi.fn();
const mockListAuditLogs = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace, prefetch: vi.fn() }),
  usePathname: () => "/workspace/admin/audit-logs",
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/core/audit-logs/api", () => ({
  listAuditLogs: (...args: unknown[]) => mockListAuditLogs(...args),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import AuditLogsPage from "@/app/workspace/admin/audit-logs/page";
import { useAuth } from "@/core/auth/AuthProvider";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

// IDs are designed so .slice(0, 8) gives readable prefixes:
// "log-0001" → "log-0001...", "log-0002" → "log-0002...", etc.
const mockLogs = [
  {
    id: "log-0001abc",
    actor_id: "user-1",
    action: "create",
    resource_type: "tool",
    resource_id: "tool-1",
    detail: JSON.stringify({ name: "test tool" }),
    ip_address: "192.168.1.1",
    created_at: "2025-06-01T10:00:00Z",
  },
  {
    id: "log-0002def",
    actor_id: "user-2",
    action: "delete",
    resource_type: "skill",
    resource_id: "skill-1",
    detail: null,
    ip_address: "10.0.0.1",
    created_at: "2025-06-02T14:30:00Z",
  },
  {
    id: "log-0003ghi",
    actor_id: null,
    action: "approve",
    resource_type: "workflow",
    resource_id: null,
    detail: '{"reason":"auto-approved"}',
    ip_address: null,
    created_at: "2025-06-03T09:15:00Z",
  },
];

function setupAuth(role = "super_admin") {
  vi.mocked(useAuth).mockReturnValue({
    user: {
      id: "current-admin-id",
      email: "admin@example.com",
      system_role: role,
      needs_setup: false,
    } as never,
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AuditLogsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupAuth();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 3,
      page: 1,
      page_size: 20,
    });
  });

  afterEach(() => {
    cleanup();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  test("renders the page with title and description", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("审计日志")).toBeInTheDocument();
      expect(
        screen.getByText("浏览和查询系统操作审计记录"),
      ).toBeInTheDocument();
    });
  });

  test("renders a back link to /workspace/admin", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      const link = screen.getByRole("link");
      expect(link).toHaveAttribute("href", "/workspace/admin");
    });
  });

  test("renders audit log items after loading", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0001...")).toBeInTheDocument();
      expect(screen.getByText("log-0002...")).toBeInTheDocument();
      expect(screen.getByText("log-0003...")).toBeInTheDocument();
    });
  });

  // ── Access control ─────────────────────────────────────────────────

  test("redirects non-super_admin users to /workspace", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "current-user",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      } as never,
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<AuditLogsPage />);
    expect(mockReplace).toHaveBeenCalledWith("/workspace");
  });

  test("does not render page content for non-admin users", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "current-user",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      } as never,
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<AuditLogsPage />);
    expect(screen.queryByTestId("audit-logs-page")).not.toBeInTheDocument();
  });

  // ── Loading state ──────────────────────────────────────────────────

  test("shows loading indicator while fetching data", () => {
    // eslint-disable-next-line @typescript-eslint/no-empty-function -- pending promise for loading state test
    mockListAuditLogs.mockReturnValue(new Promise(() => {}));
    render(<AuditLogsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
    expect(screen.queryByText("log-0001...")).not.toBeInTheDocument();
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when API call fails", async () => {
    mockListAuditLogs.mockRejectedValue(new Error("Server error"));
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  test("shows stringified error for non-Error throws", async () => {
    mockListAuditLogs.mockRejectedValue("unknown failure");
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("unknown failure")).toBeInTheDocument();
    });
  });

  // ── Data display ───────────────────────────────────────────────────

  test("renders audit log cards after loading", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0001...")).toBeInTheDocument();
      expect(screen.getByText("log-0002...")).toBeInTheDocument();
      expect(screen.getByText("log-0003...")).toBeInTheDocument();
    });
  });

  test("displays action badges with correct labels", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("创建")).toBeInTheDocument();
      expect(screen.getByText("删除")).toBeInTheDocument();
      expect(screen.getByText("批准")).toBeInTheDocument();
    });
  });

  test("displays resource type badges", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      const toolBadges = screen.getAllByText("工具");
      expect(toolBadges.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Skill")).toBeInTheDocument();
      expect(screen.getByText("工作流")).toBeInTheDocument();
    });
  });

  test("displays actor_id or fallback to system", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("user-1", { exact: false })).toBeInTheDocument();
      expect(screen.getByText("user-2", { exact: false })).toBeInTheDocument();
      const systemTexts = screen.getAllByText("系统");
      expect(systemTexts.length).toBeGreaterThanOrEqual(1);
    });
  });

  test("displays resource_id when present", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("tool-1", { exact: false })).toBeInTheDocument();
      expect(screen.getByText("skill-1", { exact: false })).toBeInTheDocument();
    });
  });

  test("displays IP address when present", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(
        screen.getByText("192.168.1.1", { exact: false }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("10.0.0.1", { exact: false }),
      ).toBeInTheDocument();
    });
  });

  test("displays total count", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });
  });

  // ── Empty state ────────────────────────────────────────────────────

  test("shows empty state when no logs exist", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("没有找到审计日志")).toBeInTheDocument();
    });
  });

  // ── Filters ────────────────────────────────────────────────────────

  test("renders filter inputs", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("用户 ID")).toBeInTheDocument();
      expect(screen.getByText("操作类型")).toBeInTheDocument();
      expect(screen.getByText("资源类型")).toBeInTheDocument();
    });
  });

  test("renders reset button", async () => {
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("重置")).toBeInTheDocument();
    });
  });

  test("passes actor_id filter to API when typing", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: [mockLogs[0]],
      total: 1,
      page: 1,
      page_size: 20,
    });

    const input = screen.getByPlaceholderText("用户 ID");
    await user.type(input, "user-1");

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ actor_id: "user-1" }),
      );
    });
  });

  test("passes action filter to API when selecting action type", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: [mockLogs[0]],
      total: 1,
      page: 1,
      page_size: 20,
    });

    const actionCombobox = screen.getAllByRole("combobox")[0]!;
    await user.click(actionCombobox);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    const createOption = screen.getByRole("option", { name: "创建" });
    await user.click(createOption);

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ action: "create" }),
      );
    });
  });

  test("passes resource_type filter to API when selecting", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 3,
      page: 1,
      page_size: 20,
    });

    const resourceCombobox = screen.getAllByRole("combobox")[1]!;
    await user.click(resourceCombobox);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    const toolOption = screen.getByRole("option", { name: "工具" });
    await user.click(toolOption);

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ resource_type: "tool" }),
      );
    });
  });

  test("reset button clears all filters", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("用户 ID");
    await user.type(input, "user-1");

    await user.click(screen.getByText("重置"));

    expect(input).toHaveValue("");
  });

  // ── Pagination ─────────────────────────────────────────────────────

  test("does not show pagination when total fits one page", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 3,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });
    expect(screen.queryByText("上一页")).not.toBeInTheDocument();
    expect(screen.queryByText("下一页")).not.toBeInTheDocument();
  });

  test("shows pagination when total exceeds page size", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 40,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("上一页")).toBeInTheDocument();
      expect(screen.getByText("下一页")).toBeInTheDocument();
      expect(screen.getByText("1 / 2")).toBeInTheDocument();
    });
  });

  test("next page button triggers re-fetch with page=2", async () => {
    const user = userEvent.setup();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 40,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("1 / 2")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: [mockLogs[1]],
      total: 40,
      page: 2,
      page_size: 20,
    });

    await user.click(screen.getByText("下一页"));

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2 }),
      );
      expect(screen.getByText("2 / 2")).toBeInTheDocument();
    });
  });

  test("prev page button is disabled on first page", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 40,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("上一页")).toBeDisabled();
    });
  });

  test("next page button is disabled on last page", async () => {
    const user = userEvent.setup();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 25,
      page: 1,
      page_size: 20,
    });
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("1 / 2")).toBeInTheDocument();
    });

    // Navigate to page 2
    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: [mockLogs[0]],
      total: 25,
      page: 2,
      page_size: 20,
    });
    await user.click(screen.getByText("下一页"));

    await waitFor(() => {
      expect(screen.getByText("2 / 2")).toBeInTheDocument();
      expect(screen.getByText("下一页")).toBeDisabled();
    });
  });

  // ── Detail dialog ──────────────────────────────────────────────────

  test("opens detail dialog when clicking a log card", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0001...")).toBeInTheDocument();
    });

    const card = screen
      .getByText("log-0001...")
      .closest("[class*='cursor-pointer']")!;
    await user.click(card);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(within(dialog).getByText("审计日志详情")).toBeInTheDocument();
      expect(within(dialog).getByText(/log-0001abc/)).toBeInTheDocument();
    });
  });

  test("detail dialog shows log fields", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0001...")).toBeInTheDocument();
    });

    const card = screen
      .getByText("log-0001...")
      .closest("[class*='cursor-pointer']")!;
    await user.click(card);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(within(dialog).getByText("审计日志详情")).toBeInTheDocument();
      expect(
        within(dialog).getAllByText("操作类型").length,
      ).toBeGreaterThanOrEqual(1);
      expect(within(dialog).getByText("操作时间")).toBeInTheDocument();
      expect(within(dialog).getByText("IP 地址")).toBeInTheDocument();
      expect(within(dialog).getByText("资源类型")).toBeInTheDocument();
      expect(within(dialog).getByText("资源 ID")).toBeInTheDocument();
      expect(within(dialog).getByText("详细内容")).toBeInTheDocument();
    });
  });

  test("detail dialog shows formatted JSON detail", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0001...")).toBeInTheDocument();
    });

    const card = screen
      .getByText("log-0001...")
      .closest("[class*='cursor-pointer']")!;
    await user.click(card);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(within(dialog).getByText(/name/)).toBeInTheDocument();
      expect(within(dialog).getByText(/test tool/)).toBeInTheDocument();
    });
  });

  test("detail dialog shows fallback text when detail is null", async () => {
    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("log-0002...")).toBeInTheDocument();
    });

    const card = screen
      .getByText("log-0002...")
      .closest("[class*='cursor-pointer']")!;
    await user.click(card);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(within(dialog).getByText("审计日志详情")).toBeInTheDocument();
      expect(within(dialog).getByText("无")).toBeInTheDocument();
    });
  });

  test("detail dialog shows raw detail when JSON parse fails", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: [
        {
          ...mockLogs[0],
          id: "log-raw-001",
          detail: "not valid json",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    const user = userEvent.setup();
    render(<AuditLogsPage />);
    await waitFor(() => {
      // "log-raw-001".slice(0, 8) = "log-raw-"
      expect(screen.getByText("log-raw-...")).toBeInTheDocument();
    });

    const card = screen
      .getByText("log-raw-...")
      .closest("[class*='cursor-pointer']")!;
    await user.click(card);

    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(within(dialog).getByText("not valid json")).toBeInTheDocument();
    });
  });

  // ── API call on mount ──────────────────────────────────────────────

  test("calls listAuditLogs on mount with default params", () => {
    render(<AuditLogsPage />);
    expect(mockListAuditLogs).toHaveBeenCalledTimes(1);
    expect(mockListAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 }),
    );
  });

  test("does not call listAuditLogs for non-admin users", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "current-user",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      } as never,
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<AuditLogsPage />);
    expect(mockListAuditLogs).not.toHaveBeenCalled();
  });

  // ── Action badge variants ──────────────────────────────────────────

  test("renders all known action labels correctly", async () => {
    const allActions = [
      { action: "create", label: "创建" },
      { action: "update", label: "更新" },
      { action: "delete", label: "删除" },
      { action: "review", label: "审批" },
      { action: "approve", label: "批准" },
      { action: "reject", label: "驳回" },
      { action: "withdraw", label: "撤回" },
      { action: "grant", label: "授权" },
      { action: "revoke", label: "撤销" },
      { action: "apply", label: "申请" },
      { action: "withdrawal", label: "撤回" },
    ];

    mockListAuditLogs.mockResolvedValue({
      items: allActions.map((a, i) => ({
        ...mockLogs[0],
        id: `log-${String(i).padStart(4, "0")}`,
        action: a.action,
      })),
      total: allActions.length,
      page: 1,
      page_size: 20,
    });

    render(<AuditLogsPage />);
    await waitFor(() => {
      for (const a of allActions) {
        expect(screen.getAllByText(a.label).length).toBeGreaterThanOrEqual(1);
      }
    });
  });

  test("renders unknown action as raw string", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: [{ ...mockLogs[0], id: "log-unkn001", action: "custom_action" }],
      total: 1,
      page: 1,
      page_size: 20,
    });

    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("custom_action")).toBeInTheDocument();
    });
  });

  // ── Resource type fallback ─────────────────────────────────────────

  test("renders unknown resource type as raw string", async () => {
    mockListAuditLogs.mockResolvedValue({
      items: [
        { ...mockLogs[0], id: "log-rt0001", resource_type: "unknown_type" },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("unknown_type")).toBeInTheDocument();
    });
  });

  // ── Date filter inputs ─────────────────────────────────────────────

  test("renders date filter inputs", async () => {
    const { container } = render(<AuditLogsPage />);
    await waitFor(() => {
      const datetimeInputs = container.querySelectorAll(
        'input[type="datetime-local"]',
      );
      expect(datetimeInputs).toHaveLength(2);
    });
  });

  test("passes start_date filter to API", async () => {
    const user = userEvent.setup();
    const { container } = render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 3,
      page: 1,
      page_size: 20,
    });

    const startDateInput = container.querySelector(
      'input[type="datetime-local"]',
    )!;
    await user.type(startDateInput, "2025-06-01T00:00");

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ start_date: "2025-06-01T00:00" }),
      );
    });
  });

  test("passes end_date filter to API", async () => {
    const user = userEvent.setup();
    const { container } = render(<AuditLogsPage />);
    await waitFor(() => {
      expect(screen.getByText("共 3 条")).toBeInTheDocument();
    });

    mockListAuditLogs.mockClear();
    mockListAuditLogs.mockResolvedValue({
      items: mockLogs,
      total: 3,
      page: 1,
      page_size: 20,
    });

    const datetimeInputs = container.querySelectorAll(
      'input[type="datetime-local"]',
    );
    const endDateInput = datetimeInputs[1] as HTMLInputElement;
    await user.type(endDateInput, "2025-06-30T23:59");

    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ end_date: "2025-06-30T23:59" }),
      );
    });
  });
});
