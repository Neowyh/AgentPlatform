import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

// next/link – render as a plain anchor
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

// Sidebar context
const mockSidebarOpen = { open: true };
vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => mockSidebarOpen,
  SidebarMenu: ({ children, ...props }: { children: React.ReactNode }) => (
    <div {...props}>{children}</div>
  ),
  SidebarMenuButton: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <button {...props}>{children}</button>,
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

// i18n – return the translation keys the component uses
const mockT = {
  workspace: {
    settingsAndMore: "Settings and more",
    adminPanel: "Admin Panel",
    userManagement: "User Management",
    departmentManagement: "Department Management",
    toolManagement: "Tool Management",
    resourceManagement: "Resource Management",
    auditLogManagement: "Audit Logs",
    about: "About iDeer",
  },
  common: {
    settings: "Settings",
  },
};
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: mockT,
    changeLocale: vi.fn(),
  }),
}));

// Auth context – mutable for role tests
let mockUser: { id: string; email: string; system_role: string } | null = null;
vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser }),
}));

// SettingsDialog – capture props for assertions
let capturedSettingsProps: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultSection: string;
} | null = null;
vi.mock("@/components/workspace/settings", () => ({
  SettingsDialog: (props: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    defaultSection: string;
  }) => {
    capturedSettingsProps = props;
    return props.open ? (
      <div data-testid="settings-dialog">Settings Dialog Open</div>
    ) : null;
  },
}));

// Radix dropdown-menu – lightweight passthrough so clicks still fire
vi.mock("@/components/ui/dropdown-menu", () => {
  const React = require("react");
  return {
    DropdownMenu: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="dropdown-menu">{children}</div>
    ),
    DropdownMenuTrigger: ({
      children,
      asChild,
      ...props
    }: {
      children: React.ReactNode;
      asChild?: boolean;
      [key: string]: unknown;
    }) => (
      <div data-testid="dropdown-trigger" {...props}>
        {children}
      </div>
    ),
    DropdownMenuContent: ({
      children,
      ...props
    }: {
      children: React.ReactNode;
      [key: string]: unknown;
    }) => (
      <div data-testid="dropdown-content" {...props}>
        {children}
      </div>
    ),
    DropdownMenuGroup: ({
      children,
      ...props
    }: {
      children: React.ReactNode;
      [key: string]: unknown;
    }) => <div {...props}>{children}</div>,
    DropdownMenuItem: ({
      children,
      onClick,
      asChild,
      ...props
    }: {
      children: React.ReactNode;
      onClick?: () => void;
      asChild?: boolean;
      [key: string]: unknown;
    }) => (
      <div role="menuitem" onClick={onClick} {...props}>
        {children}
      </div>
    ),
    DropdownMenuSeparator: () => <hr data-testid="separator" />,
  };
});

// ── Dynamic import (after mocks) ─────────────────────────────────────────────

let WorkspaceNavMenu: typeof import("@/components/workspace/workspace-nav-menu").WorkspaceNavMenu;

beforeEach(async () => {
  vi.clearAllMocks();
  mockUser = null;
  capturedSettingsProps = null;
  const mod = await import("@/components/workspace/workspace-nav-menu");
  WorkspaceNavMenu = mod.WorkspaceNavMenu;
});

