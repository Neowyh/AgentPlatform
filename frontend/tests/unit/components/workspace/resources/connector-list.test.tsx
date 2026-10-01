import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { auth, mockConfig } = vi.hoisted(() => ({
  auth: { role: "user" },
  mockConfig: {
    mcp_servers: {
      "server-1": { description: "Server 1 description", enabled: true },
      "server-2": { description: "Server 2 description", enabled: false },
    },
  } as {
    mcp_servers: Record<string, { description: string; enabled: boolean }>;
  },
}));

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/mcp/hooks", () => ({
  useMCPConfig: () => ({
    config: mockConfig,
    isLoading: false,
  }),
}));

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { system_role: auth.role } }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ConnectorList: typeof import("@/components/workspace/resources/connector-list").ConnectorList;

beforeEach(async () => {
  vi.clearAllMocks();
  auth.role = "user";
  mockConfig.mcp_servers = {
    "server-1": { description: "Server 1 description", enabled: true },
    "server-2": { description: "Server 2 description", enabled: false },
  };
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

  test("hides the empty-state hint from super administrators", () => {
    // 合并形态：MCP 配置控件收敛进连接器 tab 的 MCPPluginManager
    //（有独立 rstest 覆盖），ConnectorList 自身保留的角色门控是
    // 空态提示只面向普通用户——管理员空态交给上方管理面板。
    mockConfig.mcp_servers = {};
    auth.role = "department_admin";
    const { rerender } = render(<ConnectorList />);
    expect(screen.getByText("No connectors found")).toBeInTheDocument();

    auth.role = "super_admin";
    rerender(<ConnectorList />);
    expect(screen.queryByText("No connectors found")).not.toBeInTheDocument();
  });
});
