import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      library: {
        retrievalTest: {
          selectKnowledgeBase: "Select a knowledge base to run retrieval tests",
          loading: "Loading...",
          revisionsLoadFailed: "Unable to load revisions.",
          noPublishedRevision:
            "This knowledge base has no published revision to test yet",
          questionLabel: "Question",
          questionPlaceholder: "Ask a question to probe this revision",
          topKLabel: "Hits (K)",
          revisionLabel: "Revision",
          run: "Run test",
          running: "Running...",
          runFailed: "Unable to run the retrieval test.",
          restricted: "You no longer have access to this knowledge base.",
          emptyResult: "No hits for this question.",
          providerFailed: (code: string) => `Retrieval failed (${code}).`,
          hitsTitle: (count: number) => `${count} hit(s)`,
          manifest: (hash: string) => `manifest ${hash}`,
          archivedTitle: "Archived tests",
          archivedEmpty: "No archived retrieval tests yet",
          archivedLoadFailed: "Unable to load archived tests.",
          viewRecord: "View record",
          recordLoadFailed: "This record is no longer accessible.",
          appliedParameters: "Applied parameters",
          profileLabel: "Profile",
          frozenProfile: "Frozen revision profile",
        },
      },
    },
  }),
}));

const archivedRecord = {
  id: "test-1",
  resource_id: "kb-1",
  revision_id: "rev-2",
  revision_no: 2,
  manifest_hash: "a".repeat(64),
  query: "What is the retry policy?",
  requested_top_k: 8,
  retrieval_profile: { top_k: 42 },
  result_status: "success",
  error_code: null,
  returned_count: 1,
  truncated: false,
  duration_ms: 120,
  applied_parameters: {
    page_size: 8,
    similarity_threshold: 0.35,
    vector_similarity_weight: 0.7,
    top_k: 42,
  },
  created_by: "owner",
  created_at: "2026-09-15T10:00:00Z",
  items: [
    {
      rank: 1,
      document_id: "doc-1",
      display_name: "runbook.txt",
      content_hash: "b".repeat(64),
      chunk_ref: "c".repeat(24),
      content: "Retry with exponential backoff.",
      score: 0.91,
      rerank_score: null,
      position: { page: 3 },
    },
  ],
};

const revisions = [
  {
    id: "rev-1",
    resource_id: "kb-1",
    revision_no: 1,
    status: "superseded",
    manifest_hash: "1".repeat(64),
    document_count: 1,
    created_at: null,
    published_at: "2026-09-13T00:00:00Z",
  },
  {
    id: "rev-2",
    resource_id: "kb-1",
    revision_no: 2,
    status: "published",
    manifest_hash: "2".repeat(64),
    document_count: 2,
    created_at: null,
    published_at: "2026-09-14T00:00:00Z",
    knowledge_profiles: {
      retrieval: { top_k: 42, similarity_threshold: 0.35 },
    },
  },
];

const runRetrievalTest = vi.fn();
let mockState: {
  revisions: typeof revisions;
  revisionsLoading: boolean;
  revisionsError: Error | null;
  archived: { items: Array<Record<string, unknown>>; total: number };
  archivedLoading: boolean;
  archivedError: Error | null;
  record: Record<string, unknown> | undefined;
  recordLoading: boolean;
  recordError: Error | null;
  runPending: boolean;
  runError: Error | null;
  runData: Record<string, unknown> | undefined;
};

class MockRetrievalTestAccessError extends Error {
  readonly status: number;
  constructor(status: number) {
    super("denied");
    this.status = status;
  }
}

vi.mock("@/core/library", () => ({
  RetrievalTestAccessError: MockRetrievalTestAccessError,
  useKnowledgeRevisions: (_resourceId: string | undefined) => ({
    revisions: mockState.revisions,
    isLoading: mockState.revisionsLoading,
    error: mockState.revisionsError,
  }),
  useRetrievalTests: (_resourceId: string | undefined) => ({
    tests: mockState.archived.items,
    total: mockState.archived.total,
    isLoading: mockState.archivedLoading,
    error: mockState.archivedError,
  }),
  useRetrievalTest: (
    _resourceId: string | undefined,
    testId: string | undefined,
  ) => ({
    data: mockState.record,
    isLoading: mockState.recordLoading,
    error: mockState.recordError,
    testId,
  }),
  useRunRetrievalTest: (_resourceId: string | undefined) => ({
    mutateAsync: runRetrievalTest,
    isPending: mockState.runPending,
    error: mockState.runError,
    data: mockState.runData,
  }),
}));

// ── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  runRetrievalTest.mockReset();
  runRetrievalTest.mockImplementation(async (input: unknown) => input);
  mockState = {
    revisions,
    revisionsLoading: false,
    revisionsError: null,
    archived: { items: [archivedRecord], total: 1 },
    archivedLoading: false,
    archivedError: null,
    record: undefined,
    recordLoading: false,
    recordError: null,
    runPending: false,
    runError: null,
    runData: undefined,
  };
});

