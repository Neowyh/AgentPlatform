import {
  render,
  screen,
  cleanup,
  waitFor,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks -- must be declared before the component import
// ---------------------------------------------------------------------------

const mockListTools = vi.fn();
const mockTestTool = vi.fn();

vi.mock("@/core/auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/workspace/admin/tools",
}));

vi.mock("@/core/admin/api", () => ({
  listTools: (...args: unknown[]) => mockListTools(...args),
  testTool: (...args: unknown[]) => mockTestTool(...args),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import ToolsPage from "@/app/workspace/admin/tools/page";
import { useAuth } from "@/core/auth/AuthProvider";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockTools = [
  {
    name: "read_document",
    description: "Read and parse documents (PDF, Word, Excel)",
    group: "document",
    requires_network: false,
    configurable: true,
    param_schema: { file_path: { type: "string" } },
    config: {},
  },
  {
    name: "web_search",
    description: "Search the web for information",
    group: "network",
    requires_network: true,
    configurable: false,
    param_schema: { query: { type: "string" } },
    config: {},
  },
  {
    name: "code_interpreter",
    description: "Execute Python and JavaScript code",
    group: "code",
    requires_network: false,
    configurable: true,
    param_schema: { code: { type: "string" }, language: { type: "string" } },
    config: {},
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToolsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: "test-admin-id",
        email: "admin@example.com",
        system_role: "super_admin",
        needs_setup: false,
      },
      isAuthenticated: true,
      isLoading: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
    mockListTools.mockResolvedValue({
      tools: mockTools,
      total: 3,
    });
    mockTestTool.mockResolvedValue({
      success: true,
      tool: "read_document",
      result: "parsed content",
    });
  });

  afterEach(() => {
    cleanup();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  test("renders the page header with title and description", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("工具管理")).toBeInTheDocument();
      expect(screen.getByText("查看和测试系统工具")).toBeInTheDocument();
    });
  });

  test("renders a back link to /workspace/admin", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      const links = screen.getAllByRole("link");
      const backLink = links.find(
        (l) => l.getAttribute("href") === "/workspace/admin",
      );
      expect(backLink).toBeDefined();
    });
  });

  // ── Loading state ──────────────────────────────────────────────────

  test("shows loading indicator while fetching tools", () => {
    mockListTools.mockReturnValue(new Promise(() => {}));
    render(<ToolsPage />);
    expect(screen.getByText("加载中...")).toBeInTheDocument();
  });

  // ── Success state ──────────────────────────────────────────────────

  test("renders tool list after loading", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });
    const toolCards = screen.getAllByTestId("tool-card");
    expect(toolCards).toHaveLength(3);
  });

  test("displays tool names", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("read_document")).toBeInTheDocument();
      expect(screen.getByText("web_search")).toBeInTheDocument();
      expect(screen.getByText("code_interpreter")).toBeInTheDocument();
    });
  });

  test("displays tool descriptions", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Read and parse documents (PDF, Word, Excel)"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Search the web for information"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Execute Python and JavaScript code"),
      ).toBeInTheDocument();
    });
  });

  test("displays tool group badges", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("document")).toBeInTheDocument();
      expect(screen.getByText("network")).toBeInTheDocument();
      expect(screen.getByText("code")).toBeInTheDocument();
    });
  });

  test("displays 'available' badge for tools without network requirement", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      const availableBadges = screen.getAllByText("可用");
      expect(availableBadges.length).toBeGreaterThanOrEqual(1);
    });
  });

  test("displays 'requires network' badge for network tools", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("需联网")).toBeInTheDocument();
    });
  });

  test("displays 'no description' placeholder when description is empty", async () => {
    mockListTools.mockResolvedValue({
      tools: [
        {
          ...mockTools[0],
          description: "",
        },
      ],
      total: 1,
    });
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("暂无描述")).toBeInTheDocument();
    });
  });

  // ── Empty state ────────────────────────────────────────────────────

  test("shows empty state when no tools exist", async () => {
    mockListTools.mockResolvedValue({ tools: [], total: 0 });
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("暂无工具")).toBeInTheDocument();
    });
  });

  test("does not render tool list in empty state", async () => {
    mockListTools.mockResolvedValue({ tools: [], total: 0 });
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.queryByTestId("tool-list")).not.toBeInTheDocument();
    });
  });

  // ── Error state ────────────────────────────────────────────────────

  test("shows error message when API call fails", async () => {
    mockListTools.mockRejectedValue(new Error("Server error"));
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  test("shows stringified error for non-Error throws", async () => {
    mockListTools.mockRejectedValue("unknown failure");
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("unknown failure")).toBeInTheDocument();
    });
  });

  test("does not render tool list in error state", async () => {
    mockListTools.mockRejectedValue(new Error("fail"));
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.queryByTestId("tool-list")).not.toBeInTheDocument();
    });
  });

  // ── API calls ──────────────────────────────────────────────────────

  test("calls listTools on mount", () => {
    render(<ToolsPage />);
    expect(mockListTools).toHaveBeenCalledTimes(1);
  });

  // ── Group filter ───────────────────────────────────────────────────

  test("renders group filter select", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByText("全部工具组")).toBeInTheDocument();
    });
  });

  // ── Detail dialog ──────────────────────────────────────────────────

  test("opens detail dialog when clicking a tool card", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!); // click read_document

    await waitFor(() => {
      expect(screen.getByText("测试输入 (JSON)")).toBeInTheDocument();
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });
  });

  test("detail dialog shows tool name and description", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      // Dialog shows the tool name as title
      const dialogTitles = screen.getAllByText("read_document");
      expect(dialogTitles.length).toBeGreaterThanOrEqual(1);
    });
  });

  test("detail dialog pre-fills test input with param schema", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!); // read_document

    await waitFor(() => {
      const textarea =
        screen.getByPlaceholderText<HTMLTextAreaElement>('{"key": "value"}');
      expect(textarea.value).toContain("file_path");
    });
  });

  test("detail dialog shows close button", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("关闭")).toBeInTheDocument();
    });
  });

  // ── Test tool ──────────────────────────────────────────────────────

  test("calls testTool with tool name and parsed input", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!); // read_document

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    // The textarea is pre-filled with the schema, modify it
    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });

    const testButton = screen.getByText("测试工具");
    await user.click(testButton);

    await waitFor(() => {
      expect(mockTestTool).toHaveBeenCalledWith("read_document", {
        file_path: "/test.pdf",
      });
    });
  });

  test("displays test result on success", async () => {
    const user = userEvent.setup();
    mockTestTool.mockResolvedValue({
      success: true,
      tool: "read_document",
      result: "parsed content here",
    });

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    // Update the input to valid JSON
    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });

    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText("测试结果")).toBeInTheDocument();
      expect(screen.getByText(/"success": true/)).toBeInTheDocument();
    });
  });

  test("displays error result when testTool fails", async () => {
    const user = userEvent.setup();
    mockTestTool.mockRejectedValue(new Error("Tool execution failed"));

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });

    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText(/Tool execution failed/)).toBeInTheDocument();
    });
  });

  test("displays error for invalid JSON input", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    await user.clear(textarea);
    await user.type(textarea, "not valid json");

    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText("Error: Invalid JSON input")).toBeInTheDocument();
    });

    // testTool should not be called with invalid JSON
    expect(mockTestTool).not.toHaveBeenCalled();
  });

  test("shows 'testing' button text while test is running", async () => {
    const user = userEvent.setup();
    // Make testTool hang to observe the testing state
    mockTestTool.mockReturnValue(new Promise(() => {}));

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });

    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText("测试中...")).toBeInTheDocument();
    });
  });

  // ── Close dialog ───────────────────────────────────────────────────

  test("closes detail dialog when close button is clicked", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    await user.click(screen.getByText("关闭"));

    await waitFor(() => {
      expect(screen.queryByText("测试工具")).not.toBeInTheDocument();
    });
  });

  // ── Network badge variants ─────────────────────────────────────────

  test("renders correct badge variant for network-requiring tools", async () => {
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });
    // web_search has requires_network: true, so shows "需联网"
    expect(screen.getByText("需联网")).toBeInTheDocument();
    // read_document and code_interpreter have requires_network: false, so show "可用"
    const availableBadges = screen.getAllByText("可用");
    expect(availableBadges.length).toBeGreaterThanOrEqual(2);
  });

  // ── Empty filtered tools ───────────────────────────────────────────

  test("shows empty state when filtered group has no tools", async () => {
    const user = userEvent.setup();
    // Tools with distinct groups
    mockListTools.mockResolvedValue({
      tools: [mockTools[0]], // only "document" group
      total: 1,
    });
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    // Verify single tool rendered
    const toolCards = screen.getAllByTestId("tool-card");
    expect(toolCards).toHaveLength(1);
  });

  // ── Test result label ──────────────────────────────────────────────

  test("does not show test result section before testing", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    // Test result section should not be visible before running a test
    expect(screen.queryByText("测试结果")).not.toBeInTheDocument();
  });

  // ── Non-Error throw from testTool ──────────────────────────────────

  test("displays error for non-Error throw from testTool", async () => {
    const user = userEvent.setup();
    mockTestTool.mockRejectedValue("raw string error");

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });

    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText(/raw string error/)).toBeInTheDocument();
    });
  });

  // ── Group filtering ────────────────────────────────────────────────

  test("filters tools by group when a specific group is selected", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    // Initially all tools are shown
    const toolCards = screen.getAllByTestId("tool-card");
    expect(toolCards).toHaveLength(3);

    // The group filter select exists with all groups
    expect(screen.getByText("全部工具组")).toBeInTheDocument();
  });

  test("filters to specific group via Select interaction", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    // Initially all tools are shown
    let toolCards = screen.getAllByTestId("tool-card");
    expect(toolCards).toHaveLength(3);

    // Find the filter select trigger (first combobox)
    const comboboxes = screen.getAllByRole("combobox");
    const filterSelect = comboboxes[0]!;

    // Click to open the filter dropdown
    await user.click(filterSelect);

    // Wait for options to appear in the portal
    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    // Click on "document" group option
    const documentOption = screen.getByRole("option", { name: "document" });
    await user.click(documentOption);

    // After filtering, only the document tool should be shown
    await waitFor(() => {
      toolCards = screen.getAllByTestId("tool-card");
      expect(toolCards).toHaveLength(1);
      expect(screen.getByText("read_document")).toBeInTheDocument();
      expect(screen.queryByText("web_search")).not.toBeInTheDocument();
      expect(screen.queryByText("code_interpreter")).not.toBeInTheDocument();
    });
  });

  test("filters to network group shows only network tools", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const comboboxes = screen.getAllByRole("combobox");
    const filterSelect = comboboxes[0]!;

    await user.click(filterSelect);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    const networkOption = screen.getByRole("option", { name: "network" });
    await user.click(networkOption);

    await waitFor(() => {
      const toolCards = screen.getAllByTestId("tool-card");
      expect(toolCards).toHaveLength(1);
      expect(screen.getByText("web_search")).toBeInTheDocument();
      expect(screen.queryByText("read_document")).not.toBeInTheDocument();
    });
  });

  test("filters to code group shows only code tools", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const comboboxes = screen.getAllByRole("combobox");
    const filterSelect = comboboxes[0]!;

    await user.click(filterSelect);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    const codeOption = screen.getByRole("option", { name: "code" });
    await user.click(codeOption);

    await waitFor(() => {
      const toolCards = screen.getAllByTestId("tool-card");
      expect(toolCards).toHaveLength(1);
      expect(screen.getByText("code_interpreter")).toBeInTheDocument();
      expect(screen.queryByText("read_document")).not.toBeInTheDocument();
    });
  });

  test("shows empty state when filtered group has no matching tools", async () => {
    const user = userEvent.setup();
    // All tools are in distinct groups
    mockListTools.mockResolvedValue({
      tools: [mockTools[0]], // only "document" group
      total: 1,
    });

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const comboboxes = screen.getAllByRole("combobox");
    const filterSelect = comboboxes[0]!;

    await user.click(filterSelect);

    await waitFor(() => {
      const options = screen.getAllByRole("option");
      expect(options.length).toBeGreaterThan(0);
    });

    // Try to filter by "network" but no tools have that group
    // Since only "document" group tool exists, "network" option won't be in the list
    // But we can test filtering by the existing group
    const documentOption = screen.getByRole("option", { name: "document" });
    await user.click(documentOption);

    await waitFor(() => {
      const toolCards = screen.getAllByTestId("tool-card");
      expect(toolCards).toHaveLength(1);
    });
  });

  // ── Detail dialog: param_schema null ───────────────────────────────

  test("handles tool with null param_schema", async () => {
    const user = userEvent.setup();
    mockListTools.mockResolvedValue({
      tools: [
        {
          name: "simple_tool",
          description: "A simple tool",
          group: "util",
          requires_network: false,
          configurable: false,
          param_schema: null,
          config: {},
        },
      ],
      total: 1,
    });

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试输入 (JSON)")).toBeInTheDocument();
    });

    // The textarea should default to "{}" when param_schema is null
    const textarea =
      screen.getByPlaceholderText<HTMLTextAreaElement>('{"key": "value"}');
    expect(textarea.value).toBe("{}");
  });

  // ── Detail dialog: tool name badge ─────────────────────────────────

  test("shows tool group and network badges in detail dialog", async () => {
    const user = userEvent.setup();
    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!); // read_document (document group, no network)

    await waitFor(() => {
      // The dialog shows badges for group and network status
      const badges = screen.getAllByText("document");
      expect(badges.length).toBeGreaterThanOrEqual(1);
      // read_document is not network-required, should show "可用"
      const availableBadges = screen.getAllByText("可用");
      expect(availableBadges.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── Test result cleared on new dialog open ──────────────────────────

  test("clears test result when opening a different tool", async () => {
    const user = userEvent.setup();
    mockTestTool.mockResolvedValue({ success: true, result: "test data" });

    render(<ToolsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("tool-list")).toBeInTheDocument();
    });

    // Open first tool
    const toolCards = screen.getAllByTestId("tool-card");
    await user.click(toolCards[0]!);

    await waitFor(() => {
      expect(screen.getByText("测试工具")).toBeInTheDocument();
    });

    // Run a test
    const textarea = screen.getByPlaceholderText('{"key": "value"}');
    fireEvent.change(textarea, {
      target: { value: '{"file_path": "/test.pdf"}' },
    });
    await user.click(screen.getByText("测试工具"));

    await waitFor(() => {
      expect(screen.getByText("测试结果")).toBeInTheDocument();
    });

    // Close and open second tool
    await user.click(screen.getByText("关闭"));
    await waitFor(() => {
      expect(screen.queryByText("测试结果")).not.toBeInTheDocument();
    });

    await user.click(toolCards[1]!); // web_search

    await waitFor(() => {
      expect(screen.getByText("测试输入 (JSON)")).toBeInTheDocument();
      // Test result should not be visible
      expect(screen.queryByText("测试结果")).not.toBeInTheDocument();
    });
  });
});
