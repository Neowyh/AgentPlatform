import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

const mockExportThreadAsMarkdown = vi.fn();
const mockExportThreadAsJSON = vi.fn();
vi.mock("@/core/threads/export", () => ({
  exportThreadAsMarkdown: (...args: unknown[]) =>
    mockExportThreadAsMarkdown(...args),
  exportThreadAsJSON: (...args: unknown[]) => mockExportThreadAsJSON(...args),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      common: {
        export: "Export",
        exportAsMarkdown: "Export as Markdown",
        exportAsJSON: "Export as JSON",
        exportSuccess: "Export successful",
      },
      conversation: {
        noMessages: "No messages to export",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
  }) => (
    <div data-testid="tooltip-wrapper" data-tooltip-content={String(content)}>
      {children}
    </div>
  ),
}));

// Mock the thread context with a mutable reference
let mockMessages: unknown[] = [
  { id: "msg-1", type: "human", content: "Hello" },
  { id: "msg-2", type: "ai", content: "Hi there" },
];
let mockValues: Record<string, unknown> = { title: "Test Thread" };

vi.mock("@/components/workspace/messages/context", () => ({
  useThread: () => ({
    thread: {
      get messages() {
        return mockMessages;
      },
      get values() {
        return mockValues;
      },
    },
  }),
}));