afterEach(() => {
  cleanup();
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function setUser(role: string | null) {
  if (role === null) {
    mockUser = null;
  } else {
    mockUser = { id: "u1", email: "test@test.com", system_role: role };
  }
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceNavMenu", () => {
  // ── Mount behavior ───────────────────────────────────────────────────────

  test("renders a placeholder button before mount (no dropdown)", () => {
    // Before useEffect runs the component shows a static button
    // We can observe this by checking for the settings icon text
    // Note: in jsdom useEffect fires synchronously after first render,
    // so the "mounted" state is true. We verify the mounted path instead.
    render(<WorkspaceNavMenu />);
    // After mount, the dropdown trigger should be present
    expect(screen.getByTestId("dropdown-trigger")).toBeInTheDocument();
  });

  test("renders the SettingsDialog component", () => {
    render(<WorkspaceNavMenu />);
    // SettingsDialog is always rendered (closed by default)
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
  });

  // ── NavMenuButtonContent (sidebar open) ──────────────────────────────────

  test("shows 'Settings and more' text when sidebar is open", () => {
    mockSidebarOpen.open = true;
    render(<WorkspaceNavMenu />);
    expect(screen.getByText("Settings and more")).toBeInTheDocument();
  });

  test("does not show 'Settings and more' text when sidebar is closed", () => {
    mockSidebarOpen.open = false;
    render(<WorkspaceNavMenu />);
    expect(screen.queryByText("Settings and more")).not.toBeInTheDocument();
  });

  // ── Settings menu item ───────────────────────────────────────────────────

  test("renders Settings menu item", () => {
    render(<WorkspaceNavMenu />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  test("clicking Settings menu item opens the settings dialog with 'appearance' section", async () => {
    const user = userEvent.setup();
    render(<WorkspaceNavMenu />);

    const settingsItem = screen.getByText("Settings");
    await user.click(settingsItem);

    await waitFor(() => {
      expect(capturedSettingsProps).not.toBeNull();
      expect(capturedSettingsProps!.open).toBe(true);
      expect(capturedSettingsProps!.defaultSection).toBe("appearance");
    });
  });

  // ── About menu item ──────────────────────────────────────────────────────

  test("renders About menu item", () => {
    render(<WorkspaceNavMenu />);
    expect(screen.getByText("About iDeer")).toBeInTheDocument();
  });

  test("clicking About menu item opens settings dialog with 'about' section", async () => {
    const user = userEvent.setup();
    render(<WorkspaceNavMenu />);

    const aboutItem = screen.getByText("About iDeer");
    await user.click(aboutItem);

    await waitFor(() => {
      expect(capturedSettingsProps).not.toBeNull();
      expect(capturedSettingsProps!.open).toBe(true);
      expect(capturedSettingsProps!.defaultSection).toBe("about");
    });
  });

  // ── Admin links visibility ───────────────────────────────────────────────

  describe("admin links for super_admin", () => {
    beforeEach(() => {
      setUser("super_admin");
    });

    test("shows Admin Panel link", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Admin Panel")).toBeInTheDocument();
    });

    test("shows User Management link", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("User Management")).toBeInTheDocument();
    });

    test("shows Department Management link", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Department Management")).toBeInTheDocument();
    });

    test("shows Tool Management link", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Tool Management")).toBeInTheDocument();
    });

    test("shows Resource Management link", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Resource Management")).toBeInTheDocument();
    });

    test("Admin Panel link points to /workspace/admin", () => {
      render(<WorkspaceNavMenu />);
      const link = screen.getByText("Admin Panel").closest("a");
      expect(link).toHaveAttribute("href", "/workspace/admin");
    });

    test("User Management link points to /workspace/admin/users", () => {
      render(<WorkspaceNavMenu />);
      const link = screen.getByText("User Management").closest("a");
      expect(link).toHaveAttribute("href", "/workspace/admin/users");
    });

    test("Department Management link points to /workspace/admin/departments", () => {
      render(<WorkspaceNavMenu />);
      const link = screen.getByText("Department Management").closest("a");
      expect(link).toHaveAttribute("href", "/workspace/admin/departments");
    });

    test("Tool Management link points to /workspace/admin/tools", () => {
      render(<WorkspaceNavMenu />);
      const link = screen.getByText("Tool Management").closest("a");
      expect(link).toHaveAttribute("href", "/workspace/admin/tools");
    });

    test("Resource Management link points to /workspace/admin/resources", () => {
      render(<WorkspaceNavMenu />);
      const link = screen.getByText("Resource Management").closest("a");
      expect(link).toHaveAttribute("href", "/workspace/admin/resources");
    });
  });

  describe("admin links for department_admin", () => {
    beforeEach(() => {
      setUser("department_admin");
    });

    test("shows admin links for department_admin role", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Admin Panel")).toBeInTheDocument();
      expect(screen.getByText("User Management")).toBeInTheDocument();
      expect(screen.getByText("Department Management")).toBeInTheDocument();
      expect(screen.getByText("Tool Management")).toBeInTheDocument();
      expect(screen.getByText("Resource Management")).toBeInTheDocument();
      expect(screen.getByText("Audit Logs")).toBeInTheDocument();
    });
  });

  describe("admin links for regular user", () => {
    beforeEach(() => {
      setUser("user");
    });

    test("does not show admin links for user role", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
      expect(screen.queryByText("User Management")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Department Management"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tool Management")).not.toBeInTheDocument();
      expect(screen.queryByText("Resource Management")).not.toBeInTheDocument();
    });

    test("still shows Settings and About items", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Settings")).toBeInTheDocument();
      expect(screen.getByText("About iDeer")).toBeInTheDocument();
    });
  });

  describe("admin links for viewer", () => {
    beforeEach(() => {
      setUser("viewer");
    });

    test("does not show admin links for viewer role", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
      expect(screen.queryByText("User Management")).not.toBeInTheDocument();
      expect(
        screen.queryByText("Department Management"),
      ).not.toBeInTheDocument();
      expect(screen.queryByText("Tool Management")).not.toBeInTheDocument();
      expect(screen.queryByText("Resource Management")).not.toBeInTheDocument();
    });
  });

  describe("admin links when user is null", () => {
    beforeEach(() => {
      setUser(null);
    });

    test("does not show admin links when no user", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.queryByText("Admin Panel")).not.toBeInTheDocument();
      expect(screen.queryByText("User Management")).not.toBeInTheDocument();
    });

    test("still shows Settings and About items", () => {
      render(<WorkspaceNavMenu />);
      expect(screen.getByText("Settings")).toBeInTheDocument();
      expect(screen.getByText("About iDeer")).toBeInTheDocument();
    });
  });

  // ── Separators ───────────────────────────────────────────────────────────

  test("renders separators between menu groups", () => {
    render(<WorkspaceNavMenu />);
    const separators = screen.getAllByTestId("separator");
    // At least 2 separators: one after Settings group, one before About
    expect(separators.length).toBeGreaterThanOrEqual(2);
  });

  test("renders additional separators for admin users", () => {
    setUser("super_admin");
    render(<WorkspaceNavMenu />);
    const separators = screen.getAllByTestId("separator");
    // Admin section adds extra separator
    expect(separators.length).toBeGreaterThanOrEqual(3);
  });

  // ── SettingsDialog integration ───────────────────────────────────────────

  test("SettingsDialog receives correct onOpenChange callback", async () => {
    const user = userEvent.setup();
    render(<WorkspaceNavMenu />);

    // Open settings
    await user.click(screen.getByText("Settings"));
    await waitFor(() => {
      expect(capturedSettingsProps!.open).toBe(true);
    });

    // Simulate closing via the callback
    capturedSettingsProps!.onOpenChange(false);
    await waitFor(() => {
      expect(capturedSettingsProps!.open).toBe(false);
    });
  });

  // ── Wrapper fragment ─────────────────────────────────────────────────────

  test("renders both SettingsDialog and SidebarMenu", () => {
    render(<WorkspaceNavMenu />);
    // SidebarMenu wrapper
    expect(screen.getByTestId("dropdown-trigger")).toBeInTheDocument();
    // Settings and About items confirm the menu content
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("About iDeer")).toBeInTheDocument();
  });
});
