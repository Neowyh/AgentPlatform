import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockGetAdminStats = vi.fn();

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/workspace/admin",
}));

vi.mock("@/core/admin/api", () => ({
  getAdminStats: (...args: unknown[]) => mockGetAdminStats(...args),
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
  total_skills: 23,
  total_resources: 38,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAdminStats.mockResolvedValue(mockStats);
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
    // Make the promise never resolve during this test
    mockGetAdminStats.mockReturnValue(new Promise(() => {}));
    render(<AdminDashboardPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
  });

  // ── Success state ──────────────────────────────────────────────────

  test("renders seven stat cards after loading", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const cards = screen.getAllByTestId("admin-stat-card");
      expect(cards).toHaveLength(7);
    });
  });

  test("displays correct stat values", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument(); // total_users
      expect(screen.getByText("8")).toBeInTheDocument(); // total_departments
      expect(screen.getByText("15")).toBeInTheDocument(); // total_agents
      expect(screen.getByText("38")).toBeInTheDocument(); // total_resources
    });
  });

  test("displays correct labels for each stat card", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("用户总数")).toBeInTheDocument();
      expect(screen.getByText("部门总数")).toBeInTheDocument();
      expect(screen.getByText("智能体总数")).toBeInTheDocument();
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
      expect(hrefs).toContain("/workspace/agents");
      expect(hrefs).toContain("/workspace/admin/tools");
    });
  });

  test("each stat card shows 'click to view details' text", async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const details = screen.getAllByText("点击查看详情");
      expect(details).toHaveLength(7);
    });
  });

  // ── Default values when stats are null ─────────────────────────────

  test("shows 0 for stat values when API returns zero counts", async () => {
    mockGetAdminStats.mockResolvedValue({
      total_users: 0,
      total_departments: 0,
      total_agents: 0,
      total_skills: 0,
    });
    render(<AdminDashboardPage />);
    await waitFor(() => {
      const zeros = screen.getAllByText("0");
      expect(zeros.length).toBeGreaterThanOrEqual(4);
    });
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when API call fails", async () => {
    mockGetAdminStats.mockRejectedValue(new Error("Network failure"));
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });

  test("shows stringified error when non-Error is thrown", async () => {
    mockGetAdminStats.mockRejectedValue("raw string error");
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("raw string error")).toBeInTheDocument();
    });
  });

  test("does not render stat cards in error state", async () => {
    mockGetAdminStats.mockRejectedValue(new Error("fail"));
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.queryAllByTestId("admin-stat-card")).toHaveLength(0);
    });
  });

  // ── API call ───────────────────────────────────────────────────────

  test("calls getAdminStats once on mount", () => {
    render(<AdminDashboardPage />);
    expect(mockGetAdminStats).toHaveBeenCalledTimes(1);
    expect(mockGetAdminStats).toHaveBeenCalledWith();
  });

  // ── Transition from loading to error ───────────────────────────────

  test("hides loading indicator after error", async () => {
    mockGetAdminStats.mockRejectedValue(new Error("timeout"));
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
      expect(screen.getByText("timeout")).toBeInTheDocument();
    });
  });
});
