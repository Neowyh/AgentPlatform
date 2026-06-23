import { render, screen, cleanup } from "@testing-library/react";
import type { ReadonlyRequestCookies } from "next/dist/server/web/spec-extension/adapters/request-cookies";
import { afterEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// WorkspaceContent -- mock the module-level dependencies
// ---------------------------------------------------------------------------

vi.mock("next/headers", () => ({
  cookies: vi.fn().mockResolvedValue({
    get: vi.fn().mockReturnValue(undefined),
  }),
}));

vi.mock("sonner", () => ({
  Toaster: (props: Record<string, unknown>) => (
    <div data-testid="toaster" data-position={props.position} />
  ),
}));

vi.mock("@/components/query-client-provider", () => ({
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="query-client-provider">{children}</div>
  ),
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({
    children,
    defaultOpen,
    className,
  }: {
    children: React.ReactNode;
    defaultOpen?: boolean;
    className?: string;
  }) => (
    <div
      data-testid="sidebar-provider"
      data-default-open={String(defaultOpen)}
      className={className}
    >
      {children}
    </div>
  ),
  SidebarInset: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="sidebar-inset" className={className}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/workspace/command-palette", () => ({
  CommandPalette: () => <div data-testid="command-palette" />,
}));

vi.mock("@/components/workspace/workspace-sidebar", () => ({
  WorkspaceSidebar: () => <div data-testid="workspace-sidebar" />,
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import { WorkspaceContent } from "@/app/workspace/workspace-content";

describe("WorkspaceContent", () => {
  afterEach(() => {
    cleanup();
  });

  // ── Component structure ────────────────────────────────────────────

  test("renders QueryClientProvider", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    expect(screen.getByTestId("query-client-provider")).toBeInTheDocument();
  });

  test("renders SidebarProvider", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    expect(screen.getByTestId("sidebar-provider")).toBeInTheDocument();
  });

  test("renders WorkspaceSidebar", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    expect(screen.getByTestId("workspace-sidebar")).toBeInTheDocument();
  });

  test("renders SidebarInset wrapping children", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    expect(screen.getByTestId("sidebar-inset")).toBeInTheDocument();
    expect(screen.getByText("child")).toBeInTheDocument();
  });

  test("renders CommandPalette", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    expect(screen.getByTestId("command-palette")).toBeInTheDocument();
  });

  test("renders Toaster with position top-center", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const toaster = screen.getByTestId("toaster");
    expect(toaster).toHaveAttribute("data-position", "top-center");
  });

  // ── parseSidebarOpenCookie branches ────────────────────────────────

  test("defaultOpen is 'undefined' string when no sidebar_state cookie", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider).toHaveAttribute("data-default-open", "undefined");
  });

  test("defaultOpen is true when sidebar_state cookie is 'true'", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi
        .fn()
        .mockImplementation((key: string) =>
          key === "sidebar_state" ? { value: "true" } : undefined,
        ),
    } as unknown as ReadonlyRequestCookies);

    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider).toHaveAttribute("data-default-open", "true");
  });

  test("defaultOpen is false when sidebar_state cookie is 'false'", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi
        .fn()
        .mockImplementation((key: string) =>
          key === "sidebar_state" ? { value: "false" } : undefined,
        ),
    } as unknown as ReadonlyRequestCookies);

    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider).toHaveAttribute("data-default-open", "false");
  });

  test("defaultOpen is undefined string for unrecognized cookie value", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi
        .fn()
        .mockImplementation((key: string) =>
          key === "sidebar_state" ? { value: "something-else" } : undefined,
        ),
    } as unknown as ReadonlyRequestCookies);

    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    // parseSidebarOpenCookie returns undefined for "something-else", which String(undefined) => "undefined"
    expect(sidebarProvider).toHaveAttribute("data-default-open", "undefined");
  });

  test("defaultOpen is undefined string for empty string cookie value", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi
        .fn()
        .mockImplementation((key: string) =>
          key === "sidebar_state" ? { value: "" } : undefined,
        ),
    } as unknown as ReadonlyRequestCookies);

    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider).toHaveAttribute("data-default-open", "undefined");
  });

  // ── Children placement ─────────────────────────────────────────────

  test("children are placed inside SidebarInset (not SidebarProvider)", async () => {
    render(
      await WorkspaceContent({
        children: <span data-testid="test-child">inside</span>,
      }),
    );
    const sidebarInset = screen.getByTestId("sidebar-inset");
    expect(sidebarInset).toContainElement(screen.getByTestId("test-child"));
  });

  // ── CSS classes ────────────────────────────────────────────────────

  test("SidebarProvider has h-screen class", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider.className).toContain("h-screen");
  });

  test("SidebarInset has min-w-0 class", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarInset = screen.getByTestId("sidebar-inset");
    expect(sidebarInset.className).toContain("min-w-0");
  });

  // ── Multiple children ──────────────────────────────────────────────

  test("renders multiple children inside SidebarInset", async () => {
    render(
      await WorkspaceContent({
        children: (
          <>
            <div data-testid="child-1">First</div>
            <div data-testid="child-2">Second</div>
          </>
        ),
      }),
    );
    expect(screen.getByTestId("child-1")).toBeInTheDocument();
    expect(screen.getByTestId("child-2")).toBeInTheDocument();
    const sidebarInset = screen.getByTestId("sidebar-inset");
    expect(sidebarInset).toContainElement(screen.getByTestId("child-1"));
    expect(sidebarInset).toContainElement(screen.getByTestId("child-2"));
  });

  // ── Nested cookie with no value ────────────────────────────────────

  test("handles cookie store returning null for sidebar_state", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(null),
    } as unknown as ReadonlyRequestCookies);

    render(await WorkspaceContent({ children: <div>child</div> }));
    const sidebarProvider = screen.getByTestId("sidebar-provider");
    expect(sidebarProvider).toHaveAttribute("data-default-open", "undefined");
  });

  // ── QueryClientProvider wraps everything ───────────────────────────

  test("QueryClientProvider wraps SidebarProvider", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const qcp = screen.getByTestId("query-client-provider");
    expect(qcp).toContainElement(screen.getByTestId("sidebar-provider"));
  });

  test("QueryClientProvider wraps CommandPalette", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const qcp = screen.getByTestId("query-client-provider");
    expect(qcp).toContainElement(screen.getByTestId("command-palette"));
  });

  test("QueryClientProvider wraps Toaster", async () => {
    render(await WorkspaceContent({ children: <div>child</div> }));
    const qcp = screen.getByTestId("query-client-provider");
    expect(qcp).toContainElement(screen.getByTestId("toaster"));
  });
});
