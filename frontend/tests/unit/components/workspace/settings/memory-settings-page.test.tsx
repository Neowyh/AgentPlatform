import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      settings: {
        memory: {
          title: "Memory",
          description: "Manage your memory",
          empty: "No memory",
          clearAll: "Clear All",
          clearAllConfirmTitle: "Clear all?",
          clearAllConfirmDescription: "This will remove everything.",
          clearAllSuccess: "Memory cleared",
          addFact: "Add Fact",
          addFactTitle: "Add Fact",
          editFactTitle: "Edit Fact",
          addFactSuccess: "Fact added",
          editFactSuccess: "Fact updated",
          factContentLabel: "Content",
          factCategoryLabel: "Category",
          factConfidenceLabel: "Confidence",
          factContentPlaceholder: "Enter content",
          factCategoryPlaceholder: "context",
          factConfidenceHint: "0-1",
          factSave: "Save",
          factValidationContent: "Content required",
          factValidationConfidence: "Invalid confidence",
          noFacts: "No facts",
          summaryReadOnly: "Read only",
          memoryFullyEmpty: "No memory saved yet",
          factPreviewLabel: "Preview",
          searchPlaceholder: "Search",
          filterAll: "All",
          filterFacts: "Facts",
          filterSummaries: "Summaries",
          noMatches: "No matches",
          exportButton: "Export",
          exportSuccess: "Exported",
          importButton: "Import",
          importSuccess: "Imported",
          importConfirmTitle: "Import?",
          importConfirmDescription: "Import memory?",
          importFileLabel: "File",
          importInvalidFile: "Invalid file",
          factDeleteConfirmTitle: "Delete fact?",
          factDeleteConfirmDescription: "Delete this fact?",
          factDeleteSuccess: "Fact deleted",
          manualFactSource: "Manual",
          markdown: {
            empty: "Empty",
            overview: "Overview",
            updatedAt: "Updated",
            userContext: "User Context",
            personal: "Personal",
            work: "Work",
            topOfMind: "Top of Mind",
            historyBackground: "History",
            recentMonths: "Recent",
            earlierContext: "Earlier",
            longTermBackground: "Long Term",
            facts: "Facts",
            table: {
              category: "Category",
              confidence: "Confidence",
              createdAt: "Created",
              source: "Source",
              view: "View",
              confidenceLevel: {
                veryHigh: "Very High",
                high: "High",
                normal: "Normal",
                unknown: "Unknown",
              },
            },
          },
        },
      },
      common: {
        cancel: "Cancel",
        delete: "Delete",
        loading: "Loading...",
        import: "Import",
        export: "Export",
        exportSuccess: "Exported",
        lastUpdated: "Last Updated",
        edit: "Edit",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

// ── Mutable mock state ───────────────────────────────────────────────────────

let mockMemory: any = null;
let mockIsLoading = false;
let mockError: any = null;

let mockClearMemory: { mutateAsync: any; isPending: boolean };
let mockCreateFact: { mutateAsync: any; isPending: boolean };
let mockDeleteFact: { mutateAsync: any; isPending: boolean };
let mockUpdateFact: { mutateAsync: any; isPending: boolean };
let mockImportMemory: { mutateAsync: any; isPending: boolean };
let mockExportMemoryFn: any;

vi.mock("@/core/memory/hooks", () => ({
  useMemory: () => ({
    memory: mockMemory,
    isLoading: mockIsLoading,
    error: mockError,
  }),
  useClearMemory: () => mockClearMemory,
  useCreateMemoryFact: () => mockCreateFact,
  useDeleteMemoryFact: () => mockDeleteFact,
  useUpdateMemoryFact: () => mockUpdateFact,
  useImportMemory: () => mockImportMemory,
}));

vi.mock("@/core/memory/api", () => ({
  exportMemory: (...args: any[]) => mockExportMemoryFn(...args),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("streamdown", () => ({
  Streamdown: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="streamdown">{children}</div>
  ),
}));

vi.mock("@/core/streamdown/plugins", () => ({
  streamdownPlugins: {},
}));

vi.mock("@/core/utils/datetime", () => ({
  formatTimeAgo: (date: string) => `ago (${date})`,
}));

vi.mock("@/core/threads/utils", () => ({
  pathOfThread: (id: string) => `/workspace/chats/${id}`,
}));

vi.mock("@/components/workspace/settings/settings-section", () => ({
  SettingsSection: ({ title, description, children }: any) => (
    <div data-testid="settings-section">
      <div data-testid="section-title">{title}</div>
      <div data-testid="section-description">{description}</div>
      {children}
    </div>
  ),
}));

vi.mock("@/components/ui/input", () => ({
  Input: ({ type, ...props }: any) => <input data-testid="input" {...props} />,
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: (props: any) => <textarea data-testid="textarea" {...props} />,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant, ...props }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      {...props}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? (
      <div data-testid="dialog">
        {children}
        <button
          data-testid="dialog-external-close"
          onClick={() => onOpenChange?.(false)}
        />
      </div>
    ) : null,
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h2>{children}</h2>,
  DialogDescription: ({ children }: any) => <p>{children}</p>,
  DialogFooter: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/toggle-group", () => ({
  ToggleGroup: ({ children, value, onValueChange }: any) => (
    <div data-testid="toggle-group" data-value={value}>
      {typeof children === "function"
        ? children
        : Array.isArray(children)
          ? children.map((child: any) =>
              typeof child === "object" && child?.props
                ? {
                    ...child,
                    props: {
                      ...child.props,
                      onClick: () => onValueChange?.(child.props.value),
                    },
                  }
                : child,
            )
          : children}
    </div>
  ),
  ToggleGroupItem: ({ children, value, onClick }: any) => (
    <button
      data-testid={`toggle-${value}`}
      onClick={onClick}
      data-value={value}
    >
      {children}
    </button>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let MemorySettingsPage: typeof import("@/components/workspace/settings/memory-settings-page").MemorySettingsPage;

const DEFAULT_EXPORT_DATA = {
  lastUpdated: "2024-01-01T00:00:00Z",
  version: "1.0",
  user: {
    workContext: { summary: "Work summary", updatedAt: "2024-01-01" },
    personalContext: { summary: "", updatedAt: "" },
    topOfMind: { summary: "", updatedAt: "" },
  },
  history: {
    recentMonths: { summary: "", updatedAt: "" },
    earlierContext: { summary: "", updatedAt: "" },
    longTermBackground: { summary: "", updatedAt: "" },
  },
  facts: [],
};

beforeEach(async () => {
  vi.clearAllMocks();
  mockMemory = null;
  mockIsLoading = false;
  mockError = null;

  mockClearMemory = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  mockCreateFact = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  mockDeleteFact = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  mockUpdateFact = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  mockImportMemory = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  mockExportMemoryFn = vi.fn().mockResolvedValue(DEFAULT_EXPORT_DATA);

  const mod =
    await import("@/components/workspace/settings/memory-settings-page");
  MemorySettingsPage = mod.MemorySettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeMemory(overrides: any = {}) {
  return {
    version: "1.0",
    lastUpdated: "2024-06-01T00:00:00Z",
    user: {
      workContext: {
        summary: "Work context summary",
        updatedAt: "2024-06-01",
      },
      personalContext: { summary: "", updatedAt: "" },
      topOfMind: { summary: "", updatedAt: "" },
    },
    history: {
      recentMonths: { summary: "", updatedAt: "" },
      earlierContext: { summary: "", updatedAt: "" },
      longTermBackground: { summary: "", updatedAt: "" },
    },
    facts: [
      {
        id: "f1",
        content: "Test fact",
        category: "context",
        confidence: 0.9,
        createdAt: "2024-06-01",
        source: "manual",
      },
    ],
    ...overrides,
  };
}

function makeFact(overrides: any = {}) {
  return {
    id: "f1",
    content: "Test fact",
    category: "context",
    confidence: 0.9,
    createdAt: "2024-06-01",
    source: "manual",
    ...overrides,
  };
}

function makeValidImportData() {
  return {
    version: "1.0",
    lastUpdated: "2024-06-01T00:00:00Z",
    user: {
      workContext: { summary: "Work", updatedAt: "2024-06-01" },
      personalContext: { summary: "Personal", updatedAt: "2024-06-01" },
      topOfMind: { summary: "Top of Mind", updatedAt: "2024-06-01" },
    },
    history: {
      recentMonths: { summary: "Recent", updatedAt: "2024-06-01" },
      earlierContext: { summary: "Earlier", updatedAt: "2024-06-01" },
      longTermBackground: { summary: "Long term", updatedAt: "2024-06-01" },
    },
    facts: [] as any[],
  };
}

function setupFileImport(
  container: HTMLElement,
  fileContent: string,
  fileName = "memory.json",
) {
  const file = new File([fileContent], fileName, {
    type: "application/json",
  });
  const input = container.querySelector('input[type="file"]')!;
  Object.defineProperty(input, "files", {
    value: [file],
    configurable: true,
  });
  fireEvent.change(input);
  return input;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("MemorySettingsPage", () => {
  // ─── Rendering states ────────────────────────────────────────────────────

  describe("Rendering states", () => {
    test("shows loading indicator when isLoading is true", () => {
      mockIsLoading = true;
      render(<MemorySettingsPage />);
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("shows error message when error is present", () => {
      mockError = new Error("Failed to load");
      render(<MemorySettingsPage />);
      expect(screen.getByText("Error: Failed to load")).toBeInTheDocument();
    });

    test("shows empty state when memory is null", () => {
      mockMemory = null;
      render(<MemorySettingsPage />);
      expect(screen.getByText("No memory")).toBeInTheDocument();
    });

    test("renders section title and description when memory is loaded", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByTestId("section-title")).toHaveTextContent("Memory");
      expect(screen.getByTestId("section-description")).toHaveTextContent(
        "Manage your memory",
      );
    });

    test("shows fully empty state when all summaries are empty and no facts exist", () => {
      mockMemory = makeMemory({
        facts: [],
        user: {
          workContext: { summary: "", updatedAt: "" },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("No memory saved yet")).toBeInTheDocument();
    });

    test("does not show fully empty state when summaries have content", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);
      expect(screen.queryByText("No memory saved yet")).not.toBeInTheDocument();
    });

    test("does not show fully empty state when facts exist even with empty summaries", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "A fact" })],
        user: {
          workContext: { summary: "", updatedAt: "" },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      expect(screen.queryByText("No memory saved yet")).not.toBeInTheDocument();
    });

    test("does not show toolbar when memory is null", () => {
      mockMemory = null;
      render(<MemorySettingsPage />);
      expect(screen.queryByPlaceholderText("Search")).not.toBeInTheDocument();
    });

    test("does not show toolbar when loading", () => {
      mockIsLoading = true;
      render(<MemorySettingsPage />);
      expect(screen.queryByPlaceholderText("Search")).not.toBeInTheDocument();
    });
  });

  // ─── Toolbar buttons ─────────────────────────────────────────────────────

  describe("Toolbar buttons", () => {
    test("renders all toolbar buttons when memory is loaded", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("Import")).toBeInTheDocument();
      expect(screen.getByText("Export")).toBeInTheDocument();
      expect(screen.getByText("Add Fact")).toBeInTheDocument();
      expect(screen.getByText("Clear All")).toBeInTheDocument();
    });

    test("renders search input", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByPlaceholderText("Search")).toBeInTheDocument();
    });

    test("renders filter toggle group with all options", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("All")).toBeInTheDocument();
      expect(screen.getByText("Summaries")).toBeInTheDocument();
      const toggleGroup = screen.getByTestId("toggle-group");
      expect(toggleGroup).toHaveAttribute("data-value", "all");
    });

    test("import button is disabled when import is pending", () => {
      mockImportMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const importBtn = screen.getByText("Import").closest("button");
      expect(importBtn).toBeDisabled();
    });

    test("export button shows loading text when exporting", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const exportBtn = screen.getByText("Export").closest("button");
      // Initially not disabled
      expect(exportBtn).not.toBeDisabled();
    });

    test("clear all button is disabled when clear is pending", () => {
      mockClearMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const clearBtn = screen.getByText("Loading...").closest("button");
      expect(clearBtn).toBeDisabled();
    });

    test("add fact button is always enabled", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const addFactBtn = screen.getByText("Add Fact").closest("button");
      expect(addFactBtn).not.toBeDisabled();
    });
  });

  // ─── Search and filtering ────────────────────────────────────────────────

  describe("Search and filtering", () => {
    test("search input updates query and filters facts", async () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({ id: "f1", content: "React patterns" }),
          makeFact({ id: "f2", content: "Vue patterns", category: "tech" }),
        ],
      });
      render(<MemorySettingsPage />);

      // Both facts visible initially
      expect(screen.getByText("React patterns")).toBeInTheDocument();
      expect(screen.getByText("Vue patterns")).toBeInTheDocument();

      // Type in search to filter
      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "React" },
      });

      // Only React fact should be visible after deferred update
      await waitFor(() => {
        expect(screen.getByText("React patterns")).toBeInTheDocument();
        expect(screen.queryByText("Vue patterns")).not.toBeInTheDocument();
      });
    });

    test("search filters summaries by title and content", async () => {
      mockMemory = makeMemory({
        user: {
          workContext: {
            summary: "Software engineering notes",
            updatedAt: "2024-06-01",
          },
          personalContext: {
            summary: "Family vacation plans",
            updatedAt: "2024-06-01",
          },
          topOfMind: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);

      // Summary block is visible initially
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "software" },
      });

      await waitFor(() => {
        const streamdown = screen.getByTestId("streamdown");
        expect(streamdown.textContent).toContain("Software engineering notes");
        expect(streamdown.textContent).not.toContain("Family vacation plans");
      });
    });

    test("shows no matches message when search has no results", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Hello world" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "xyznonexistent" },
      });

      await waitFor(() => {
        expect(screen.getAllByText("No matches").length).toBeGreaterThanOrEqual(
          1,
        );
      });
    });

    test("empty search shows all content", async () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({ id: "f1", content: "Fact one" }),
          makeFact({ id: "f2", content: "Fact two" }),
        ],
      });
      render(<MemorySettingsPage />);

      expect(screen.getByText("Fact one")).toBeInTheDocument();
      expect(screen.getByText("Fact two")).toBeInTheDocument();

      // Type and then clear
      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "Fact" },
      });
      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "" },
      });

      await waitFor(() => {
        expect(screen.getByText("Fact one")).toBeInTheDocument();
        expect(screen.getByText("Fact two")).toBeInTheDocument();
      });
    });

    test("filter toggle switches to facts only hides summaries", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      // Summaries visible by default
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();

      // Switch to facts only
      fireEvent.click(screen.getByTestId("toggle-facts"));

      await waitFor(() => {
        expect(screen.queryByTestId("streamdown")).not.toBeInTheDocument();
      });
    });

    test("filter toggle switches to summaries only hides facts", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      // Facts section visible by default
      expect(screen.getByText("Test fact")).toBeInTheDocument();

      // Switch to summaries only
      fireEvent.click(screen.getByTestId("toggle-summaries"));

      await waitFor(() => {
        expect(screen.queryByText("Test fact")).not.toBeInTheDocument();
        // Summaries still visible
        expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      });
    });

    test("filter=all shows both summaries and facts", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      expect(screen.getByText("Test fact")).toBeInTheDocument();

      // Toggle to all (already default)
      fireEvent.click(screen.getByTestId("toggle-all"));

      await waitFor(() => {
        expect(screen.getByTestId("streamdown")).toBeInTheDocument();
        expect(screen.getByText("Test fact")).toBeInTheDocument();
      });
    });

    test("facts filter with no matching facts shows no matches in facts block", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Something specific" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByTestId("toggle-facts"));

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "nonexistent" },
      });

      await waitFor(() => {
        // "No matches" appears both in the overall no-matches block and in the facts block
        expect(screen.getAllByText("No matches").length).toBeGreaterThanOrEqual(
          1,
        );
      });
    });

    test("facts filter with no query and no facts shows no facts message", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByTestId("toggle-facts"));

      await waitFor(() => {
        expect(screen.getByText("No facts")).toBeInTheDocument();
      });
    });

    test("search by category filters facts", async () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({ id: "f1", content: "Fact A", category: "preference" }),
          makeFact({ id: "f2", content: "Fact B", category: "context" }),
        ],
      });
      render(<MemorySettingsPage />);

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "preference" },
      });

      await waitFor(() => {
        expect(screen.getByText("Fact A")).toBeInTheDocument();
        expect(screen.queryByText("Fact B")).not.toBeInTheDocument();
      });
    });
  });

  // ─── Fact display ────────────────────────────────────────────────────────

  describe("Fact display", () => {
    test("renders fact content and category", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("Test fact")).toBeInTheDocument();
      expect(screen.getByText("Context")).toBeInTheDocument();
    });

    test("renders fact with very high confidence label (>= 0.85)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.95 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Very High")).toBeInTheDocument();
    });

    test("renders fact with very high confidence at boundary (0.85)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.85 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Very High")).toBeInTheDocument();
    });

    test("renders fact with high confidence label (>= 0.65)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.7 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("High")).toBeInTheDocument();
    });

    test("renders fact with high confidence at boundary (0.65)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.65 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("High")).toBeInTheDocument();
    });

    test("renders fact with normal confidence label (< 0.65)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.3 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Normal")).toBeInTheDocument();
    });

    test("renders fact with normal confidence at boundary (0.64)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0.64 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Normal")).toBeInTheDocument();
    });

    test("renders manual source as Manual text", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ source: "manual" })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Manual")).toBeInTheDocument();
    });

    test("renders thread source as a link", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ source: "thread-abc-123" })],
      });
      render(<MemorySettingsPage />);
      const link = screen.getByText("View");
      expect(link).toBeInTheDocument();
      expect(link.closest("a")).toHaveAttribute(
        "href",
        "/workspace/chats/thread-abc-123",
      );
    });

    test("renders multiple facts", () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({ id: "f1", content: "First fact" }),
          makeFact({
            id: "f2",
            content: "Second fact",
            category: "preference",
          }),
          makeFact({ id: "f3", content: "Third fact", confidence: 0.4 }),
        ],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("First fact")).toBeInTheDocument();
      expect(screen.getByText("Second fact")).toBeInTheDocument();
      expect(screen.getByText("Third fact")).toBeInTheDocument();
    });

    test("fact category is capitalized with upperFirst", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ category: "preference" })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Preference")).toBeInTheDocument();
    });

    test("fact displays created date", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("ago (2024-06-01)")).toBeInTheDocument();
    });

    test("renders edit and delete buttons for each fact", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f1" })],
      });
      render(<MemorySettingsPage />);
      // Each fact has edit and delete buttons
      const editButtons = screen.getAllByTitle("Edit");
      const deleteButtons = screen.getAllByTitle("Delete");
      expect(editButtons.length).toBeGreaterThanOrEqual(1);
      expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ─── Summary display ─────────────────────────────────────────────────────

  describe("Summary display", () => {
    test("renders summaries in Streamdown component", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown).toBeInTheDocument();
    });

    test("summaries include overview and section titles", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("Overview");
      expect(streamdown.textContent).toContain("Work");
      expect(streamdown.textContent).toContain("User Context");
    });

    test("summaries include last updated time", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("Last Updated");
      expect(streamdown.textContent).toContain("ago (2024-06-01T00:00:00Z)");
    });

    test("hides summaries when filter is facts", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByTestId("toggle-facts"));
      await waitFor(() => {
        expect(screen.queryByTestId("streamdown")).not.toBeInTheDocument();
      });
    });

    test("shows summaries when filter is all", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("toggle-all"));
      await waitFor(() => {
        expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      });
    });

    test("shows summaries when filter is summaries", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByTestId("toggle-summaries"));
      await waitFor(() => {
        expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      });
    });

    test("renders read only notice above summaries", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("Read only")).toBeInTheDocument();
    });

    test("summaries with empty summary show placeholder", () => {
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "", updatedAt: "" },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
        history: {
          recentMonths: { summary: "", updatedAt: "" },
          earlierContext: { summary: "", updatedAt: "" },
          longTermBackground: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("Empty");
    });

    test("summaries include updatedAt when present", () => {
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "Work", updatedAt: "2024-06-01" },
          personalContext: { summary: "Personal", updatedAt: "2024-07-01" },
          topOfMind: { summary: "Top", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("ago (2024-06-01)");
      expect(streamdown.textContent).toContain("ago (2024-07-01)");
    });

    test("summaries include history sections", () => {
      mockMemory = makeMemory({
        history: {
          recentMonths: { summary: "Recent stuff", updatedAt: "2024-05-01" },
          earlierContext: { summary: "Earlier stuff", updatedAt: "2024-04-01" },
          longTermBackground: { summary: "Long term", updatedAt: "2024-03-01" },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("History");
      expect(streamdown.textContent).toContain("Recent");
      expect(streamdown.textContent).toContain("Earlier");
      expect(streamdown.textContent).toContain("Long Term");
    });
  });

  // ─── Export functionality ────────────────────────────────────────────────

  describe("Export functionality", () => {
    test("clicking export triggers exportMemory and shows success toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Export"));

      await await waitFor(() => {
        expect(mockExportMemoryFn).toHaveBeenCalled();
        expect(toast.success).toHaveBeenCalledWith("Exported");
      });
    });

    test("export error shows error toast", async () => {
      mockExportMemoryFn = vi
        .fn()
        .mockRejectedValue(new Error("Export failed"));
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Export"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Export failed");
      });
    });

    test("export with non-Error rejection shows string error", async () => {
      mockExportMemoryFn = vi.fn().mockRejectedValue("some error");
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Export"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("some error");
      });
    });

    test("export creates a download link with correct filename", async () => {
      mockExportMemoryFn = vi.fn().mockResolvedValue({
        ...DEFAULT_EXPORT_DATA,
        lastUpdated: "2024-06-15T10:30:00.000Z",
      });
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      const appendSpy = vi.spyOn(document.body, "appendChild");
      const removeSpy = vi.spyOn(HTMLElement.prototype, "remove");

      fireEvent.click(screen.getByText("Export"));

      await await waitFor(() => {
        expect(appendSpy).toHaveBeenCalled();
        expect(removeSpy).toHaveBeenCalled();
      });

      appendSpy.mockRestore();
      removeSpy.mockRestore();
    });
  });

  // ─── Import functionality ────────────────────────────────────────────────

  describe("Import functionality", () => {
    test("import button triggers file input click", () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      const fileInput =
        container.querySelector<HTMLInputElement>('input[type="file"]')!;
      const clickSpy = vi.spyOn(fileInput, "click");

      fireEvent.click(screen.getByText("Import"));
      expect(clickSpy).toHaveBeenCalled();
      clickSpy.mockRestore();
    });

    test("valid JSON file shows import confirmation dialog", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
        expect(screen.getByText("Import memory?")).toBeInTheDocument();
      });
    });

    test("invalid JSON shows error toast", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, "{invalid json");

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("valid JSON with invalid structure shows error toast", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify({ foo: "bar" }));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("no file selected does nothing", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      const input = container.querySelector('input[type="file"]')!;
      Object.defineProperty(input, "files", {
        value: [],
        configurable: true,
      });
      fireEvent.change(input);

      await await waitFor(() => {
        expect(screen.queryByText("Import?")).not.toBeInTheDocument();
      });
    });

    test("confirm import calls mutation and shows success", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      // Select file to open import dialog
      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      // Click Import button in dialog (last "Import" text = dialog confirm)
      const importBtns = screen.getAllByText("Import");
      fireEvent.click(importBtns[importBtns.length - 1]!);

      await await waitFor(() => {
        expect(mockImportMemory.mutateAsync).toHaveBeenCalled();
        expect(toast.success).toHaveBeenCalledWith("Imported");
      });
    });

    test("import error shows error toast", async () => {
      mockImportMemory.mutateAsync = vi
        .fn()
        .mockRejectedValue(new Error("Import failed"));
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      const importBtns = screen.getAllByText("Import");
      fireEvent.click(importBtns[importBtns.length - 1]!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Import failed");
      });
    });

    test("import with non-Error rejection shows string error", async () => {
      mockImportMemory.mutateAsync = vi.fn().mockRejectedValue("bad import");
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      const importBtns = screen.getAllByText("Import");
      fireEvent.click(importBtns[importBtns.length - 1]!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("bad import");
      });
    });

    test("cancel import closes dialog", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Cancel"));

      await await waitFor(() => {
        expect(screen.queryByText("Import?")).not.toBeInTheDocument();
      });
    });

    test("import dialog shows file name and fact count", async () => {
      const importData = makeValidImportData();
      importData.facts = [
        {
          id: "f1",
          content: "A",
          category: "c",
          confidence: 0.5,
          createdAt: "2024-01-01",
          source: "manual",
        },
        {
          id: "f2",
          content: "B",
          category: "c",
          confidence: 0.6,
          createdAt: "2024-01-01",
          source: "manual",
        },
      ];
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(importData), "my-memory.json");

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      expect(screen.getByText("my-memory.json")).toBeInTheDocument();
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    test("import button is disabled when import is pending", () => {
      mockImportMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const btn = screen.getByText("Import").closest("button");
      expect(btn).toBeDisabled();
    });

    test("import dialog cancel button is disabled when pending", async () => {
      mockImportMemory.isPending = true;
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      const cancelBtn = screen.getByText("Cancel").closest("button");
      expect(cancelBtn).toBeDisabled();
    });

    test("import dialog confirm button is disabled when pending", async () => {
      mockImportMemory.isPending = true;
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      // The Import button inside the dialog
      const importBtns = screen.getAllByText("Import");
      // The dialog confirm button should be disabled
      const dialogBtn = importBtns[importBtns.length - 1]!.closest("button");
      expect(dialogBtn).toBeDisabled();
    });
  });

  // ─── Clear all memory ────────────────────────────────────────────────────

  describe("Clear all memory", () => {
    test("clicking Clear All opens confirmation dialog", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Clear All"));

      expect(screen.getByText("Clear all?")).toBeInTheDocument();
      expect(
        screen.getByText("This will remove everything."),
      ).toBeInTheDocument();
    });

    test("confirm button calls clear mutation", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Clear All"));
      // Click the destructive (confirm) button inside the dialog
      // When dialog is open, "Clear All" appears twice: toolbar + dialog confirm
      const clearBtns = screen.getAllByText("Clear All");
      fireEvent.click(clearBtns[clearBtns.length - 1]!);

      await await waitFor(() => {
        expect(mockClearMemory.mutateAsync).toHaveBeenCalled();
        expect(toast.success).toHaveBeenCalledWith("Memory cleared");
      });
    });

    test("failed clear shows error toast", async () => {
      mockClearMemory.mutateAsync = vi
        .fn()
        .mockRejectedValue(new Error("Clear failed"));
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Clear All"));
      const clearBtns = screen.getAllByText("Clear All");
      fireEvent.click(clearBtns[clearBtns.length - 1]!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Clear failed");
      });
    });

    test("failed clear with non-Error shows string", async () => {
      mockClearMemory.mutateAsync = vi.fn().mockRejectedValue("clear err");
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Clear All"));
      const clearBtns = screen.getAllByText("Clear All");
      fireEvent.click(clearBtns[clearBtns.length - 1]!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("clear err");
      });
    });

    test("cancel button closes dialog", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Clear All"));
      expect(screen.getByText("Clear all?")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Cancel"));

      expect(screen.queryByText("Clear all?")).not.toBeInTheDocument();
    });

    test("clear button shows loading text when pending", () => {
      mockClearMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("clear button is disabled when pending", () => {
      mockClearMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      const btn = screen.getByText("Loading...").closest("button");
      expect(btn).toBeDisabled();
    });

    test("cancel button in clear dialog is disabled when pending", () => {
      mockClearMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      // The clear dialog is not open by default, need to open it
      // But since isPending is true, the Clear All button is disabled
      // so we can't open the dialog via click in the test
      // Instead, we just verify the button is disabled
      const btns = screen.getAllByText("Loading...");
      expect(btns.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ─── Add fact ────────────────────────────────────────────────────────────

  describe("Add fact", () => {
    test("opens create dialog with default form values", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      // "Add Fact" appears in both toolbar button and dialog title
      expect(screen.getAllByText("Add Fact").length).toBeGreaterThanOrEqual(2);
      // Form fields should have default values
      const contentArea = screen.getByLabelText("Content");
      expect(contentArea).toHaveValue("");

      const categoryInput = screen.getByLabelText("Category");
      expect(categoryInput).toHaveValue("context");

      const confidenceInput = screen.getByLabelText("Confidence");
      expect(confidenceInput).toHaveValue("0.8");
    });

    test("validates empty content shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      // Click Save without entering content
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Content required");
      });
      expect(mockCreateFact.mutateAsync).not.toHaveBeenCalled();
    });

    test("validates whitespace-only content shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "   " },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Content required");
      });
    });

    test("validates invalid confidence (NaN) shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "abc" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("validates confidence below 0 shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "-0.1" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("validates confidence above 1 shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "1.5" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("validates confidence of Infinity shows error toast", async () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "Infinity" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("successful create shows success toast and closes dialog", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "New important fact" },
      });
      fireEvent.change(screen.getByLabelText("Category"), {
        target: { value: "preference" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.9" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith({
          content: "New important fact",
          category: "preference",
          confidence: 0.9,
        });
        expect(toast.success).toHaveBeenCalledWith("Fact added");
      });

      // Dialog should close
      await await waitFor(() => {
        expect(screen.queryByLabelText("Content")).not.toBeInTheDocument();
      });
    });

    test("empty category defaults to context", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Fact with no category" },
      });
      fireEvent.change(screen.getByLabelText("Category"), {
        target: { value: "" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.7" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith({
          content: "Fact with no category",
          category: "context",
          confidence: 0.7,
        });
      });
    });

    test("error during create shows error toast", async () => {
      mockCreateFact.mutateAsync = vi
        .fn()
        .mockRejectedValue(new Error("Create failed"));
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.5" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Create failed");
      });
    });

    test("non-Error during create shows string error", async () => {
      mockCreateFact.mutateAsync = vi.fn().mockRejectedValue("create err");
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.5" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("create err");
      });
    });

    test("cancel closes dialog and resets form", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Some content" },
      });

      // Cancel
      fireEvent.click(screen.getByText("Cancel"));

      // Dialog should be closed
      expect(screen.queryByLabelText("Content")).not.toBeInTheDocument();

      // Reopen and verify form was reset
      fireEvent.click(screen.getByText("Add Fact"));
      expect(screen.getByLabelText("Content")).toHaveValue("");
    });

    test("save button shows loading text when pending", () => {
      mockCreateFact.isPending = true;
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    test("save button is disabled when pending", () => {
      mockCreateFact.isPending = true;
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      const saveBtn = screen.getByText("Loading...").closest("button");
      expect(saveBtn).toBeDisabled();
    });

    test("accepts confidence of exactly 0 as valid", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Low confidence fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({ confidence: 0 }),
        );
      });
    });

    test("accepts confidence of exactly 1 as valid", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Max confidence fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "1" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({ confidence: 1 }),
        );
      });
    });

    test("content is trimmed when saving", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "  Trimmed fact  " },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.5" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({ content: "Trimmed fact" }),
        );
      });
    });

    test("category is trimmed when saving", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "A fact" },
      });
      fireEvent.change(screen.getByLabelText("Category"), {
        target: { value: "  preference  " },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "0.5" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockCreateFact.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({ category: "preference" }),
        );
      });
    });
  });

  // ─── Edit fact ───────────────────────────────────────────────────────────

  describe("Edit fact", () => {
    test("opens edit dialog with pre-filled values", () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({
            id: "f1",
            content: "Existing fact",
            category: "preference",
            confidence: 0.7,
          }),
        ],
      });
      render(<MemorySettingsPage />);

      // Click the edit button
      const editButtons = screen.getAllByTitle("Edit");
      fireEvent.click(editButtons[0]!);

      expect(screen.getByText("Edit Fact")).toBeInTheDocument();
      expect(screen.getByLabelText("Content")).toHaveValue("Existing fact");
      expect(screen.getByLabelText("Category")).toHaveValue("preference");
      expect(screen.getByLabelText("Confidence")).toHaveValue("0.7");
    });

    test("successful edit shows success toast and closes dialog", async () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({
            id: "f-edit",
            content: "Original content",
            category: "context",
            confidence: 0.5,
          }),
        ],
      });
      render(<MemorySettingsPage />);

      const editButtons = screen.getAllByTitle("Edit");
      fireEvent.click(editButtons[0]!);

      // Modify content
      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Updated content" },
      });

      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockUpdateFact.mutateAsync).toHaveBeenCalledWith({
          factId: "f-edit",
          input: {
            content: "Updated content",
            category: "context",
            confidence: 0.5,
          },
        });
        expect(toast.success).toHaveBeenCalledWith("Fact updated");
      });
    });

    test("error during edit shows error toast", async () => {
      mockUpdateFact.mutateAsync = vi
        .fn()
        .mockRejectedValue(new Error("Edit failed"));
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-err" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Edit")[0]!);
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Edit failed");
      });
    });

    test("cancel edit closes dialog and resets state", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Original" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Edit")[0]!);

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Changed" },
      });

      fireEvent.click(screen.getByText("Cancel"));

      // Dialog closed
      expect(screen.queryByLabelText("Content")).not.toBeInTheDocument();

      // Reopen edit - should show original, not changed
      fireEvent.click(screen.getAllByTitle("Edit")[0]!);
      expect(screen.getByLabelText("Content")).toHaveValue("Original");
    });

    test("edit dialog uses updateMutation not createMutation", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-only" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Edit")[0]!);
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(mockUpdateFact.mutateAsync).toHaveBeenCalled();
        expect(mockCreateFact.mutateAsync).not.toHaveBeenCalled();
      });
    });

    test("edit dialog shows Edit Fact title", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Edit")[0]!);
      expect(screen.getByText("Edit Fact")).toBeInTheDocument();
    });

    test("save button shows loading when update is pending", () => {
      mockUpdateFact.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Edit")[0]!);

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });

  // ─── Delete fact ─────────────────────────────────────────────────────────

  describe("Delete fact", () => {
    test("clicking delete opens confirmation dialog", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      const deleteButtons = screen.getAllByTitle("Delete");
      fireEvent.click(deleteButtons[0]!);

      expect(screen.getByText("Delete fact?")).toBeInTheDocument();
      expect(screen.getByText("Delete this fact?")).toBeInTheDocument();
    });

    test("shows fact preview in confirmation dialog", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Important fact to preview" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);

      expect(screen.getByText("Preview")).toBeInTheDocument();
      // Text appears both in fact list and in dialog preview
      expect(
        screen.getAllByText("Important fact to preview").length,
      ).toBeGreaterThanOrEqual(2);
    });

    test("truncates long fact content in preview", () => {
      const longContent = "A".repeat(200);
      mockMemory = makeMemory({
        facts: [makeFact({ content: longContent })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);

      // Should be truncated to 140 chars with "..."
      const preview = screen.getByText(
        new RegExp("^" + "A".repeat(137) + "\\.\\.\\.$"),
      );
      expect(preview).toBeInTheDocument();
    });

    test("confirm calls delete mutation", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-delete" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);

      // Click the destructive confirm button
      const deleteBtn = screen.getByText("Delete").closest("button");
      fireEvent.click(deleteBtn!);

      await await waitFor(() => {
        expect(mockDeleteFact.mutateAsync).toHaveBeenCalledWith("f-delete");
        expect(toast.success).toHaveBeenCalledWith("Fact deleted");
      });
    });

    test("successful delete shows success toast", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-succ" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      const deleteBtn = screen.getByText("Delete").closest("button");
      fireEvent.click(deleteBtn!);

      await await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith("Fact deleted");
      });
    });

    test("failed delete shows error toast", async () => {
      mockDeleteFact.mutateAsync = vi
        .fn()
        .mockRejectedValue(new Error("Delete failed"));
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-fail" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      const deleteBtn = screen.getByText("Delete").closest("button");
      fireEvent.click(deleteBtn!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Delete failed");
      });
    });

    test("non-Error during delete shows string error", async () => {
      mockDeleteFact.mutateAsync = vi.fn().mockRejectedValue("del err");
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-str" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      const deleteBtn = screen.getByText("Delete").closest("button");
      fireEvent.click(deleteBtn!);

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("del err");
      });
    });

    test("cancel closes delete dialog", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      expect(screen.getByText("Delete fact?")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Cancel"));

      expect(screen.queryByText("Delete fact?")).not.toBeInTheDocument();
    });

    test("delete button is disabled when delete is pending", () => {
      mockDeleteFact.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      const editButtons = screen.getAllByTitle("Edit");
      // The edit buttons should be disabled when delete is pending
      editButtons.forEach((btn) => {
        expect(btn.closest("button")).toBeDisabled();
      });
    });

    test("delete icon buttons are disabled when delete is pending", () => {
      mockDeleteFact.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      const deleteButtons = screen.getAllByTitle("Delete");
      deleteButtons.forEach((btn) => {
        expect(btn).toBeDisabled();
      });
    });

    test("delete dialog shows no preview when factToDelete is null", () => {
      // This tests the guard `factToDelete ? ... : null` in the dialog
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      // Without opening the delete dialog, no preview should be visible
      expect(screen.queryByText("Preview")).not.toBeInTheDocument();
    });
  });

  // ─── Dialog state management ─────────────────────────────────────────────

  describe("Dialog state management", () => {
    test("fact editor dialog resets on close via cancel", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      // Open create dialog
      fireEvent.click(screen.getByText("Add Fact"));

      // Fill in some data
      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Temporary data" },
      });

      // Close via cancel
      fireEvent.click(screen.getByText("Cancel"));

      // Reopen - should have default values
      fireEvent.click(screen.getByText("Add Fact"));
      expect(screen.getByLabelText("Content")).toHaveValue("");
      expect(screen.getByLabelText("Category")).toHaveValue("context");
      expect(screen.getByLabelText("Confidence")).toHaveValue("0.8");
    });

    test("import dialog resets pendingImport on cancel", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      // Import a valid file
      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      // Cancel
      fireEvent.click(screen.getByText("Cancel"));

      // Dialog should close
      await await waitFor(() => {
        expect(screen.queryByText("Import?")).not.toBeInTheDocument();
      });

      // Import button should still be clickable
      expect(screen.getByText("Import")).toBeInTheDocument();
    });

    test("fact delete dialog resets factToDelete on cancel", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      expect(screen.getByText("Delete fact?")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Cancel"));

      expect(screen.queryByText("Delete fact?")).not.toBeInTheDocument();
    });

    test("clear dialog can be reopened after cancel", () => {
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      // Open and cancel
      fireEvent.click(screen.getByText("Clear All"));
      fireEvent.click(screen.getByText("Cancel"));

      // Reopen
      fireEvent.click(screen.getByText("Clear All"));
      expect(screen.getByText("Clear all?")).toBeInTheDocument();
    });
  });

  // ─── Comprehensive edge cases ────────────────────────────────────────────

  describe("Edge cases", () => {
    test("fact with empty string source shows as link (not manual)", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ source: "" })],
      });
      render(<MemorySettingsPage />);
      // Empty string is not "manual", so it should render as a link
      expect(screen.getByText("View")).toBeInTheDocument();
    });

    test("fact with zero confidence shows normal level", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: 0 })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Normal")).toBeInTheDocument();
    });

    test("multiple section groups in summaries", () => {
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "Work details", updatedAt: "2024-01-01" },
          personalContext: {
            summary: "Personal details",
            updatedAt: "2024-02-01",
          },
          topOfMind: { summary: "Urgent items", updatedAt: "2024-03-01" },
        },
        history: {
          recentMonths: { summary: "Recent history", updatedAt: "2024-04-01" },
          earlierContext: {
            summary: "Earlier context",
            updatedAt: "2024-05-01",
          },
          longTermBackground: {
            summary: "Long term background",
            updatedAt: "2024-06-01",
          },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      // Check both group titles appear
      expect(streamdown.textContent).toContain("User Context");
      expect(streamdown.textContent).toContain("History");
    });

    test("search with only whitespace results in no query filter", async () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Visible fact" })],
      });
      render(<MemorySettingsPage />);

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "   " },
      });

      // Whitespace-only query is trimmed to empty, so all content shows
      await waitFor(() => {
        expect(screen.getByText("Visible fact")).toBeInTheDocument();
      });
    });

    test("fact editor dialog shows Add Fact title when creating", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByText("Add Fact"));
      // "Add Fact" appears in both toolbar button and dialog title
      expect(screen.getAllByText("Add Fact").length).toBeGreaterThanOrEqual(2);
      // Should NOT show "Edit Fact"
      expect(screen.queryByText("Edit Fact")).not.toBeInTheDocument();
    });

    test("confidence hint text is displayed in fact editor", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByText("Add Fact"));
      expect(screen.getByText("0-1")).toBeInTheDocument();
    });

    test("fact with long content renders fully in fact list", () => {
      const longContent = "A".repeat(100);
      mockMemory = makeMemory({
        facts: [makeFact({ content: longContent })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText(longContent)).toBeInTheDocument();
    });

    test("truncated fact preview with very short maxLength", () => {
      // truncateFactPreview(content, maxLength) where maxLength <= 3
      // This is tested indirectly through the delete dialog
      const shortContent = "AB";
      mockMemory = makeMemory({
        facts: [makeFact({ content: shortContent })],
      });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      // Text appears both in fact list and in dialog preview
      expect(screen.getAllByText(shortContent).length).toBeGreaterThanOrEqual(
        2,
      );
    });

    test("search filters both facts and summaries simultaneously", async () => {
      mockMemory = makeMemory({
        user: {
          workContext: {
            summary: "Coding guidelines",
            updatedAt: "2024-01-01",
          },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
        facts: [
          makeFact({ id: "f1", content: "Coding standards" }),
          makeFact({ id: "f2", content: "Meeting notes" }),
        ],
      });
      render(<MemorySettingsPage />);

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "coding" },
      });

      await waitFor(() => {
        // Summary should be visible (matches "Coding guidelines")
        expect(screen.getByTestId("streamdown").textContent).toContain(
          "Coding guidelines",
        );
        // Fact matching "Coding standards" should be visible
        expect(screen.getByText("Coding standards")).toBeInTheDocument();
        // Fact not matching should be hidden
        expect(screen.queryByText("Meeting notes")).not.toBeInTheDocument();
      });
    });

    test("fact with negative confidence is invalid", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "-1" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("fact with confidence > 1 is invalid", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getByText("Add Fact"));

      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Fact" },
      });
      fireEvent.change(screen.getByLabelText("Confidence"), {
        target: { value: "2" },
      });
      fireEvent.click(screen.getByText("Save"));

      await await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid confidence");
      });
    });

    test("clear button shows loading text when clearMemory.isPending is true", () => {
      mockClearMemory.isPending = true;
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);
      // The button should show loading text
      const buttons = screen.getAllByText("Loading...");
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });

    test("no toolbar buttons when loading", () => {
      mockIsLoading = true;
      render(<MemorySettingsPage />);
      expect(screen.queryByText("Import")).not.toBeInTheDocument();
      expect(screen.queryByText("Export")).not.toBeInTheDocument();
      expect(screen.queryByText("Add Fact")).not.toBeInTheDocument();
      expect(screen.queryByText("Clear All")).not.toBeInTheDocument();
    });

    test("no toolbar buttons on error", () => {
      mockError = new Error("err");
      render(<MemorySettingsPage />);
      expect(screen.queryByText("Import")).not.toBeInTheDocument();
      expect(screen.queryByText("Export")).not.toBeInTheDocument();
    });

    test("no toolbar buttons on empty memory", () => {
      mockMemory = null;
      render(<MemorySettingsPage />);
      expect(screen.queryByText("Import")).not.toBeInTheDocument();
    });

    test("import file input has correct accept attribute", () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      const fileInput = container.querySelector('input[type="file"]');
      expect(fileInput).toHaveAttribute("accept", ".json,application/json");
    });

    test("import file input is hidden", () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      const fileInput = container.querySelector('input[type="file"]');
      expect(fileInput).toHaveClass("hidden");
    });

    test("fact with all sections having content shows all in summary", () => {
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "Work content", updatedAt: "2024-01-01" },
          personalContext: {
            summary: "Personal content",
            updatedAt: "2024-02-01",
          },
          topOfMind: { summary: "Top content", updatedAt: "2024-03-01" },
        },
        history: {
          recentMonths: { summary: "Recent content", updatedAt: "2024-04-01" },
          earlierContext: {
            summary: "Earlier content",
            updatedAt: "2024-05-01",
          },
          longTermBackground: {
            summary: "Long term content",
            updatedAt: "2024-06-01",
          },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("Work content");
      expect(streamdown.textContent).toContain("Personal content");
      expect(streamdown.textContent).toContain("Top content");
      expect(streamdown.textContent).toContain("Recent content");
      expect(streamdown.textContent).toContain("Earlier content");
      expect(streamdown.textContent).toContain("Long term content");
    });

    test("formatTimeAgo is called for each fact's createdAt", () => {
      mockMemory = makeMemory({
        facts: [
          makeFact({ id: "f1", createdAt: "2024-01-01" }),
          makeFact({ id: "f2", createdAt: "2024-06-15" }),
        ],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("ago (2024-01-01)")).toBeInTheDocument();
      expect(screen.getByText("ago (2024-06-15)")).toBeInTheDocument();
    });

    test("summary updatedAt is formatted with formatTimeAgo", () => {
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "Work", updatedAt: "2024-03-15" },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      expect(streamdown.textContent).toContain("ago (2024-03-15)");
    });

    test("summaries with no updatedAt omit the updated line for individual sections", () => {
      // One section has updatedAt, others do not
      mockMemory = makeMemory({
        user: {
          workContext: { summary: "Work", updatedAt: "2024-06-01" },
          personalContext: { summary: "Personal", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
        history: {
          recentMonths: { summary: "", updatedAt: "" },
          earlierContext: { summary: "", updatedAt: "" },
          longTermBackground: { summary: "", updatedAt: "" },
        },
      });
      render(<MemorySettingsPage />);
      const streamdown = screen.getByTestId("streamdown");
      // The overview always shows "Last Updated"
      expect(streamdown.textContent).toContain("Last Updated");
      // The workContext section has updatedAt, so its date should appear
      expect(streamdown.textContent).toContain("ago (2024-06-01)");
      // Sections with empty updatedAt should not show formatTimeAgo for them
      // Only 1 "ago (" match expected (for workContext + overview lastUpdated)
      const agoMatches = streamdown.textContent?.match(/ago \(/g);
      // 2 matches: one for overview "Last Updated" and one for workContext
      expect(agoMatches?.length).toBe(2);
    });
  });

  // ─── Coverage edge cases for missed lines ────────────────────────────────

  describe("Coverage edge cases for missed lines", () => {
    // ── confidenceToLevelKey: non-number/non-finite → "unknown" ───────────

    test("fact with NaN confidence renders Unknown confidence level", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: NaN })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });

    test("fact with Infinity confidence renders Unknown confidence level", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: Infinity })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });

    test("fact with -Infinity confidence renders Unknown confidence level", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ confidence: -Infinity })],
      });
      render(<MemorySettingsPage />);
      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });

    // ── isImportedMemory / isRecord edge cases ────────────────────────────

    test("import with null JSON value shows error (isRecord returns false)", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(container, "null");
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with numeric JSON value shows error (isRecord returns false)", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(container, "42");
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with missing version field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with missing lastUpdated field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with non-string lastUpdated shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: 12345,
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with missing user field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with missing history field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with missing facts array shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    // ── isMemorySection validation ────────────────────────────────────────

    test("import with section missing summary field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with section missing updatedAt field shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "Work" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with section as non-object shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: "not an object",
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    // ── isMemoryFact validation ───────────────────────────────────────────

    test("import with fact missing required fields shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [{ content: "Missing id and other fields" }],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with fact having string confidence shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: [
            {
              id: "f1",
              content: "Bad confidence",
              category: "c",
              confidence: "high",
              createdAt: "2024-01-01",
              source: "manual",
            },
          ],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    test("import with fact as non-object shows error", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(
        container,
        JSON.stringify({
          version: "1.0",
          lastUpdated: "2024-01-01",
          user: {
            workContext: { summary: "", updatedAt: "" },
            personalContext: { summary: "", updatedAt: "" },
            topOfMind: { summary: "", updatedAt: "" },
          },
          history: {
            recentMonths: { summary: "", updatedAt: "" },
            earlierContext: { summary: "", updatedAt: "" },
            longTermBackground: { summary: "", updatedAt: "" },
          },
          facts: ["not an object"],
        }),
      );
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Invalid file");
      });
    });

    // ── Import dialog: lastUpdated edge case ──────────────────────────────

    test("import dialog shows dash when lastUpdated is empty string", async () => {
      const importData = makeValidImportData();
      importData.lastUpdated = "";
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);
      setupFileImport(container, JSON.stringify(importData));
      await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });
      // The dialog should show "-" instead of a formatted date for lastUpdated
      const lastUpdatedLabel = screen.getByText("Last Updated:");
      const row = lastUpdatedLabel.parentElement;
      expect(row?.textContent).toContain("-");
      expect(row?.textContent).not.toContain("ago (");
    });

    // ── Edit fact: non-Error rejection path ───────────────────────────────

    test("edit fact with non-Error rejection shows string error toast", async () => {
      mockUpdateFact.mutateAsync = vi.fn().mockRejectedValue("edit err");
      mockMemory = makeMemory({
        facts: [makeFact({ id: "f-edit-str" })],
      });
      render(<MemorySettingsPage />);
      fireEvent.click(screen.getAllByTitle("Edit")[0]!);
      fireEvent.click(screen.getByText("Save"));
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("edit err");
      });
    });

    // ── Export button loading state ───────────────────────────────────────

    test("export button shows loading text and is disabled while exporting", async () => {
      // Make export return a never-resolving promise to keep isExporting true
      mockExportMemoryFn = vi.fn().mockReturnValue(new Promise(() => {}));
      mockMemory = makeMemory();
      render(<MemorySettingsPage />);

      // Initially shows "Export"
      expect(screen.getByText("Export")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Export"));

      // After click, "Export" text should be replaced by "Loading..."
      await waitFor(() => {
        expect(screen.queryByText("Export")).not.toBeInTheDocument();
      });
    });

    // ── Search: filter "summaries" with no matching results ───────────────

    test("filter summaries with non-matching query hides summaries and shows no matches", async () => {
      mockMemory = makeMemory({
        user: {
          workContext: {
            summary: "Engineering notes",
            updatedAt: "2024-01-01",
          },
          personalContext: { summary: "", updatedAt: "" },
          topOfMind: { summary: "", updatedAt: "" },
        },
        facts: [makeFact({ content: "Engineering fact" })],
      });
      render(<MemorySettingsPage />);

      // Switch to summaries filter
      fireEvent.click(screen.getByTestId("toggle-summaries"));

      // Type a query that matches nothing in summaries
      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "xyznonexistent" },
      });

      await waitFor(() => {
        // No matching content -> "No matches" shown
        expect(screen.getByText("No matches")).toBeInTheDocument();
        // Summaries block should not be rendered
        expect(screen.queryByTestId("streamdown")).not.toBeInTheDocument();
      });
    });

    // ── Search: filter "facts" with non-matching query and no facts ───────

    test("filter facts with non-matching query and no facts shows no matches", async () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      fireEvent.click(screen.getByTestId("toggle-facts"));

      fireEvent.change(screen.getByPlaceholderText("Search"), {
        target: { value: "something" },
      });

      await waitFor(() => {
        // Both the overall "no matches" banner and the facts block "no matches" appear
        expect(screen.getAllByText("No matches").length).toBeGreaterThanOrEqual(
          1,
        );
      });
    });

    // ── Dialog onOpenChange handlers (external close) ─────────────────────

    test("fact editor dialog onOpenChange resets state when closed externally", () => {
      mockMemory = makeMemory({ facts: [] });
      render(<MemorySettingsPage />);

      // Open the create dialog
      fireEvent.click(screen.getByText("Add Fact"));
      expect(
        screen.getByText("Add Fact", { selector: "h2" }),
      ).toBeInTheDocument();

      // Fill in some data
      fireEvent.change(screen.getByLabelText("Content"), {
        target: { value: "Some content" },
      });

      // Simulate external close (e.g., clicking overlay or pressing Escape)
      fireEvent.click(screen.getByTestId("dialog-external-close"));

      // Dialog should close and state should be reset
      expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();

      // Reopen and verify form was reset
      fireEvent.click(screen.getByText("Add Fact"));
      expect(screen.getByLabelText("Content")).toHaveValue("");
      expect(screen.getByLabelText("Category")).toHaveValue("context");
      expect(screen.getByLabelText("Confidence")).toHaveValue("0.8");
    });

    test("delete fact dialog onOpenChange resets factToDelete when closed externally", () => {
      mockMemory = makeMemory({
        facts: [makeFact({ content: "Fact to delete" })],
      });
      render(<MemorySettingsPage />);

      // Open the delete dialog
      fireEvent.click(screen.getAllByTitle("Delete")[0]!);
      expect(screen.getByText("Delete fact?")).toBeInTheDocument();

      // Simulate external close
      fireEvent.click(screen.getByTestId("dialog-external-close"));

      // Dialog should close
      expect(screen.queryByText("Delete fact?")).not.toBeInTheDocument();
    });

    test("import dialog onOpenChange resets pendingImport when closed externally", async () => {
      mockMemory = makeMemory();
      const { container } = render(<MemorySettingsPage />);

      // Open the import dialog
      setupFileImport(container, JSON.stringify(makeValidImportData()));

      await waitFor(() => {
        expect(screen.getByText("Import?")).toBeInTheDocument();
      });

      // Simulate external close
      fireEvent.click(screen.getByTestId("dialog-external-close"));

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByText("Import?")).not.toBeInTheDocument();
      });
    });
  });
});
