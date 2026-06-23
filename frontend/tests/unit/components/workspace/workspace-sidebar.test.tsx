import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

// Sidebar context
let mockSidebarOpen = true;
vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ open: mockSidebarOpen }),
  Sidebar: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <div data-testid="sidebar" {...props}>
      {children}
    </div>
  ),
  SidebarHeader: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-header">{children}</div>
  ),
  SidebarContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-content">{children}</div>
  ),
  SidebarFooter: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-footer">{children}</div>
  ),
  SidebarRail: () => <div data-testid="sidebar-rail" />,
}));

// WorkspaceHeader
vi.mock("@/components/workspace/workspace-header", () => ({
  WorkspaceHeader: () => <div data-testid="workspace-header">Header</div>,
}));

// WorkspaceNavChatList
vi.mock("@/components/workspace/workspace-nav-chat-list", () => ({
  WorkspaceNavChatList: () => (
    <div data-testid="workspace-nav-chat-list">NavChatList</div>
  ),
}));

// RecentChatList
vi.mock("@/components/workspace/recent-chat-list", () => ({
  RecentChatList: () => (
    <div data-testid="recent-chat-list">RecentChatList</div>
  ),
}));

// WorkspaceNavMenu
vi.mock("@/components/workspace/workspace-nav-menu", () => ({
  WorkspaceNavMenu: () => <div data-testid="workspace-nav-menu">NavMenu</div>,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkspaceSidebar: typeof import("@/components/workspace/workspace-sidebar").WorkspaceSidebar;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSidebarOpen = true;
  const mod = await import("@/components/workspace/workspace-sidebar");
  WorkspaceSidebar = mod.WorkspaceSidebar;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceSidebar", () => {
  // ── Structure ────────────────────────────────────────────────────────────

  test("renders the Sidebar component", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });

  test("renders WorkspaceHeader in the sidebar header", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("workspace-header")).toBeInTheDocument();
    // Header should be inside the sidebar-header region
    const header = screen.getByTestId("sidebar-header");
    expect(header).toContainElement(screen.getByTestId("workspace-header"));
  });

  test("renders WorkspaceNavChatList in the sidebar content", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("workspace-nav-chat-list")).toBeInTheDocument();
    const content = screen.getByTestId("sidebar-content");
    expect(content).toContainElement(
      screen.getByTestId("workspace-nav-chat-list"),
    );
  });

  test("renders WorkspaceNavMenu in the sidebar footer", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("workspace-nav-menu")).toBeInTheDocument();
    const footer = screen.getByTestId("sidebar-footer");
    expect(footer).toContainElement(screen.getByTestId("workspace-nav-menu"));
  });

  test("renders the SidebarRail", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("sidebar-rail")).toBeInTheDocument();
  });

  // ── RecentChatList visibility based on sidebar open state ────────────────

  test("renders RecentChatList when sidebar is open", () => {
    mockSidebarOpen = true;
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("recent-chat-list")).toBeInTheDocument();
  });

  test("does not render RecentChatList when sidebar is closed", () => {
    mockSidebarOpen = false;
    render(<WorkspaceSidebar />);
    expect(screen.queryByTestId("recent-chat-list")).not.toBeInTheDocument();
  });

  // ── Props passthrough ────────────────────────────────────────────────────

  test("passes additional props to the Sidebar component", () => {
    render(<WorkspaceSidebar className="custom-class" />);
    const sidebar = screen.getByTestId("sidebar");
    expect(sidebar).toHaveAttribute(
      "class",
      expect.stringContaining("custom-class"),
    );
  });

  test("sets data-testid on sidebar", () => {
    render(<WorkspaceSidebar />);
    expect(screen.getByTestId("sidebar")).toHaveAttribute(
      "data-testid",
      "sidebar",
    );
  });

  // ── Layout order ─────────────────────────────────────────────────────────

  test("renders children in correct order: header, content, footer, rail", () => {
    render(<WorkspaceSidebar />);
    const sidebar = screen.getByTestId("sidebar");
    const children = Array.from(sidebar.children);

    // Should have: header, content, footer, rail
    expect(children).toHaveLength(4);
    expect(children[0]).toHaveAttribute("data-testid", "sidebar-header");
    expect(children[1]).toHaveAttribute("data-testid", "sidebar-content");
    expect(children[2]).toHaveAttribute("data-testid", "sidebar-footer");
    expect(children[3]).toHaveAttribute("data-testid", "sidebar-rail");
  });
});
