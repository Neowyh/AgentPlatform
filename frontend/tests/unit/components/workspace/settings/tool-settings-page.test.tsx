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
const mockAddMCPServer = vi.fn();
const mockUpdateMCPServer = vi.fn();
const mockDeleteMCPServer = vi.fn();

vi.mock("@/core/mcp/hooks", () => ({
  useMCPConfig: () => ({
    config: mockConfig,
    isLoading: mockIsLoading,
    error: mockError,
  }),
  useEnableMCPServer: () => ({
    mutate: mockEnableMCPServer,
    isPending: false,
  }),
  useAddMCPServer: () => ({
    mutateAsync: mockAddMCPServer,
    isPending: false,
  }),
  useUpdateMCPServer: () => ({
    mutateAsync: mockUpdateMCPServer,
    isPending: false,
  }),
  useDeleteMCPServer: () => ({
    mutateAsync: mockDeleteMCPServer,
    isPending: false,
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
          addServer: "Add Server",
          editServer: "Edit Server",
          deleteConfirmTitle: "Delete server?",
          deleteConfirmDescription: "This server will be removed.",
          serverName: "Server Name",
          serverType: "Type",
          command: "Command",
          args: "Arguments",
          url: "URL",
          env: "Environment Variables",
          headers: "Headers",
          emptyState: "No MCP servers configured.",
          validationNameRequired: "Server name cannot be empty.",
          validationNameExists: "A server with this name already exists.",
          addSuccess: "Server added",
          editSuccess: "Server updated",
          deleteSuccess: "Server deleted",
        },
      },
      common: {
        loading: "Loading...",
        cancel: "Cancel",
        save: "Save",
        delete: "Delete",
        edit: "Edit",
      },
    },
  }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
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

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    variant,
    size,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    variant?: string;
    size?: string;
    disabled?: boolean;
  }) => (
    <button
      onClick={onClick}
      data-variant={variant}
      data-size={size}
      disabled={disabled}
    >
      {children}
    </button>
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
  }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogFooter: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: ({
    value,
    onChange,
    disabled,
    readOnly,
    placeholder,
    className,
  }: {
    value?: string;
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
    disabled?: boolean;
    readOnly?: boolean;
    placeholder?: string;
    className?: string;
  }) => (
    <input
      value={value}
      onChange={onChange}
      disabled={disabled}
      readOnly={readOnly}
      placeholder={placeholder}
      className={className}
    />
  ),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: ({
    value,
    onChange,
    rows,
    placeholder,
  }: {
    value?: string;
    onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
    rows?: number;
    placeholder?: string;
  }) => (
    <textarea
      value={value}
      onChange={onChange}
      rows={rows}
      placeholder={placeholder}
    />
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
  }) => (
    <select data-testid="select" value={value}>
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectValue: () => <span />,
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectItem: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => <option value={value}>{children}</option>,
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

  test("renders empty state when config has no servers", () => {
    mockConfig = { mcp_servers: {} };
    render(<ToolSettingsPage />);
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
    expect(screen.getByText("No MCP servers configured.")).toBeInTheDocument();
  });

  test("renders add server button", () => {
    render(<ToolSettingsPage />);
    expect(screen.getByText("Add Server")).toBeInTheDocument();
  });

  test("clicking switch calls enableMCPServer with correct args", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
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
    await user.click(switches[1]!);
    expect(mockEnableMCPServer).toHaveBeenCalledWith({
      serverName: "web-search",
      enabled: true,
    });
  });
});
