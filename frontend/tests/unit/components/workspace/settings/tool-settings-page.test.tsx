import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockConfig: {
  mcp_servers: Record<
    string,
    {
      description: string;
      enabled: boolean;
      type: "stdio" | "sse" | "http";
      command?: string;
      args: string[];
      env: Record<string, string>;
      url?: string;
      headers: Record<string, string>;
    }
  >;
} | null = {
  mcp_servers: {
    "code-runner": {
      description: "Run code snippets",
      enabled: true,
      type: "stdio",
      command: "node",
      args: ["server.js"],
      env: { TOKEN: "abc" },
      headers: {},
    },
    "web-search": {
      description: "Search the web",
      enabled: false,
      type: "http",
      args: [],
      env: {},
      url: "http://localhost:3000/mcp",
      headers: { Authorization: "Bearer token" },
    },
  },
};
let mockIsLoading = false;
let mockError: Error | null = null;
const mockEnableMCPServer = vi.fn();
const mockAddMCPServer = vi.fn();
const mockUpdateMCPServer = vi.fn();
const mockDeleteMCPServer = vi.fn();
let mockAddPending = false;
let mockUpdatePending = false;
let mockDeletePending = false;

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
    get isPending() {
      return mockAddPending;
    },
  }),
  useUpdateMCPServer: () => ({
    mutateAsync: mockUpdateMCPServer,
    get isPending() {
      return mockUpdatePending;
    },
  }),
  useDeleteMCPServer: () => ({
    mutateAsync: mockDeleteMCPServer,
    get isPending() {
      return mockDeletePending;
    },
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
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    variant?: string;
    size?: string;
    disabled?: boolean;
    [key: string]: unknown;
  }) => (
    <button
      onClick={onClick}
      data-variant={variant}
      data-size={size}
      disabled={disabled}
      {...props}
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
    onValueChange,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (value: string) => void;
  }) => (
    <select
      data-testid="select"
      value={value}
      onChange={(event) => onValueChange?.(event.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  SelectValue: () => <span />,
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
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
        type: "stdio",
        command: "node",
        args: ["server.js"],
        env: { TOKEN: "abc" },
        headers: {},
      },
      "web-search": {
        description: "Search the web",
        enabled: false,
        type: "http",
        args: [],
        env: {},
        url: "http://localhost:3000/mcp",
        headers: { Authorization: "Bearer token" },
      },
    },
  };
  mockIsLoading = false;
  mockError = null;
  mockAddPending = false;
  mockUpdatePending = false;
  mockDeletePending = false;
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
    expect(mockEnableMCPServer).toHaveBeenCalledWith(
      {
        serverName: "code-runner",
        enabled: false,
      },
      expect.objectContaining({ onError: expect.any(Function) }),
    );
  });

  test("clicking disabled switch enables the server", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);
    const switches = screen.getAllByRole("switch");
    await user.click(switches[1]!);
    expect(mockEnableMCPServer).toHaveBeenCalledWith(
      {
        serverName: "web-search",
        enabled: true,
      },
      expect.objectContaining({ onError: expect.any(Function) }),
    );
  });

  test("validates add form requires a server name", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.click(screen.getByText("Save"));

    expect(toast.error).toHaveBeenCalledWith("Server name cannot be empty.");
    expect(mockAddMCPServer).not.toHaveBeenCalled();
  });

  test("adds a stdio server from form values", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.type(screen.getByPlaceholderText("e.g. github"), "github");
    await user.type(screen.getByPlaceholderText("e.g. npx"), "npx");
    await user.type(
      screen.getByPlaceholderText(/One argument per line/),
      "-y\n@modelcontextprotocol/server-github",
    );
    await user.type(screen.getByDisplayValue(""), "GitHub tools");
    await user.click(screen.getByText("Save"));

    expect(mockAddMCPServer).toHaveBeenCalledWith({
      name: "github",
      serverConfig: expect.objectContaining({
        enabled: true,
        type: "stdio",
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-github"],
        description: "GitHub tools",
      }),
    });
    expect(toast.success).toHaveBeenCalledWith("Server added");
  });

  test("shows add errors without closing the form", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    mockAddMCPServer.mockRejectedValue(new Error("duplicate"));
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.type(screen.getByPlaceholderText("e.g. github"), "github");
    await user.click(screen.getByText("Save"));

    expect(toast.error).toHaveBeenCalledWith("duplicate");
    expect(screen.getByTestId("dialog")).toBeInTheDocument();
  });

  test("opens edit form and saves updated server config", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    render(<ToolSettingsPage />);

    const editButtons = screen.getAllByLabelText("Edit");
    await user.click(editButtons[0]!);
    expect(screen.getByDisplayValue("code-runner")).toBeDisabled();
    await user.clear(screen.getByDisplayValue("Run code snippets"));
    await user.type(screen.getByDisplayValue(""), "Run snippets safely");
    await user.click(screen.getByText("Save"));

    expect(mockUpdateMCPServer).toHaveBeenCalledWith({
      name: "code-runner",
      serverConfig: expect.objectContaining({
        type: "stdio",
        command: "node",
        args: ["server.js"],
        env: { TOKEN: "abc" },
        description: "Run snippets safely",
      }),
    });
    expect(toast.success).toHaveBeenCalledWith("Server updated");
  });

  test("shows edit errors", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    mockUpdateMCPServer.mockRejectedValue("failed");
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Edit")[0]!);
    await user.click(screen.getByText("Save"));

    expect(toast.error).toHaveBeenCalledWith("failed");
  });

  test("adds and removes environment entries", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.click(screen.getAllByText("Add")[0]!);
    expect(screen.getByDisplayValue("key")).toBeInTheDocument();
    await user.click(
      screen
        .getAllByRole("button")
        .find((button) => button.textContent === "")!,
    );
    expect(screen.queryByDisplayValue("key")).not.toBeInTheDocument();
  });

  test("updates environment entry values", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Edit")[0]!);
    const tokenInput = screen.getByDisplayValue("abc");
    await user.clear(tokenInput);
    await user.type(tokenInput, "updated");
    await user.click(screen.getByText("Save"));

    expect(mockUpdateMCPServer).toHaveBeenCalledWith({
      name: "code-runner",
      serverConfig: expect.objectContaining({
        env: { TOKEN: "updated" },
      }),
    });
  });

  test("adds unique environment keys when key already exists", async () => {
    const user = userEvent.setup();
    mockConfig = {
      mcp_servers: {
        existing: {
          description: "Has env",
          enabled: true,
          type: "stdio",
          command: "node",
          args: [],
          env: { key: "first" },
          headers: {},
        },
      },
    };
    render(<ToolSettingsPage />);

    await user.click(screen.getByLabelText("Edit"));
    await user.click(screen.getAllByText("Add")[0]!);

    expect(screen.getByDisplayValue("key_1")).toBeInTheDocument();
  });

  test("adds an http server with url and headers", async () => {
    const user = userEvent.setup();
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.type(screen.getByPlaceholderText("e.g. github"), "remote");
    fireEvent.change(screen.getByTestId("select"), {
      target: { value: "http" },
    });
    await user.type(
      screen.getByPlaceholderText("e.g. http://localhost:3000/sse"),
      "https://mcp.example/http",
    );
    await user.click(screen.getAllByText("Add")[1]!);
    const headerValueInput = screen
      .getAllByDisplayValue("")
      .find((element) => element.tagName === "INPUT");
    await user.type(headerValueInput!, "Bearer abc");
    await user.click(screen.getByText("Save"));

    expect(mockAddMCPServer).toHaveBeenCalledWith({
      name: "remote",
      serverConfig: expect.objectContaining({
        type: "http",
        command: undefined,
        args: [],
        url: "https://mcp.example/http",
        headers: { key: "Bearer abc" },
      }),
    });
  });

  test("does not submit add form while add mutation is pending", async () => {
    const user = userEvent.setup();
    mockAddPending = true;
    render(<ToolSettingsPage />);

    await user.click(screen.getByText("Add Server"));
    await user.type(screen.getByPlaceholderText("e.g. github"), "blocked");
    await user.click(screen.getByText("Loading..."));

    expect(mockAddMCPServer).not.toHaveBeenCalled();
  });

  test("does not submit edit form while update mutation is pending", async () => {
    const user = userEvent.setup();
    mockUpdatePending = true;
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Edit")[0]!);
    await user.click(screen.getByText("Loading..."));

    expect(mockUpdateMCPServer).not.toHaveBeenCalled();
  });

  test("does not delete while delete mutation is pending", async () => {
    const user = userEvent.setup();
    mockDeletePending = true;
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Delete")[0]!);
    await user.click(screen.getByText("Loading..."));

    expect(mockDeleteMCPServer).not.toHaveBeenCalled();
  });

  test("deletes a selected server", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Delete")[0]!);
    expect(screen.getByText("Delete server?")).toBeInTheDocument();
    expect(screen.getAllByText("code-runner").length).toBeGreaterThanOrEqual(2);
    await user.click(screen.getAllByText("Delete").at(-1)!);

    expect(mockDeleteMCPServer).toHaveBeenCalledWith({ name: "code-runner" });
    expect(toast.success).toHaveBeenCalledWith("Server deleted");
  });

  test("shows delete errors", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    mockDeleteMCPServer.mockRejectedValue(new Error("delete failed"));
    render(<ToolSettingsPage />);

    await user.click(screen.getAllByLabelText("Delete")[0]!);
    await user.click(screen.getAllByText("Delete").at(-1)!);

    expect(toast.error).toHaveBeenCalledWith("delete failed");
  });
});
