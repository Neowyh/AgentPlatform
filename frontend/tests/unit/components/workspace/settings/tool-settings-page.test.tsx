import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockConfig: {
  mcp_servers: Record<string, { description: string; enabled: boolean }>;
} | null = {
  mcp_servers: {
    "code-runner": {
      description: "Run code snippets",
      enabled: true,
    },
    "web-search": {
      description: "Search the web",
      enabled: false,
    },
  },
};
let mockIsLoading = false;
let mockError: Error | null = null;
const mockEnableMCPServer = vi.fn();

vi.mock("@/core/mcp/hooks", () => ({
  useMCPConfig: () => ({
    config: mockConfig,
    isLoading: mockIsLoading,
    error: mockError,
  }),
  useEnableMCPServer: () => ({
    mutate: mockEnableMCPServer,
  }),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        tools: {
          title: "Tools",
          description: "Manage MCP servers",
        },
      },
      common: {
        loading: "Loading...",
      },
    },
  }),
}));

vi.mock("@/components/workspace/settings/settings-section", () => ({
  SettingsSection: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <div data-testid="settings-section">
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/item", () => ({
  Item: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
    variant?: string;
  }) => (
    <div data-testid="item" className={className}>
      {children}
    </div>
  ),
  ItemContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  ItemTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  ItemDescription: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  ItemActions: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    disabled,
  }: {
    checked?: boolean;
    onCheckedChange?: (v: boolean) => void;
    disabled?: boolean;
  }) => (
    <button
      role="switch"
      data-checked={checked}
      data-disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
    >
      Switch
    </button>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ToolSettingsPage: typeof import("@/components/workspace/settings/tool-settings-page").ToolSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  mockConfig = {
    mcp_servers: {
      "code-runner": {
        description: "Run code snippets",
        enabled: true,
      },
      "web-search": {
        description: "Search the web",
        enabled: false,
      },
    },
  };
  mockIsLoading = false;
  mockError = null;
  const mod =
    await import("@/components/workspace/settings/tool-settings-page");
  ToolSettingsPage = mod.ToolSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ToolSettingsPage", () => {
  test("renders the settings section with title", () => {
    render(<ToolSettingsPage />);
    expect(screen.getByText("Tools")).toBeInTheDocument();
  });

  test("renders description", () => {
    render(<ToolSettingsPage />);
    expect(screen.getByText("Manage MCP servers")).toBeInTheDocument();
  });

  test("renders server names", () => {
    render(<ToolSettingsPage />);
    expect(screen.getByText("code-runner")).toBeInTheDocument();
    expect(screen.getByText("web-search")).toBeInTheDocument();
  });

  test("renders server descriptions", () => {
    render(<ToolSettingsPage />);
    expect(screen.getByText("Run code snippets")).toBeInTheDocument();
    expect(screen.getByText("Search the web")).toBeInTheDocument();
  });

  test("renders switch for each server", () => {
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(2);
  });

  test("shows correct enabled state for servers", () => {
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
    expect(switches[0]!.getAttribute("data-checked")).toBe("true");
    expect(switches[1]!.getAttribute("data-checked")).toBe("false");
  });

  test("shows loading state", () => {
    mockConfig = null;
    mockIsLoading = true;
    render(<ToolSettingsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows error state", () => {
    mockConfig = null;
    mockError = new Error("Config error");
    render(<ToolSettingsPage />);
    expect(screen.getByText("Error: Config error")).toBeInTheDocument();
  });

  test("renders empty when config has no servers", () => {
    mockConfig = { mcp_servers: {} };
    render(<ToolSettingsPage />);
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
  });

  test("clicking switch calls enableMCPServer with correct args", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
    // Click the first switch (code-runner, currently enabled=true) to disable it
    await user.click(switches[0]!);
    expect(mockEnableMCPServer).toHaveBeenCalledWith({
      serverName: "code-runner",
      enabled: false,
    });
  });

  test("clicking disabled switch enables the server", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
    // Click the second switch (web-search, currently enabled=false) to enable it
    await user.click(switches[1]!);
    expect(mockEnableMCPServer).toHaveBeenCalledWith({
      serverName: "web-search",
      enabled: true,
    });
  });
});
