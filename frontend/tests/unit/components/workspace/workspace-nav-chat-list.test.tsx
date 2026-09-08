import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as renderBase, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "user@test.com", system_role: "user" },
  }),
}));

const render = (ui: React.ReactElement, options?: any) =>
  renderBase(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {ui}
    </QueryClientProvider>,
    options,
  );

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

let mockAgentsEnabled = true;
vi.mock("@/core/agents", () => ({
  useAgentsApiEnabled: () => ({ enabled: mockAgentsEnabled }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      sidebar: {
        chats: "Chats",
        capabilities: "Experts · Skills · Connectors",
        library: "Library",
        agents: "Agents",
        scheduledTasks: "Scheduled tasks",
        workflows: "Workflows",
        agentsDisabledTooltip: "Agents are not enabled",
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
    ...rest
  }: {
    children: React.ReactNode;
    isActive?: boolean;
    asChild?: boolean;
    [key: string]: unknown;
  }) => (
    <div data-testid="sidebar-menu-button" data-is-active={isActive} {...rest}>
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
  test("renders six navigation items including the restored iDeer entries", () => {
    render(<WorkspaceNavChatList />);
    const items = screen.getAllByTestId("sidebar-menu-item");
    expect(items).toHaveLength(6);
    expect(screen.getByText("Chats")).toBeInTheDocument();
    expect(screen.getByText("Experts · Skills · Connectors")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Scheduled tasks")).toBeInTheDocument();
    expect(screen.getByText("Workflows")).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
  });

  test("marks Chats as active when on chats path", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[0]!.getAttribute("data-is-active")).toBe("true");
    expect(buttons[1]!.getAttribute("data-is-active")).toBe("false");
  });

  test("marks Capabilities active across its routes", () => {
    for (const path of [
      "/workspace/capabilities/experts",
      "/workspace/resources",
    ]) {
      mockPathname = path;
      render(<WorkspaceNavChatList />);
      const buttons = screen.getAllByTestId("sidebar-menu-button");
      expect(buttons[1]!.getAttribute("data-is-active")).toBe("true");
      cleanup();
    }
  });

  test("marks Agents as active on the agents path", () => {
    mockPathname = "/workspace/agents";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[2]!.getAttribute("data-is-active")).toBe("true");
  });

  test("marks Scheduled tasks as active on its path", () => {
    mockPathname = "/workspace/scheduled-tasks";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    expect(buttons[3]!.getAttribute("data-is-active")).toBe("true");
  });

  test("renders Agents as a plain link when the agents API is enabled", () => {
    mockAgentsEnabled = true;
    render(<WorkspaceNavChatList />);
    const link = screen.getByText("Agents").closest("a");
    expect(link).toHaveAttribute("href", "/workspace/agents");
  });

  test("renders a disabled, tooltip-explained Agents entry when the API is off", () => {
    mockAgentsEnabled = false;
    render(<WorkspaceNavChatList />);
    const button = screen
      .getByText("Agents")
      .closest("div[data-testid='sidebar-menu-button']");
    expect(button).toBeInTheDocument();
    expect(button!.getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByText("Agents are not enabled")).toBeInTheDocument();
  });

  test("marks Chats as inactive on other paths", () => {
    mockPathname = "/workspace/automations";
    render(<WorkspaceNavChatList />);
    const buttons = screen.getAllByTestId("sidebar-menu-button");
    // Chats and Scheduled tasks stay inactive; the disabled Agents entry has
    // no active state at all.
    expect(buttons[0]!.getAttribute("data-is-active")).toBe("false");
    expect(buttons[3]!.getAttribute("data-is-active")).toBe("false");
  });
});
