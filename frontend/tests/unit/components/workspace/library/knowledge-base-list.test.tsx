import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockKnowledgeBases = [
  {
    id: "kb-1",
    name: "Knowledge Base 1",
    document_count: 10,
    description: "First knowledge base",
  },
  {
    id: "kb-2",
    name: "Knowledge Base 2",
    document_count: 5,
    description: "Second knowledge base",
  },
];

vi.mock("@/core/library", () => ({
  useKnowledgeBases: () => ({
    knowledgeBases: mockKnowledgeBases,
    isLoading: false,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let KnowledgeBaseList: typeof import("@/components/workspace/library/knowledge-base-list").KnowledgeBaseList;

beforeEach(async () => {
  vi.clearAllMocks();
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

  test("displays document counts", () => {
    render(<KnowledgeBaseList />);
    expect(screen.getByText("10 documents")).toBeInTheDocument();
    expect(screen.getByText("5 documents")).toBeInTheDocument();
  });

  test("displays descriptions", () => {
    render(<KnowledgeBaseList />);
    expect(screen.getByText("First knowledge base")).toBeInTheDocument();
    expect(screen.getByText("Second knowledge base")).toBeInTheDocument();
  });
});
