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
      },
    },
  }),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({
    children,
    defaultValue,
  }: {
    children: React.ReactNode;
    defaultValue?: string;
  }) => (
    <div data-testid="tabs" data-default-value={defaultValue}>
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
  KnowledgeBaseList: () => (
    <div data-testid="knowledge-base-list">Knowledge Base List</div>
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

  test("renders tabs for documents and knowledge bases", () => {
    render(<LibraryGallery />);
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
    expect(screen.getByTestId("tabs-list")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Bases")).toBeInTheDocument();
  });

  test("renders tab content sections", () => {
    render(<LibraryGallery />);
    expect(screen.getByTestId("document-list")).toBeInTheDocument();
    expect(screen.getByTestId("knowledge-base-list")).toBeInTheDocument();
  });

  test("has correct default tab value", () => {
    render(<LibraryGallery />);
    const tabs = screen.getByTestId("tabs");
    expect(tabs.getAttribute("data-default-value")).toBe("documents");
  });

  test("has correct tab trigger values", () => {
    render(<LibraryGallery />);
    const triggers = screen.getAllByTestId("tabs-trigger");
    expect(triggers[0]?.getAttribute("data-value")).toBe("documents");
    expect(triggers[1]?.getAttribute("data-value")).toBe("knowledge-bases");
  });
});
