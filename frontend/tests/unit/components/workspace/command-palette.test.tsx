import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      shortcuts: {
        searchActions: "Search actions...",
        noResults: "No results",
        actions: "Actions",
        openCommandPalette: "Open Command Palette",
        keyboardShortcuts: "Keyboard Shortcuts",
        keyboardShortcutsDescription: "Keyboard shortcuts description",
        toggleSidebar: "Toggle Sidebar",
      },
      sidebar: {
        newChat: "New Chat",
      },
      common: {
        settings: "Settings",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

// Capture the shortcuts so we can invoke their actions in tests
let capturedShortcuts: Array<{ key: string; action: () => void }> = [];
vi.mock("@/hooks/use-global-shortcuts", () => ({
  useGlobalShortcuts: (
    shortcuts: Array<{ key: string; action: () => void }>,
  ) => {
    capturedShortcuts = shortcuts;
  },
}));

vi.mock("@/components/ui/command", () => ({
  CommandDialog: ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open?: boolean;
  }) => (open ? <div data-testid="command-dialog">{children}</div> : null),
  CommandInput: ({ placeholder }: { placeholder?: string }) => (
    <input data-testid="command-input" placeholder={placeholder} />
  ),
  CommandList: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="command-list">{children}</div>
  ),
  CommandEmpty: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="command-empty">{children}</div>
  ),
  CommandGroup: ({
    children,
    heading,
  }: {
    children: React.ReactNode;
    heading?: string;
  }) => (
    <div data-testid="command-group" data-heading={heading}>
      {children}
    </div>
  ),
  CommandItem: ({
    children,
    onSelect,
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
  }) => (
    <div data-testid="command-item" onClick={onSelect}>
      {children}
    </div>
  ),
  CommandShortcut: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="command-shortcut">{children}</span>
  ),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open?: boolean;
  }) => (open ? <div data-testid="dialog">{children}</div> : null),
  DialogContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="dialog-content" className={className}>
      {children}
    </div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
}));

vi.mock("@/components/workspace/settings/settings-dialog", () => ({
  SettingsDialog: ({
    open,
    onOpenChange,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
  }) =>
    open ? (
      <div data-testid="settings-dialog">
        <button
          data-testid="settings-close"
          onClick={() => onOpenChange(false)}
        >
          Close
        </button>
      </div>
    ) : null,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let CommandPalette: typeof import("@/components/workspace/command-palette").CommandPalette;

beforeEach(async () => {
  vi.clearAllMocks();
  vi.resetModules();
  capturedShortcuts = [];
  const mod = await import("@/components/workspace/command-palette");
  CommandPalette = mod.CommandPalette;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("CommandPalette", () => {
  test("renders without crashing", () => {
    render(<CommandPalette />);
    expect(screen.queryByTestId("command-dialog")).not.toBeInTheDocument();
  });

  test("does not render settings dialog initially", () => {
    render(<CommandPalette />);
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
  });

  test("does not render shortcuts dialog initially", () => {
    render(<CommandPalette />);
    expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
  });

  test("registers shortcuts via useGlobalShortcuts", () => {
    render(<CommandPalette />);
    expect(capturedShortcuts.length).toBe(4);
  });

  test("Cmd+K shortcut toggles command dialog open", async () => {
    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    expect(kShortcut).toBeDefined();
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });
  });

  test("Cmd+, shortcut opens settings dialog", async () => {
    render(<CommandPalette />);
    const commaShortcut = capturedShortcuts.find((s) => s.key === ",");
    expect(commaShortcut).toBeDefined();
    commaShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("settings-dialog")).toBeInTheDocument();
    });
  });

  test("Cmd+/ shortcut opens shortcuts dialog", async () => {
    render(<CommandPalette />);
    const slashShortcut = capturedShortcuts.find((s) => s.key === "/");
    expect(slashShortcut).toBeDefined();
    slashShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });
  });

  test("Cmd+Shift+N shortcut navigates to new chat", () => {
    render(<CommandPalette />);
    const nShortcut = capturedShortcuts.find((s) => s.key === "n");
    expect(nShortcut).toBeDefined();
    nShortcut!.action();
    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("command dialog renders input and items", async () => {
    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });

    expect(screen.getByTestId("command-input")).toBeInTheDocument();
    expect(screen.getByTestId("command-list")).toBeInTheDocument();
    expect(screen.getByTestId("command-group")).toBeInTheDocument();
    expect(screen.getByTestId("command-empty")).toBeInTheDocument();
  });

  test("clicking new chat in command palette navigates", async () => {
    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });

    const commandItems = screen.getAllByTestId("command-item");
    const newChatItem = commandItems[0];
    newChatItem!.click();
    expect(mockPush).toHaveBeenCalledWith("/workspace/chats/new");
  });

  test("clicking settings in command palette opens settings", async () => {
    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });

    const commandItems = screen.getAllByTestId("command-item");
    const settingsItem = commandItems[1];
    settingsItem!.click();
    await waitFor(() => {
      expect(screen.getByTestId("settings-dialog")).toBeInTheDocument();
    });
  });

  test("clicking shortcuts in command palette opens shortcuts dialog", async () => {
    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });

    const commandItems = screen.getAllByTestId("command-item");
    const shortcutsItem = commandItems[2];
    shortcutsItem!.click();
    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });
  });

  test("shortcuts dialog shows keyboard shortcut list", async () => {
    render(<CommandPalette />);
    const slashShortcut = capturedShortcuts.find((s) => s.key === "/");
    slashShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("dialog")).toBeInTheDocument();
    });
    expect(screen.getByTestId("dialog-content")).toBeInTheDocument();
  });

  test("settings dialog can be closed", async () => {
    render(<CommandPalette />);
    const commaShortcut = capturedShortcuts.find((s) => s.key === ",");
    commaShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("settings-dialog")).toBeInTheDocument();
    });
    const closeBtn = screen.getByTestId("settings-close");
    closeBtn.click();
    await waitFor(() => {
      expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
    });
  });

  test("command dialog renders with Mac meta key", async () => {
    const originalUA = navigator.userAgent;
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      configurable: true,
    });

    render(<CommandPalette />);
    const kShortcut = capturedShortcuts.find((s) => s.key === "k");
    kShortcut!.action();
    await waitFor(() => {
      expect(screen.getByTestId("command-dialog")).toBeInTheDocument();
    });
    const shortcuts = screen.getAllByTestId("command-shortcut");
    expect(shortcuts.length).toBeGreaterThan(0);

    Object.defineProperty(navigator, "userAgent", {
      value: originalUA,
      configurable: true,
    });
  });
});
