import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

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
  useAuth: () => ({ user: null }),
}));

vi.mock("@/components/workspace/settings/tool-settings-page", () => ({
  ToolSettingsPage: () => <div data-testid="tool-settings-page" />,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ConnectorList: typeof import("@/components/workspace/resources/connector-list").ConnectorList;

beforeEach(async () => {
  vi.clearAllMocks();
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
});
