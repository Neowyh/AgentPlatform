import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

// Dialog – pass through data-testid from the component (data-testid="settings-dialog")
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
    onOpenChange,
    ...props
  }: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    [key: string]: unknown;
  }) => (open ? <div {...props}>{children}</div> : null),
  DialogContent: ({
    children,
    className,
    ...props
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="settings-dialog-content" className={className} {...props}>
      {children}
    </div>
  ),
  DialogHeader: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
}));

// ScrollArea
vi.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="scroll-area" className={className}>
      {children}
    </div>
  ),
}));

// Settings sub-pages
vi.mock("@/components/workspace/settings/about-settings-page", () => ({
  AboutSettingsPage: () => <div data-testid="about-page">About Page</div>,
}));
vi.mock("@/components/workspace/settings/account-settings-page", () => ({
  AccountSettingsPage: () => <div data-testid="account-page">Account Page</div>,
}));
vi.mock("@/components/workspace/settings/appearance-settings-page", () => ({
  AppearanceSettingsPage: () => (
    <div data-testid="appearance-page">Appearance Page</div>
  ),
}));
vi.mock("@/components/workspace/settings/memory-settings-page", () => ({
  MemorySettingsPage: () => <div data-testid="memory-page">Memory Page</div>,
}));
vi.mock("@/components/workspace/settings/notification-settings-page", () => ({
  NotificationSettingsPage: () => (
    <div data-testid="notification-page">Notification Page</div>
  ),
}));
vi.mock("@/components/workspace/settings/skill-settings-page", () => ({
  SkillSettingsPage: ({ onClose }: { onClose?: () => void }) => (
    <div data-testid="skills-page">
      Skills Page
      {onClose && (
        <button data-testid="skills-close" onClick={onClose}>
          Close
        </button>
      )}
    </div>
  ),
}));
vi.mock("@/components/workspace/settings/tool-settings-page", () => ({
  ToolSettingsPage: () => <div data-testid="tools-page">Tools Page</div>,
}));

// i18n
const mockT = {
  settings: {
    title: "Settings",
    description: "Manage your preferences",
    sections: {
      account: "Account",
      appearance: "Appearance",
      notification: "Notifications",
      memory: "Memory",
      tools: "Tools",
      skills: "Skills",
      about: "About",
    },
  },
};
vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: mockT,
    changeLocale: vi.fn(),
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let SettingsDialog: typeof import("@/components/workspace/settings/settings-dialog").SettingsDialog;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/settings/settings-dialog");
  SettingsDialog = mod.SettingsDialog;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SettingsDialog", () => {
  // ── Open / Close ─────────────────────────────────────────────────────────

  test("renders nothing when closed", () => {
    render(<SettingsDialog open={false} onOpenChange={vi.fn()} />);
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
  });

  test("renders the dialog when open", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByTestId("settings-dialog")).toBeInTheDocument();
  });

  test("displays the settings title", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  test("displays the settings description", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText("Manage your preferences")).toBeInTheDocument();
  });

  // ── Navigation tabs ──────────────────────────────────────────────────────

  test("renders all settings section tabs", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByTestId("settings-tab-account")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-appearance")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-notification")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-memory")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-tools")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-skills")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-about")).toBeInTheDocument();
  });

  test("renders tab labels", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText("Account")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Tools")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("About")).toBeInTheDocument();
  });

  // ── Default section ──────────────────────────────────────────────────────

  test("defaults to appearance section when no defaultSection provided", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByTestId("appearance-page")).toBeInTheDocument();
    expect(screen.queryByTestId("account-page")).not.toBeInTheDocument();
  });

  test("opens to the specified defaultSection", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="about"
      />,
    );
    expect(screen.getByTestId("about-page")).toBeInTheDocument();
    expect(screen.queryByTestId("appearance-page")).not.toBeInTheDocument();
  });

  test("opens to account section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="account"
      />,
    );
    expect(screen.getByTestId("account-page")).toBeInTheDocument();
  });

  test("opens to memory section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="memory"
      />,
    );
    expect(screen.getByTestId("memory-page")).toBeInTheDocument();
  });

  test("opens to tools section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="tools"
      />,
    );
    expect(screen.getByTestId("tools-page")).toBeInTheDocument();
  });

  test("opens to skills section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="skills"
      />,
    );
    expect(screen.getByTestId("skills-page")).toBeInTheDocument();
  });

  test("opens to notification section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="notification"
      />,
    );
    expect(screen.getByTestId("notification-page")).toBeInTheDocument();
  });

  // ── Section switching ────────────────────────────────────────────────────

  test("switches to account section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    // Initially shows appearance
    expect(screen.getByTestId("appearance-page")).toBeInTheDocument();

    await user.click(screen.getByTestId("settings-tab-account"));

    await waitFor(() => {
      expect(screen.getByTestId("account-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("appearance-page")).not.toBeInTheDocument();
  });

  test("switches to tools section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByTestId("settings-tab-tools"));

    await waitFor(() => {
      expect(screen.getByTestId("tools-page")).toBeInTheDocument();
    });
  });

  test("switches to about section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByTestId("settings-tab-about"));

    await waitFor(() => {
      expect(screen.getByTestId("about-page")).toBeInTheDocument();
    });
  });

  test("switches to memory section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByTestId("settings-tab-memory"));

    await waitFor(() => {
      expect(screen.getByTestId("memory-page")).toBeInTheDocument();
    });
  });

  test("switches to notification section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByTestId("settings-tab-notification"));

    await waitFor(() => {
      expect(screen.getByTestId("notification-page")).toBeInTheDocument();
    });
  });

  test("switches to skills section when tab clicked", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    await user.click(screen.getByTestId("settings-tab-skills"));

    await waitFor(() => {
      expect(screen.getByTestId("skills-page")).toBeInTheDocument();
    });
  });

  test("only renders one section page at a time", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    // Start at appearance
    expect(screen.getByTestId("appearance-page")).toBeInTheDocument();
    expect(screen.queryByTestId("tools-page")).not.toBeInTheDocument();

    // Switch to tools
    await user.click(screen.getByTestId("settings-tab-tools"));

    await waitFor(() => {
      expect(screen.getByTestId("tools-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("appearance-page")).not.toBeInTheDocument();
  });

  // ── Reset section on open ────────────────────────────────────────────────

  test("resets to defaultSection when dialog opens", async () => {
    const onOpenChange = vi.fn();
    const { rerender } = render(
      <SettingsDialog open={false} onOpenChange={onOpenChange} />,
    );

    // Open with about
    rerender(
      <SettingsDialog
        open={true}
        onOpenChange={onOpenChange}
        defaultSection="about"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("about-page")).toBeInTheDocument();
    });
  });

  // ── ScrollArea ───────────────────────────────────────────────────────────

  test("renders content inside a ScrollArea", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByTestId("scroll-area")).toBeInTheDocument();
  });

  // ── Active tab styling ───────────────────────────────────────────────────

  test("applies active styling to the current section tab", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="tools"
      />,
    );
    const toolsTab = screen.getByTestId("settings-tab-tools");
    expect(toolsTab.className).toContain("bg-primary");
  });

  test("applies inactive styling to non-current section tabs", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="tools"
      />,
    );
    const accountTab = screen.getByTestId("settings-tab-account");
    expect(accountTab.className).toContain("text-muted-foreground");
  });
});
