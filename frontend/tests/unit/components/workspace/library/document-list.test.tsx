import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockDocuments = [
  {
    id: "doc-1",
    name: "Document 1",
    status: "ready",
    created_at: "2024-01-01",
  },
  {
    id: "doc-2",
    name: "Document 2",
    status: "processing",
    created_at: "2024-01-02",
  },
];

vi.mock("@/core/library", () => ({
  useDocuments: () => ({
    documents: mockDocuments,
    isLoading: false,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let DocumentList: typeof import("@/components/workspace/library/document-list").DocumentList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/library/document-list");
  DocumentList = mod.DocumentList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("DocumentList", () => {
  test("displays list of documents", () => {
    render(<DocumentList />);
    expect(screen.getByText("Document 1")).toBeInTheDocument();
    expect(screen.getByText("Document 2")).toBeInTheDocument();
  });

  test("displays document status", () => {
    render(<DocumentList />);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
  });

  test("displays document IDs", () => {
    render(<DocumentList />);
    expect(screen.getByText("doc-1")).toBeInTheDocument();
    expect(screen.getByText("doc-2")).toBeInTheDocument();
  });
});
