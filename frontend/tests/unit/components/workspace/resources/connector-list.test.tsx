import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { auth } = vi.hoisted(() => ({ auth: { role: "user" } }));

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockConfig = {
  mcp_servers: {
    "server-1": { description: "Server 1 description", enabled: true },
    "server-2": { description: "Server 2 description", enabled: false },
  },
};

vi.mock("@/core/mcp/hooks", () => ({
  useMCPConfig: () => ({
    config: mockConfig,
    isLoading: false,
  }),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { system_role: auth.role } }),
}));

vi.mock("@/components/workspace/settings/tool-settings-page", () => ({
  ToolSettingsPage: () => <div data-testid="tool-settings-page" />,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ConnectorList: typeof import("@/components/workspace/resources/connector-list").ConnectorList;

beforeEach(async () => {
  vi.clearAllMocks();
  auth.role = "user";
  const mod = await import("@/components/workspace/resources/connector-list");
  ConnectorList = mod.ConnectorList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ConnectorList", () => {
  test("displays list of MCP connectors", () => {
    render(<ConnectorList />);
    expect(screen.getByText("server-1")).toBeInTheDocument();
    expect(screen.getByText("server-2")).toBeInTheDocument();
  });

  test("displays connector descriptions", () => {
    render(<ConnectorList />);
    expect(screen.getByText("Server 1 description")).toBeInTheDocument();
    expect(screen.getByText("Server 2 description")).toBeInTheDocument();
  });

  test("offers enabled connectors for a new conversation", () => {
    render(<ConnectorList />);
    const links = screen.getAllByRole("link", {
      name: "Use in new conversation",
    });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute(
      "href",
      "/workspace/chats/new?connector=server-1",
    );
  });

  test("only super administrators see MCP configuration controls", () => {
    auth.role = "department_admin";
    const { rerender } = render(<ConnectorList />);
    expect(screen.queryByTestId("tool-settings-page")).not.toBeInTheDocument();

    auth.role = "super_admin";
    rerender(<ConnectorList />);
    expect(screen.getByTestId("tool-settings-page")).toBeInTheDocument();
  });
});
