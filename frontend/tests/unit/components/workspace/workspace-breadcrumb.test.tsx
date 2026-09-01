import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockPathname = "/workspace";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
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

const mockT = {
  breadcrumb: {
    workspace: "Workspace",
    chats: "Chats",
    workflows: "Workflows",
    edit: "Edit",
    runs: "Runs",
  },
  sidebar: {
    agents: "Agents",
    capabilities: "Capabilities",
  },
  resources: { experts: "Experts", skills: "Skills", connectors: "Connectors" },
  workspace: {
    adminPanel: "Admin",
    userManagement: "Users",
    departmentManagement: "Departments",
  },
  common: {
    edit: "Edit",
  },
  pages: {
    untitled: "Untitled",
  },
};

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: mockT }),
}));

vi.mock("@/core/agents", () => ({
  useAgent: () => ({ agent: { name: "中文专家" } }),
}));

// Mock breadcrumb components
vi.mock("@/components/ui/breadcrumb", () => ({
  Breadcrumb: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <nav data-testid="breadcrumb" className={className}>
      {children}
    </nav>
  ),
  BreadcrumbList: ({ children }: { children: React.ReactNode }) => (
    <ol data-testid="breadcrumb-list">{children}</ol>
  ),
  BreadcrumbItem: ({ children }: { children: React.ReactNode }) => (
    <li data-testid="breadcrumb-item">{children}</li>
  ),
  BreadcrumbLink: ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <span data-testid="breadcrumb-link">{children}</span>,
  BreadcrumbPage: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="breadcrumb-page">{children}</span>
  ),
  BreadcrumbSeparator: () => <span data-testid="breadcrumb-separator">/</span>,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkspaceBreadcrumb: typeof import("@/components/workspace/workspace-breadcrumb").WorkspaceBreadcrumb;

beforeEach(async () => {
  vi.clearAllMocks();
  mockPathname = "/workspace";
  const mod = await import("@/components/workspace/workspace-breadcrumb");
  WorkspaceBreadcrumb = mod.WorkspaceBreadcrumb;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceBreadcrumb", () => {
  test("returns null for root workspace path", () => {
    mockPathname = "/workspace";
    const { container } = render(<WorkspaceBreadcrumb />);
    expect(container.innerHTML).toBe("");
  });

  test("renders breadcrumb for chats path", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByTestId("breadcrumb")).toBeInTheDocument();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Chats")).toBeInTheDocument();
  });

  test("renders breadcrumb for agents path", () => {
    mockPathname = "/workspace/capabilities/experts";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Experts")).toBeInTheDocument();
  });

  test("renders agent detail breadcrumb", () => {
    mockPathname = "/workspace/capabilities/experts/my-agent";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Capabilities")).toBeInTheDocument();
    expect(screen.getByText("中文专家")).toBeInTheDocument();
  });

  test("renders skill name instead of the resource id", () => {
    mockPathname = "/workspace/capabilities/skills/skill-uuid";
    render(
      <WorkspaceBreadcrumb
        skill={{
          name: "文档整理",
          description: "",
          category: "public",
          license: "",
          enabled: true,
        }}
      />,
    );
    expect(screen.getByText("文档整理")).toBeInTheDocument();
    expect(screen.queryByText("skill-uuid")).not.toBeInTheDocument();
  });

  test("renders agent edit breadcrumb", () => {
    mockPathname = "/workspace/capabilities/experts/my-agent/edit";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Edit")).toBeInTheDocument();
  });

  test("renders agent chats breadcrumb", () => {
    mockPathname = "/workspace/capabilities/experts/my-agent/chats";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Chats")).toBeInTheDocument();
  });

  test("renders agent chats with thread breadcrumb", () => {
    mockPathname = "/workspace/capabilities/experts/my-agent/chats/thread-123";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  test("does not render Untitled for new chat", () => {
    mockPathname = "/workspace/capabilities/experts/my-agent/chats/new";
    render(<WorkspaceBreadcrumb />);
    expect(screen.queryByText("Untitled")).not.toBeInTheDocument();
  });

  test("renders workflows breadcrumb", () => {
    mockPathname = "/workspace/workflows";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Workflows")).toBeInTheDocument();
  });

  test("renders workflow detail breadcrumb", () => {
    mockPathname = "/workspace/workflows/my-workflow";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("my-workflow")).toBeInTheDocument();
  });

  test("renders workflow edit breadcrumb", () => {
    mockPathname = "/workspace/workflows/my-workflow/edit";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Edit")).toBeInTheDocument();
  });

  test("renders workflow runs breadcrumb", () => {
    mockPathname = "/workspace/workflows/my-workflow/runs";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Runs")).toBeInTheDocument();
  });

  test("renders admin breadcrumb", () => {
    mockPathname = "/workspace/admin";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  test("renders admin users breadcrumb", () => {
    mockPathname = "/workspace/admin/users";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Users")).toBeInTheDocument();
  });

  test("renders admin agents (departments) breadcrumb", () => {
    mockPathname = "/workspace/admin/agents";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Departments")).toBeInTheDocument();
  });

  test("renders chats with thread breadcrumb", () => {
    mockPathname = "/workspace/chats/thread-abc";
    render(<WorkspaceBreadcrumb />);
    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  test("does not render Untitled for new chat in chats", () => {
    mockPathname = "/workspace/chats/new";
    render(<WorkspaceBreadcrumb />);
    expect(screen.queryByText("Untitled")).not.toBeInTheDocument();
  });

  test("renders separators between items", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceBreadcrumb />);
    const separators = screen.getAllByTestId("breadcrumb-separator");
    expect(separators.length).toBeGreaterThan(0);
  });

  test("returns null for non-workspace paths", () => {
    mockPathname = "/other/path";
    const { container } = render(<WorkspaceBreadcrumb />);
    expect(container.innerHTML).toBe("");
  });
});
