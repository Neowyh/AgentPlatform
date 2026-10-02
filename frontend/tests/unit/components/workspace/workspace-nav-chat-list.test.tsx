import { render as renderBase, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const render = (ui: React.ReactElement) => renderBase(ui);

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
        capabilities: "Agents · Skills · Connectors",
        library: "Library",
        scheduledTasks: "Scheduled tasks",
        workflows: "Workflows",
      },
      capabilities: {
        title: "Capability Center",
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

// ── Helpers ──────────────────────────────────────────────────────────────────

const renderedLabels = () =>
  screen
    .getAllByTestId("sidebar-menu-item")
    .map(
      (item) =>
        item.querySelector("[data-testid='sidebar-menu-button']")
          ?.textContent ?? "",
    );

const renderedHrefs = () =>
  screen
    .getAllByTestId("sidebar-menu-button")
    .map((button) => button.querySelector("a")?.getAttribute("href"));

const buttonActiveStates = () =>
  screen
    .getAllByTestId("sidebar-menu-button")
    .map((button) => button.getAttribute("data-is-active"));

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceNavChatList", () => {
  test("renders the merged five-entry nav with a single capability-center entry", () => {
    render(<WorkspaceNavChatList />);
    // 能力中心唯一入口（含 experts tab）；上游重复的 capability 入口与本地
    // "专家 · 技能 · 连接器" 入口按 ADR-0007 方向去重，仅保留能力中心一项。
    expect(renderedLabels()).toEqual([
      "Chats",
      "Capability Center",
      "Workflows",
      "Library",
      "Scheduled tasks",
    ]);
  });

  test("does not render a second agent management entry next to the capability center", () => {
    render(<WorkspaceNavChatList />);
    // The capability-center link is the single agent management entry;
    // ADR-0007 vocabulary shows Agents in the label, and no duplicate
    // standalone Experts/Agents entry may appear next to it.
    expect(screen.queryByText("Experts")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Experts · Skills · Connectors"),
    ).not.toBeInTheDocument();
  });

  test("links each entry to its pre-merge destination and Scheduled tasks to its own page", () => {
    render(<WorkspaceNavChatList />);
    expect(renderedHrefs()).toEqual([
      "/workspace/chats",
      "/workspace/capabilities/agents",
      "/workspace/workflows",
      "/workspace/library",
      "/workspace/scheduled-tasks",
    ]);
  });

  test("marks Chats as active when on chats path", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceNavChatList />);
    const states = buttonActiveStates();
    expect(states[0]).toBe("true");
    expect(states[1]).toBe("false");
  });

  test("marks Capabilities active across its routes", () => {
    for (const path of [
      "/workspace/capabilities/agents",
      "/workspace/agents/test-agent",
      "/workspace/resources",
    ]) {
      mockPathname = path;
      render(<WorkspaceNavChatList />);
      expect(buttonActiveStates()[1]).toBe("true");
      cleanup();
    }
  });

  test("marks Workflows active on workflow and automation routes", () => {
    for (const path of ["/workspace/workflows", "/workspace/automations"]) {
      mockPathname = path;
      render(<WorkspaceNavChatList />);
      expect(buttonActiveStates()[2]).toBe("true");
      cleanup();
    }
  });

  test("marks Library as active on its path", () => {
    mockPathname = "/workspace/library";
    render(<WorkspaceNavChatList />);
    expect(buttonActiveStates()[3]).toBe("true");
  });

  test("marks Scheduled tasks as active on its path while original entries stay inactive", () => {
    mockPathname = "/workspace/scheduled-tasks";
    render(<WorkspaceNavChatList />);
    expect(buttonActiveStates()).toEqual([
      "false",
      "false",
      "false",
      "false",
      "true",
    ]);
  });
});
