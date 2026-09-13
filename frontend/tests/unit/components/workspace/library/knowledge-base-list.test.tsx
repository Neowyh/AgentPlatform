import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockKnowledgeBases = [
  {
    id: "kb-1",
    slug: "knowledge-base-1",
    display_name: "Knowledge Base 1",
    visibility: "private",
  },
  {
    id: "kb-2",
    slug: "knowledge-base-2",
    display_name: "Knowledge Base 2",
    visibility: "public",
  },
];

const hookState = {
  knowledgeBases: mockKnowledgeBases,
  isLoading: false,
  error: null as Error | null,
};

vi.mock("@/core/library", () => ({
  useKnowledgeBases: () => hookState,
  useCreateKnowledgeBase: () => ({
    isPending: false,
    error: null,
    mutateAsync: vi.fn(),
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let KnowledgeBaseList: typeof import("@/components/workspace/library/knowledge-base-list").KnowledgeBaseList;

beforeEach(async () => {
  vi.clearAllMocks();
  hookState.knowledgeBases = mockKnowledgeBases;
  hookState.isLoading = false;
  hookState.error = null;
  const mod =
    await import("@/components/workspace/library/knowledge-base-list");
  KnowledgeBaseList = mod.KnowledgeBaseList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeBaseList", () => {
  test("displays list of knowledge bases", () => {
    render(<KnowledgeBaseList />);
    expect(screen.getByText("Knowledge Base 1")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Base 2")).toBeInTheDocument();
  });

  test("displays canonical KnowledgeBase details", () => {
    render(<KnowledgeBaseList />);
    expect(screen.getByText("knowledge-base-1")).toBeInTheDocument();
    expect(screen.getByText("private")).toBeInTheDocument();
    expect(screen.getByText("public")).toBeInTheDocument();
  });

  test("displays a loading state", () => {
    hookState.isLoading = true;
    render(<KnowledgeBaseList />);
    expect(screen.getByText("Loading knowledge bases...")).toBeInTheDocument();
  });

  test("displays an empty state", () => {
    hookState.knowledgeBases = [];
    render(<KnowledgeBaseList />);
    expect(screen.getByText("No knowledge bases found")).toBeInTheDocument();
  });

  test("displays an error without leaking resource details", () => {
    hookState.error = new Error("Forbidden");
    render(<KnowledgeBaseList />);
    expect(
      screen.getByText("Unable to load knowledge bases."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Forbidden")).not.toBeInTheDocument();
  });
});
