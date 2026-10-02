import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const push = vi.fn();
const router = { push };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

// Capability probes behind the Channels/Integrations entries. State objects
// are hoisted so the mock factories can read them and tests can flip them.
const channelProvidersState = vi.hoisted(() => ({
  enabled: true,
  providers: [] as Array<{
    provider: string;
    enabled: boolean;
    configured: boolean;
    unavailable_reason?: string | null;
  }>,
  isLoading: false,
  error: null as unknown,
}));

const larkIntegrationState = vi.hoisted(() => ({
  data: null as unknown,
  isLoading: false,
  error: null as unknown,
  usable: false,
}));
vi.mock("@/core/channels/hooks", () => ({
  useChannelProviders: () => ({
    enabled: channelProvidersState.enabled,
    providers: channelProvidersState.providers,
    isLoading: channelProvidersState.isLoading,
    error: channelProvidersState.error,
  }),
}));

vi.mock("@/core/integrations/lark", () => ({
  useLarkIntegrationStatus: () => ({
    data: larkIntegrationState.data,
    isLoading: larkIntegrationState.isLoading,
    error: larkIntegrationState.error,
  }),
  isLarkIntegrationUsable: () => larkIntegrationState.usable,
}));

function usableChannelProvider() {
  return {
    provider: "slack",
    enabled: true,
    configured: true,
    unavailable_reason: null,
  };
}

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
vi.mock("@/components/workspace/settings/channels-settings-page", () => ({
  ChannelsSettingsPage: () => (
    <div data-testid="channels-page">Channels Page</div>
  ),
}));
// 合并形态七分区（account/appearance/channels/memory/notification/subagents/about）；
// integrations/tools/skills 分区已删，对应入口改跳能力中心（legacy 深链由
// workspace-settings-deep-link 的测试覆盖）。

// i18n
const mockT = {
  settings: {
    title: "Settings",
    description: "Manage your preferences",
    sections: {
      account: "Account",
      appearance: "Appearance",
      notification: "Notifications",
      channels: "Channels",
      integrations: "Integrations",
      memory: "Memory",
      subagents: "Subagents",
      skills: "Skills",
      tools: "Tools",
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
  // Default to a deployment whose channel and Lark capabilities are present;
  // individual tests flip these to exercise availability variants.
  channelProvidersState.enabled = true;
  channelProvidersState.providers = [usableChannelProvider()];
  channelProvidersState.isLoading = false;
  channelProvidersState.error = null;
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

  test("renders the merged settings sections", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    // 合并形态为本地分区 ∪ 上游 subagents。skills/tools 保留为对话框 tab
    //（点击后按 D4 决议重定向能力中心），integrations 仍受可用性探测门控
    //（默认 mock 不可用 → 不渲染）。
    expect(screen.getByTestId("settings-tab-account")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-appearance")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-notification")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-memory")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-channels")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-subagents")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-skills")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-tools")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-about")).toBeInTheDocument();
    expect(
      screen.queryByTestId("settings-tab-integrations"),
    ).not.toBeInTheDocument();
  });

  test("renders merged tab labels", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText("Account")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Channels")).toBeInTheDocument();
    expect(screen.getByText("Subagents")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("Tools")).toBeInTheDocument();
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

  test("opens to channels section when specified", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="channels"
      />,
    );
    expect(screen.getByTestId("channels-page")).toBeInTheDocument();
  });

  // The merged settings dialog no longer has a standalone "integrations"
  // section; its deep-link test was covered by the channels variants below.

  // 合并后对话框不再渲染 skills/tools tab；"skills/tools 入口跳能力中心"
  // 的断言意图由 workspace-settings-deep-link.test.tsx 覆盖。

  // The merged settings dialog narrowed defaultSection to real sections, so
  // the legacy "tools" deep link is no longer representable; the redirect it
  // exercised lives in legacy-settings-destination and fires from nav clicks.

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

  test("only renders one section page at a time", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    // Start at appearance
    expect(screen.getByTestId("appearance-page")).toBeInTheDocument();
    expect(screen.queryByTestId("memory-page")).not.toBeInTheDocument();

    // Switch to memory
    await user.click(screen.getByTestId("settings-tab-memory"));

    await waitFor(() => {
      expect(screen.getByTestId("memory-page")).toBeInTheDocument();
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
        defaultSection="memory"
      />,
    );
    const memoryTab = screen.getByTestId("settings-tab-memory");
    expect(memoryTab.className).toContain("bg-primary");
  });

  test("applies inactive styling to non-current section tabs", () => {
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="memory"
      />,
    );
    const accountTab = screen.getByTestId("settings-tab-account");
    expect(accountTab.className).toContain("text-muted-foreground");
  });

  // ── Capability-gated entries ─────────────────────────────────────────────

  test("hides the channels entry when the deployment lacks the capability", () => {
    channelProvidersState.providers = [];
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByTestId("settings-tab-channels"),
    ).not.toBeInTheDocument();
    // The familiar sections stay put.
    expect(screen.getByTestId("settings-tab-account")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-appearance")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-notification")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-memory")).toBeInTheDocument();
    expect(screen.getByTestId("settings-tab-about")).toBeInTheDocument();
  });

  test("hides the channels entry when providers exist but none is usable", () => {
    channelProvidersState.providers = [
      {
        provider: "telegram",
        enabled: true,
        configured: false,
        unavailable_reason:
          "Enter the required Telegram credentials to connect this channel.",
      },
    ];
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByTestId("settings-tab-channels"),
    ).not.toBeInTheDocument();
  });

  test("hides the channels entry when channel connections are disabled for the deployment", () => {
    channelProvidersState.enabled = false;
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByTestId("settings-tab-channels"),
    ).not.toBeInTheDocument();
  });

  test("keeps the channels entry hidden while its availability probe resolves", () => {
    channelProvidersState.isLoading = true;
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByTestId("settings-tab-channels"),
    ).not.toBeInTheDocument();
  });

  test("hides the channels entry when its probe fails", () => {
    channelProvidersState.error = new Error("providers unavailable");
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);

    expect(
      screen.queryByTestId("settings-tab-channels"),
    ).not.toBeInTheDocument();
  });

  test("falls back to appearance when a deep-linked capability section is unavailable", () => {
    // Channels is the merged dialog's availability-gated section; with no
    // usable provider the deep link must fall back to the default.
    channelProvidersState.providers = [];
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="channels"
      />,
    );

    expect(screen.getByTestId("appearance-page")).toBeInTheDocument();
    expect(screen.queryByTestId("channels-page")).not.toBeInTheDocument();
  });

  test("still opens a deep-linked capability section when the capability is available", () => {
    channelProvidersState.providers = [usableChannelProvider()];
    render(
      <SettingsDialog
        open={true}
        onOpenChange={vi.fn()}
        defaultSection="channels"
      />,
    );

    expect(screen.getByTestId("channels-page")).toBeInTheDocument();
    expect(screen.queryByTestId("appearance-page")).not.toBeInTheDocument();
  });
});
