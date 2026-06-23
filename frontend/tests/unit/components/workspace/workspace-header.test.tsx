import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

// next/link
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

// next/navigation
let mockPathname = "/workspace/chats/new";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

// Sidebar context
let mockSidebarState: "expanded" | "collapsed" = "expanded";
vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ state: mockSidebarState }),
  SidebarMenu: ({ children, ...props }: { children: React.ReactNode }) => (
    <div {...props}>{children}</div>
  ),
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SidebarMenuButton: ({
    children,
    isActive,
    asChild,
    ...props
  }: {
    children: React.ReactNode;
    isActive?: boolean;
    asChild?: boolean;
    [key: string]: unknown;
  }) => (
    <button data-active={isActive} {...props}>
      {children}
    </button>
  ),
  SidebarTrigger: ({ className }: { className?: string }) => (
    <button data-testid="sidebar-trigger" className={className}>
      Toggle
    </button>
  ),
}));

// i18n
const mockT = {
  sidebar: {
    newChat: "New Chat",
  },
};
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: mockT,
    changeLocale: vi.fn(),
  }),
}));

// env
let mockStaticWebsiteOnly = "false";
vi.mock("@/env", () => ({
  get env() {
    return {
      NEXT_PUBLIC_STATIC_WEBSITE_ONLY: mockStaticWebsiteOnly,
    };
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkspaceHeader: typeof import("@/components/workspace/workspace-header").WorkspaceHeader;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSidebarState = "expanded";
  mockPathname = "/workspace/chats/new";
  mockStaticWebsiteOnly = "false";
  const mod = await import("@/components/workspace/workspace-header");
  WorkspaceHeader = mod.WorkspaceHeader;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceHeader", () => {
  // ── Expanded state ───────────────────────────────────────────────────────

  test("renders the iDeer brand text when expanded", () => {
    mockSidebarState = "expanded";
    render(<WorkspaceHeader />);
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });

  test("renders SidebarTrigger when expanded", () => {
    mockSidebarState = "expanded";
    render(<WorkspaceHeader />);
    expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
  });

  test("renders iDeer as a div (not link) in non-static mode", () => {
    mockSidebarState = "expanded";
    mockStaticWebsiteOnly = "false";
    render(<WorkspaceHeader />);
    const brand = screen.getByText("iDeer");
    expect(brand.tagName).toBe("DIV");
  });

  test("renders iDeer as a link in static website mode", () => {
    mockSidebarState = "expanded";
    mockStaticWebsiteOnly = "true";
    render(<WorkspaceHeader />);
    const brand = screen.getByText("iDeer");
    expect(brand.tagName).toBe("A");
    expect(brand).toHaveAttribute("href", "/");
  });

  // ── Collapsed state ──────────────────────────────────────────────────────

  test("renders 'DF' text when collapsed", () => {
    mockSidebarState = "collapsed";
    render(<WorkspaceHeader />);
    expect(screen.getByText("DF")).toBeInTheDocument();
  });

  test("does not render 'iDeer' text when collapsed", () => {
    mockSidebarState = "collapsed";
    render(<WorkspaceHeader />);
    expect(screen.queryByText("iDeer")).not.toBeInTheDocument();
  });

  test("renders a hidden SidebarTrigger when collapsed", () => {
    mockSidebarState = "collapsed";
    render(<WorkspaceHeader />);
    const trigger = screen.getByTestId("sidebar-trigger");
    expect(trigger).toBeInTheDocument();
    // The trigger has "hidden" class initially, shown on group hover
    expect(trigger.className).toContain("hidden");
  });

  // ── New Chat button ──────────────────────────────────────────────────────

  test("renders the New Chat button", () => {
    render(<WorkspaceHeader />);
    expect(screen.getByText("New Chat")).toBeInTheDocument();
  });

  test("New Chat button links to /workspace/chats/new", () => {
    render(<WorkspaceHeader />);
    const link = screen.getByText("New Chat").closest("a");
    expect(link).toHaveAttribute("href", "/workspace/chats/new");
  });

  test("New Chat button is marked active when pathname matches", () => {
    mockPathname = "/workspace/chats/new";
    render(<WorkspaceHeader />);
    const button = screen.getByTestId("new-chat-button");
    expect(button).toHaveAttribute("data-active", "true");
  });

  test("New Chat button is not active when on a different path", () => {
    mockPathname = "/workspace/chats/abc";
    render(<WorkspaceHeader />);
    const button = screen.getByTestId("new-chat-button");
    expect(button).toHaveAttribute("data-active", "false");
  });

  // ── Custom className ─────────────────────────────────────────────────────

  test("applies custom className to the wrapper", () => {
    render(<WorkspaceHeader className="my-custom-class" />);
    const wrapper = document.querySelector(".my-custom-class");
    expect(wrapper).toBeInTheDocument();
  });

  test("applies default classes alongside custom className", () => {
    render(<WorkspaceHeader className="extra" />);
    const wrapper = document.querySelector(".extra");
    expect(wrapper).toBeInTheDocument();
    // Should also have the default flex classes
    expect(wrapper?.className).toContain("flex");
    expect(wrapper?.className).toContain("h-12");
  });
});