afterEach(cleanup);

async function renderPanel(knowledgeBaseId = "kb-1") {
  const { RetrievalTestPanel } =
    await import("@/components/workspace/library/retrieval-test-panel");
  const view = render(<RetrievalTestPanel knowledgeBaseId={knowledgeBaseId} />);
  return view;
}

describe("RetrievalTestPanel", () => {
  test("asks to select a knowledge base first", async () => {
    const { RetrievalTestPanel } =
      await import("@/components/workspace/library/retrieval-test-panel");
    render(<RetrievalTestPanel knowledgeBaseId={undefined} />);
    expect(
      screen.getByText("Select a knowledge base to run retrieval tests"),
    ).toBeTruthy();
  });

  test("reports a knowledge base without published revisions", async () => {
    mockState.revisions = [];
    await renderPanel();
    expect(
      screen.getByText(
        "This knowledge base has no published revision to test yet",
      ),
    ).toBeTruthy();
  });

  test("runs a test with question and bounded K, showing frozen profile", async () => {
    const user = userEvent.setup();
    const { container } = await renderPanel();

    const question = screen.getByLabelText("Question");
    await user.type(question, "What is the retry policy?");
    const topK = screen.getByLabelText("Hits (K)");
    await user.clear(topK);
    await user.type(topK, "5");
    await user.click(screen.getByRole("button", { name: "Run test" }));

    expect(runRetrievalTest).toHaveBeenCalledWith({
      revisionId: "rev-2",
      profileId: "frozen",
      query: "What is the retry policy?",
      topK: 5,
    });
    expect(container.textContent).toContain("manifest");
    expect(container.textContent).toContain("top_k");
  });

  test("submits via keyboard Enter in the question field", async () => {
    const user = userEvent.setup();
    await renderPanel();
    await user.type(screen.getByLabelText("Question"), "hello{Enter}");
    expect(runRetrievalTest).toHaveBeenCalledTimes(1);
  });

  test("renders hits with rank, document, page, scores, and plain-text snippet", async () => {
    mockState.runData = archivedRecord;
    const { container } = await renderPanel();
    expect(container.textContent).toContain("1 hit(s)");
    expect(container.textContent).toContain("runbook.txt");
    expect(container.textContent).toContain("Page 3");
    expect(container.textContent).toContain("0.91");
    expect(container.textContent).toContain("Retry with exponential backoff.");
  });

  test("shows the parameters actually applied to the retrieval", async () => {
    mockState.runData = archivedRecord;
    const { container } = await renderPanel();
    expect(container.textContent).toContain("Applied parameters");
    expect(container.textContent).toContain("similarity_threshold: 0.35");
    expect(container.textContent).toContain("top_k: 42");
  });

  test("renders untrusted snippet content as text, never markup", async () => {
    mockState.runData = {
      ...archivedRecord,
      items: [
        {
          ...archivedRecord.items[0],
          content: '<img src=x onerror="alert(1)"> injected',
        },
      ],
    };
    const { container } = await renderPanel();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
  });

  test("distinguishes empty hits from provider failures", async () => {
    mockState.runData = {
      ...archivedRecord,
      result_status: "empty_hit",
      items: [],
      returned_count: 0,
    };
    const { container } = await renderPanel();
    expect(screen.getByText("No hits for this question.")).toBeTruthy();

    cleanup();
    mockState.runData = {
      ...archivedRecord,
      result_status: "provider_error",
      error_code: "connection_error",
      items: [],
    };
    await renderPanel();
    expect(
      screen.getByText("Retrieval failed (connection_error)."),
    ).toBeTruthy();
  });

  test("maps access loss to the restricted state", async () => {
    mockState.runError = new MockRetrievalTestAccessError(403);
    const { container } = await renderPanel();
    expect(
      screen.getByText("You no longer have access to this knowledge base."),
    ).toBeTruthy();
  });

  test("replays archived records without re-running retrieval", async () => {
    const user = userEvent.setup();
    const { container } = await renderPanel();

    expect(screen.getByText("Archived tests")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /View record/ }));

    expect(runRetrievalTest).not.toHaveBeenCalled();
    // Detail comes from the dedicated record query once a record is selected.
    expect(screen.getByRole("button", { name: /View record/ })).toBeTruthy();
  });

  test("shows the restricted state when an archived record is inaccessible", async () => {
    const user = userEvent.setup();
    mockState.recordError = new MockRetrievalTestAccessError(404);
    await renderPanel();
    await user.click(screen.getByRole("button", { name: /View record/ }));
    expect(
      screen.getByText("This record is no longer accessible."),
    ).toBeTruthy();
  });
});
