import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { KnowledgeBase } from "@/core/library";

const { translations } = vi.hoisted(() => ({
  translations: {
    library: {
      documentCount: (count: number) => `${count} documents`,
    },
  },
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: translations }),
}));

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockKnowledgeBases: KnowledgeBase[] = [
  {
    id: "kb-1",
    slug: "knowledge-base-1",
    display_name: "Knowledge Base 1",
    visibility: "private",
    type: "knowledge_base",
    can_modify: true,
  },
  {
    id: "kb-2",
    slug: "knowledge-base-2",
    display_name: "Knowledge Base 2",
    visibility: "public",
    type: "knowledge_base",
    can_modify: true,
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

  test("displays the document count when it is available", () => {
    hookState.knowledgeBases = [
      {
        id: "kb-1",
        slug: "knowledge-base-1",
        display_name: "Knowledge Base 1",
        visibility: "private",
        knowledge_document_count: 7,
        type: "knowledge_base",
        can_modify: true,
      },
    ];
    render(<KnowledgeBaseList />);
    expect(screen.getByText("7 documents")).toBeInTheDocument();
  });

  test("uses localized copy for the document count", () => {
    translations.library.documentCount = (count) => `${count} 个文档`;
    hookState.knowledgeBases = [
      {
        id: "kb-1",
        slug: "knowledge-base-1",
        display_name: "Knowledge Base 1",
        visibility: "private",
        knowledge_document_count: 7,
        type: "knowledge_base",
        can_modify: true,
      },
    ];
    render(<KnowledgeBaseList />);
    expect(screen.getByText("7 个文档")).toBeInTheDocument();
  });

  test("marks the selected knowledge base", () => {
    render(<KnowledgeBaseList selectedId="kb-2" />);
    expect(
      screen.getByText("Knowledge Base 2").closest("button")!,
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByText("Knowledge Base 1").closest("button")!,
    ).toHaveAttribute("aria-pressed", "false");
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
