import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockPathname = "/workspace/chats";

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

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      sidebar: {
        chats: "Chats",
        capabilities: "Experts · Skills · Connectors",
        library: "Library",
        workflows: "Workflows",
      },
    },
  }),
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarGroup: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="sidebar-group" className={className}>
      {children}
    </div>
  ),
  SidebarMenu: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-menu">{children}</div>
  ),
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="sidebar-menu-item">{children}</div>
  ),
  SidebarMenuButton: ({
    children,
    isActive,
    asChild,
  }: {
    children: React.ReactNode;
    isActive?: boolean;
    asChild?: boolean;
  }) => (
    <div data-testid="sidebar-menu-button" data-is-active={isActive}>
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkspaceNavChatList: typeof import("@/components/workspace/workspace-nav-chat-list").WorkspaceNavChatList;

beforeEach(async () => {
  vi.clearAllMocks();
  mockPathname = "/workspace/chats";
  const mod = await import("@/components/workspace/workspace-nav-chat-list");
  WorkspaceNavChatList = mod.WorkspaceNavChatList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceNavChatList", () => {
  test("renders four navigation items", () => {
    render(<WorkspaceNavChatList />);
    const items = screen.getAllByTestId("sidebar-menu-item");
    expect(items).toHaveLength(4);
  });

  test("renders history, capabilities, workflows, and library links", () => {
    render(<WorkspaceNavChatList />);
    expect(screen.getByText("Chats")).toBeInTheDocument();
    expect(
      screen.getByText("Experts · Skills · Connectors"),
    ).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Workflows")).toBeInTheDocument();
  });

  test("marks Chats as active when on chats path", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[0]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks capabilities as active on a capability path", () => {
    mockPathname = "/workspace/capabilities/skills";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[1]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks capabilities as active for legacy resource paths", () => {
    mockPathname = "/workspace/resources";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[1]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks Library as active when on library path", () => {
    mockPathname = "/workspace/library";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[3]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks Workflows as active when on workflows path", () => {
    mockPathname = "/workspace/workflows";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[2]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks capabilities as active for legacy agent paths", () => {
    mockPathname = "/workspace/agents/some-agent";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[1]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks Library as active for sub-paths", () => {
    mockPathname = "/workspace/library/some-doc";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[3]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks Workflows as active for sub-paths", () => {
    mockPathname = "/workspace/workflows/some-workflow";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[2]!.getAttribute("data-is-active")).toBe("true");
  });

  test("none are active for unrelated paths", () => {
    mockPathname = "/workspace/admin";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[0]!.getAttribute("data-is-active")).toBe("false");
    expect(buttons[1]!.getAttribute("data-is-active")).toBe("false");
    expect(buttons[2]!.getAttribute("data-is-active")).toBe("false");
    expect(buttons[3]!.getAttribute("data-is-active")).toBe("false");
  });

  test("links have correct hrefs", () => {
    render(<WorkspaceNavChatList />);
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/workspace/chats");
    expect(links[1]).toHaveAttribute("href", "/workspace/capabilities/experts");
    expect(links[2]).toHaveAttribute("href", "/workspace/workflows");
    expect(links[3]).toHaveAttribute("href", "/workspace/library");
  });
});
