import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockRouterReplace = vi.fn();
const mockUseAdminStats = vi.fn();

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockRouterReplace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/workspace/admin",
}));

vi.mock("@/core/admin/hooks", () => ({
  useAdminStats: (...args: unknown[]) => mockUseAdminStats(...args),
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

import AdminDashboardPage from "@/app/workspace/admin/page";
import { useAuth } from "@/core/auth/AuthProvider";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockStats = {
  total_users: 42,
  total_departments: 8,
  total_agents: 15,
  total_tools: 7,
  total_skills: 23,
  total_workflows: 4,
  total_resources: 38,
  audit_logs: 12,
  pending_applications: 3,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAdminStats.mockReturnValue({
      data: mockStats,
      isLoading: false,
      error: null,
      isFetched: true,
    });
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "test-admin-id",
        email: "admin@example.com",
        system_role: "super_admin",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  test("renders the dashboard container with testid", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId("admin-dashboard")).toBeInTheDocument();
    });
  });

  test("renders the page header with title and description", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("管理后台")).toBeInTheDocument();
      expect(screen.getByText("管理用户、部门和系统工具")).toBeInTheDocument();
    });
  });

  // ── Loading state ──────────────────────────────────────────────────

  test("shows loading indicator while fetching stats", () => {
    mockUseAdminStats.mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
    });
    render(<AdminDashboardPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
  });

  // ── Success state ──────────────────────────────────────────────────

  test("renders six stat cards after loading", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const cards = screen.getAllByTestId("admin-stat-card");
      expect(cards).toHaveLength(6);
    });
  });

  test("displays correct stat values", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument(); // total_users
      expect(screen.getByText("8")).toBeInTheDocument(); // total_departments
      expect(screen.getByText("38")).toBeInTheDocument(); // total_resources
    });
  });

  test("displays correct labels for each stat card", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("用户总数")).toBeInTheDocument();
      expect(screen.getByText("部门总数")).toBeInTheDocument();
      expect(screen.getByText("工具总数")).toBeInTheDocument();
    });
  });

  test("each stat card links to the correct page", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const links = screen.getAllByRole("link");
      const hrefs = links.map((link) => link.getAttribute("href"));
      expect(hrefs).toContain("/workspace/admin/users");
      expect(hrefs).toContain("/workspace/admin/departments");
      expect(hrefs).toContain("/workspace/admin/tools");
      expect(hrefs).toContain("/workspace/admin/resources");
    });
  });

  test("each stat card shows 'click to view details' text", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const details = screen.getAllByText("点击查看详情");
      expect(details).toHaveLength(6);
    });
  });

  // ── Default values when stats are null ─────────────────────────────

  test("shows 0 for stat values when API returns zero counts", async () => {
    mockUseAdminStats.mockReturnValue({
      data: {
        total_users: 0,
        total_departments: 0,
        total_agents: 0,
        total_skills: 0,
      } as unknown,
      isLoading: false,
      error: null,
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const zeros = screen.getAllByText("0");
      expect(zeros.length).toBeGreaterThanOrEqual(4);
    });
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when API call fails", async () => {
    mockUseAdminStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Network failure"),
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });

  test("shows stringified error when non-Error is thrown", async () => {
    mockUseAdminStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: "raw string error",
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("raw string error")).toBeInTheDocument();
    });
  });

  test("does not render stat cards in error state", async () => {
    mockUseAdminStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("fail"),
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.queryAllByTestId("admin-stat-card")).toHaveLength(0);
    });
  });

  // ── API call ───────────────────────────────────────────────────────

  test("calls useAdminStats with enabled=true for super_admin", () => {
    render(<AdminDashboardPage />);
    expect(mockUseAdminStats).toHaveBeenCalledTimes(1);
    expect(mockUseAdminStats).toHaveBeenCalledWith(true);
  });

  test("redirects non-admin users without fetching stats", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "regular-user",
        email: "user@example.com",
        system_role: "user",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    const { container } = render(<AdminDashboardPage />);

    expect(mockRouterReplace).toHaveBeenCalledWith("/workspace");
    expect(mockUseAdminStats).toHaveBeenCalledWith(false);
    expect(container).toBeEmptyDOMElement();
  });

  // ── Transition from loading to error ───────────────────────────────

  test("hides loading indicator after error", async () => {
    mockUseAdminStats.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("timeout"),
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
      expect(screen.getByText("timeout")).toBeInTheDocument();
    });
  });
});