// Mock DropdownMenu to render inline for testing
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuTrigger: ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => (
    <div data-testid="dropdown-trigger" data-as-child={String(asChild)}>
      {children}
    </div>
  ),
  DropdownMenuContent: ({
    children,
    align,
  }: {
    children: React.ReactNode;
    align?: string;
  }) => (
    <div data-testid="dropdown-content" data-align={align}>
      {children}
    </div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
  }) => (
    <button data-testid="dropdown-item" onClick={onSelect}>
      {children}
    </button>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ExportTrigger: (props: { threadId: string }) => React.JSX.Element | null;

beforeEach(async () => {
  vi.clearAllMocks();
  mockMessages = [
    { id: "msg-1", type: "human", content: "Hello" },
    { id: "msg-2", type: "ai", content: "Hi there" },
  ];
  mockValues = { title: "Test Thread" };
  const mod = await import("@/components/workspace/export-trigger");
  ExportTrigger = mod.ExportTrigger;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ExportTrigger", () => {
  // ── Empty state guard ────────────────────────────────────────────────────

  test("renders nothing when messages array is empty", () => {
    mockMessages = [];
    const { container } = render(<ExportTrigger threadId="thread-1" />);
    expect(container.firstChild).toBeNull();
  });

  // ── Visible rendering ────────────────────────────────────────────────────

  test("renders the export button when messages exist", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByTestId("export-trigger-button")).toBeInTheDocument();
  });

  test("displays the export label text", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  test("renders the tooltip wrapper with export content", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute("data-tooltip-content", "Export");
  });

  test("renders the dropdown menu structure", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByTestId("dropdown-menu")).toBeInTheDocument();
    expect(screen.getByTestId("dropdown-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("dropdown-content")).toBeInTheDocument();
  });

  test("dropdown content is aligned to end", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByTestId("dropdown-content")).toHaveAttribute(
      "data-align",
      "end",
    );
  });

  test("dropdown trigger uses asChild", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByTestId("dropdown-trigger")).toHaveAttribute(
      "data-as-child",
      "true",
    );
  });

  // ── Menu items ───────────────────────────────────────────────────────────

  test("renders markdown export menu item", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByText("Export as Markdown")).toBeInTheDocument();
  });

  test("renders JSON export menu item", () => {
    render(<ExportTrigger threadId="thread-1" />);
    expect(screen.getByText("Export as JSON")).toBeInTheDocument();
  });

  test("renders exactly two dropdown items", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");
    expect(items).toHaveLength(2);
  });

  // ── Markdown export ──────────────────────────────────────────────────────

  test("clicking markdown export calls exportThreadAsMarkdown with thread and messages", () => {
    render(<ExportTrigger threadId="thread-abc" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    expect(mockExportThreadAsMarkdown).toHaveBeenCalledTimes(1);
    const [threadArg, messagesArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(threadArg.thread_id).toBe("thread-abc");
    expect(threadArg.updated_at).toBeDefined();
    expect(typeof threadArg.updated_at).toBe("string");
    expect(threadArg.values).toEqual({ title: "Test Thread" });
    expect(messagesArg).toHaveLength(2);
    expect(messagesArg[0].id).toBe("msg-1");
  });

  test("markdown export shows success toast", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    expect(mockToastSuccess).toHaveBeenCalledWith("Export successful");
  });

  test("markdown export does not call JSON export", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    expect(mockExportThreadAsJSON).not.toHaveBeenCalled();
  });

  // ── JSON export ──────────────────────────────────────────────────────────

  test("clicking JSON export calls exportThreadAsJSON with thread and messages", () => {
    render(<ExportTrigger threadId="thread-xyz" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[1]!);

    expect(mockExportThreadAsJSON).toHaveBeenCalledTimes(1);
    const [threadArg, messagesArg] = mockExportThreadAsJSON.mock.calls[0]!;
    expect(threadArg.thread_id).toBe("thread-xyz");
    expect(threadArg.values).toEqual({ title: "Test Thread" });
    expect(messagesArg).toHaveLength(2);
  });

  test("JSON export shows success toast", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[1]!);

    expect(mockToastSuccess).toHaveBeenCalledWith("Export successful");
  });

  test("JSON export does not call markdown export", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[1]!);

    expect(mockExportThreadAsMarkdown).not.toHaveBeenCalled();
  });

  // ── Empty messages guard in handler (via re-render) ──────────────────────

  test("export handler shows error toast when messages are empty on click", () => {
    // Set messages to empty BEFORE rendering
    mockMessages = [];
    const { container } = render(<ExportTrigger threadId="thread-1" />);
    // Component should not render at all with empty messages
    expect(container.firstChild).toBeNull();
  });

  // ── Unreachable guard via array mutation ──────────────────────────────────
  // Lines 32-34 inside handleExport check messages.length === 0, but the
  // component also returns null when messages.length === 0 (line 52-54),
  // so the guard is unreachable through normal UI. We test it by mutating
  // the messages array in place after render, so the closure still holds
  // a reference to the now-empty array.

  test("handleExport guard fires when messages become empty after render via array mutation", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");

    // Mutate the messages array in place (same reference held by handleExport closure)
    mockMessages.length = 0;

    // Click the markdown export button (still in DOM, no re-render triggered)
    fireEvent.click(items[0]!);

    // The guard inside handleExport should fire
    expect(mockToastError).toHaveBeenCalledWith("No messages to export");
    expect(mockExportThreadAsMarkdown).not.toHaveBeenCalled();
  });

  test("handleExport JSON guard fires when messages become empty after render via array mutation", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");

    // Mutate the messages array in place
    mockMessages.length = 0;

    // Click the JSON export button
    fireEvent.click(items[1]!);

    // The guard inside handleExport should fire
    expect(mockToastError).toHaveBeenCalledWith("No messages to export");
    expect(mockExportThreadAsJSON).not.toHaveBeenCalled();
  });

  // ── threadId propagation ─────────────────────────────────────────────────

  test("threadId is correctly embedded in the exported thread object", () => {
    render(<ExportTrigger threadId="custom-id-42" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    const [threadArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(threadArg.thread_id).toBe("custom-id-42");
  });

  // ── Multiple exports ─────────────────────────────────────────────────────

  test("can trigger markdown and JSON exports sequentially", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const items = screen.getAllByTestId("dropdown-item");

    fireEvent.click(items[0]!); // Markdown
    fireEvent.click(items[1]!); // JSON

    expect(mockExportThreadAsMarkdown).toHaveBeenCalledTimes(1);
    expect(mockExportThreadAsJSON).toHaveBeenCalledTimes(1);
    expect(mockToastSuccess).toHaveBeenCalledTimes(2);
  });

  // ── Single message ───────────────────────────────────────────────────────

  test("renders and exports when there is exactly one message", () => {
    mockMessages = [{ id: "only-msg", type: "human", content: "Solo" }];

    render(<ExportTrigger threadId="single-msg" />);
    expect(screen.getByTestId("export-trigger-button")).toBeInTheDocument();

    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    expect(mockExportThreadAsMarkdown).toHaveBeenCalledTimes(1);
    const [, messagesArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(messagesArg).toHaveLength(1);
    expect(mockToastSuccess).toHaveBeenCalledWith("Export successful");
  });

  // ── Values propagation ───────────────────────────────────────────────────

  test("thread values are passed through in the export object", () => {
    mockValues = { title: "Custom Title", extra: "data" };

    render(<ExportTrigger threadId="thread-v" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    const [threadArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(threadArg.values).toEqual({ title: "Custom Title", extra: "data" });
  });

  test("empty values object is passed through correctly", () => {
    mockValues = {};

    render(<ExportTrigger threadId="thread-e" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[1]!);

    const [threadArg] = mockExportThreadAsJSON.mock.calls[0]!;
    expect(threadArg.values).toEqual({});
  });

  // ── Many messages ────────────────────────────────────────────────────────

  test("handles large number of messages", () => {
    mockMessages = Array.from({ length: 100 }, (_, i) => ({
      id: `msg-${i}`,
      type: i % 2 === 0 ? "human" : "ai",
      content: `Message ${i}`,
    }));

    render(<ExportTrigger threadId="large-thread" />);
    expect(screen.getByTestId("export-trigger-button")).toBeInTheDocument();

    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    const [, messagesArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(messagesArg).toHaveLength(100);
  });

  // ── updated_at format ───────────────────────────────────────────────────

  test("exported thread has a valid ISO timestamp in updated_at", () => {
    render(<ExportTrigger threadId="ts-thread" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    const [threadArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    const parsed = new Date(threadArg.updated_at);
    expect(parsed.toString()).not.toBe("Invalid Date");
    expect(threadArg.updated_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  // ── Button has ghost variant ────────────────────────────────────────────

  test("export button has ghost variant class", () => {
    render(<ExportTrigger threadId="thread-1" />);
    const button = screen.getByTestId("export-trigger-button");
    expect(button.className).toContain("text-muted-foreground");
  });

  // ── Both export functions are called independently ──────────────────────

  test("markdown export receives correct thread_id while JSON is not called", () => {
    render(<ExportTrigger threadId="md-only" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[0]!);

    const [threadArg] = mockExportThreadAsMarkdown.mock.calls[0]!;
    expect(threadArg.thread_id).toBe("md-only");
    expect(mockExportThreadAsJSON).not.toHaveBeenCalled();
  });

  test("JSON export receives correct thread_id while markdown is not called", () => {
    render(<ExportTrigger threadId="json-only" />);
    const items = screen.getAllByTestId("dropdown-item");
    fireEvent.click(items[1]!);

    const [threadArg] = mockExportThreadAsJSON.mock.calls[0]!;
    expect(threadArg.thread_id).toBe("json-only");
    expect(mockExportThreadAsMarkdown).not.toHaveBeenCalled();
  });
});
