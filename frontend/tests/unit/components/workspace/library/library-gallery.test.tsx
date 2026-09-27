import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/workspace/library",
}));

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
    t: {
      library: {
        title: "Library",
        description: "Manage your knowledge base documents",
        upload: "Upload Document",
        search: "Search documents...",
        documents: "Documents",
        knowledgeBases: "Knowledge Bases",
        qualityEntry: "Revisions & evaluation",
      },
    },
  }),
}));

vi.mock("@/core/library", () => ({
  useKnowledgeBases: () => ({ knowledgeBases: [] }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
  }) => (
    <div data-testid="tabs" data-value={value}>
      {children}
    </div>
  ),
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tabs-list">{children}</div>
  ),
  TabsTrigger: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <button data-testid="tabs-trigger" data-value={value}>
      {children}
    </button>
  ),
  TabsContent: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <div data-testid="tabs-content" data-value={value}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/workspace/library/document-list", () => ({
  DocumentList: () => <div data-testid="document-list">Document List</div>,
}));

vi.mock("@/components/workspace/library/knowledge-base-list", () => ({
  KnowledgeBaseList: ({ onSelect }: { onSelect?: (id: string) => void }) => (
    <button
      type="button"
      data-testid="knowledge-base-list"
      onClick={() => onSelect?.("kb-1")}
    >
      Knowledge Base List
    </button>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let LibraryGallery: typeof import("@/components/workspace/library/library-gallery").LibraryGallery;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/library/library-gallery");
  LibraryGallery = mod.LibraryGallery;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("LibraryGallery", () => {
  test("renders page title and description", () => {
    render(<LibraryGallery />);
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(
      screen.getByText("Manage your knowledge base documents"),
    ).toBeInTheDocument();
  });

  test("renders upload button", () => {
    render(<LibraryGallery />);
    expect(screen.getByText("Upload Document")).toBeInTheDocument();
  });

  test("renders search input", () => {
    render(<LibraryGallery />);
    expect(
      screen.getByPlaceholderText("Search documents..."),
    ).toBeInTheDocument();
  });

  test("links to the revisions and evaluation page", () => {
    render(<LibraryGallery />);
    expect(
      screen.getByRole("link", { name: "Revisions & evaluation" }),
    ).toHaveAttribute("href", "/workspace/library/quality");
  });

  test("renders only the baseline documents and knowledge bases tabs", () => {
    render(<LibraryGallery />);
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
    expect(screen.getByTestId("tabs-list")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Bases")).toBeInTheDocument();

    const triggers = screen.getAllByTestId("tabs-trigger");
    expect(triggers).toHaveLength(2);
    expect(triggers[0]?.getAttribute("data-value")).toBe("documents");
    expect(triggers[1]?.getAttribute("data-value")).toBe("knowledge-bases");
  });

  test("renders documents and knowledge base tab content", () => {
    render(<LibraryGallery />);
    expect(screen.getByTestId("document-list")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-base-list")).toBeInTheDocument();
  });

  test("defaults to the documents tab", () => {
    render(<LibraryGallery />);
    expect(screen.getByTestId("tabs").getAttribute("data-value")).toBe(
      "documents",
    );
  });

  test("selecting a knowledge base opens its documents", async () => {
    const user = userEvent.setup();
    render(<LibraryGallery />);
    await user.click(screen.getByText("Knowledge Base List"));
    expect(screen.getByTestId("tabs").getAttribute("data-value")).toBe(
      "documents",
    );
  });
});
