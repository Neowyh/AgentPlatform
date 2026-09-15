import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockRevisions = [
  {
    id: "rev-1",
    resource_id: "kb-1",
    revision_no: 1,
    status: "draft",
    manifest_hash:
      "a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8",
    document_count: 2,
    failure_code: null,
    failure_message: null,
    created_at: "2026-09-13T00:00:00Z",
    published_at: null,
  },
  {
    id: "rev-2",
    resource_id: "kb-1",
    revision_no: 2,
    status: "published",
    manifest_hash:
      "b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1",
    document_count: 3,
    failure_code: null,
    failure_message: null,
    created_at: "2026-09-13T01:00:00Z",
    published_at: "2026-09-13T02:00:00Z",
  },
];

const mockDetail = {
  ...mockRevisions[0],
  documents: [
    {
      document_id: "doc-1",
      content_hash:
        "f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2",
      filename: "guide.txt",
      size_bytes: 15,
      mime_type: "text/plain",
      metadata: {},
    },
  ],
};

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      library: {
        revisionList: {
          selectKnowledgeBase: "Select a knowledge base to view revisions",
          loading: "Loading...",
          loadFailed: "Unable to load revisions.",
          empty: "No revision candidates yet",
          createCandidate: "Create revision candidate",
          creating: "Creating...",
          createFailed:
            "Unable to create a revision candidate. A candidate requires at least one ready document.",
          publishFailed: "Unable to publish this revision.",
          viewDetails: "View details",
          hideDetails: "Hide details",
          documentsAndManifest: (count: number, hash: string) =>
            `${count} documents · manifest ${hash}`,
          publishingStatus: "publishing",
          integrityFlagged: (status: string) =>
            `Reconciliation flagged this revision as ${status}`,
          publish: "Publish",
          publishingAction: "Publishing...",
          publishAria: (no: number) => `Publish v${no}`,
        },
      },
    },
  }),
}));

const createRevision = vi.fn();
const publishRevision = vi.fn();

let mockState: {
  revisions: typeof mockRevisions;
  isLoading: boolean;
  error: Error | null;
  detail: typeof mockDetail;
  detailError: Error | null;
};

vi.mock("@/core/library", () => ({
  useKnowledgeRevisions: (_resourceId: string | undefined) => ({
    revisions: mockState.revisions,
    isLoading: mockState.isLoading,
    error: mockState.error,
  }),
  useKnowledgeRevision: (
    _resourceId: string | undefined,
    _revisionId: string | undefined,
  ) => ({
    data: mockState.detail,
    isLoading: false,
    error: mockState.detailError,
  }),
  useCreateKnowledgeRevision: () => ({
    isPending: false,
    error: null,
    mutateAsync: createRevision,
  }),
  usePublishKnowledgeRevision: () => ({
    isPending: false,
    error: null,
    mutateAsync: publishRevision,
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let RevisionList: typeof import("@/components/workspace/library/revision-list").RevisionList;

beforeEach(async () => {
  vi.clearAllMocks();
  mockState = {
    revisions: mockRevisions,
    isLoading: false,
    error: null,
    detail: mockDetail,
    detailError: null,
  };
  const mod = await import("@/components/workspace/library/revision-list");
  RevisionList = mod.RevisionList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("RevisionList", () => {
  test("prompts to select a knowledge base when none is selected", () => {
    render(<RevisionList />);
    expect(
      screen.getByText("Select a knowledge base to view revisions"),
    ).toBeInTheDocument();
  });

  test("shows a loading state", () => {
    mockState.isLoading = true;
    render(<RevisionList knowledgeBaseId="kb-1" />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("shows an error state", () => {
    mockState.error = new Error("boom");
    render(<RevisionList knowledgeBaseId="kb-1" />);
    expect(screen.getByText("Unable to load revisions.")).toBeInTheDocument();
  });

  test("shows the empty state", () => {
    mockState.revisions = [];
    render(<RevisionList knowledgeBaseId="kb-1" canModify />);
    expect(screen.getByText("No revision candidates yet")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create revision candidate" }),
    ).toBeInTheDocument();
  });

  test("renders revision cards with status and manifest short hash", () => {
    render(<RevisionList knowledgeBaseId="kb-1" />);
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.getByText("published")).toBeInTheDocument();
    expect(screen.getAllByText(/manifest a1b2c3d4e5f6/)).toHaveLength(1);
  });

  test("create is hidden for users who cannot modify", () => {
    render(<RevisionList knowledgeBaseId="kb-1" />);
    expect(
      screen.queryByRole("button", { name: "Create revision candidate" }),
    ).not.toBeInTheDocument();
  });

  test("create button invokes the mutation", async () => {
    const user = userEvent.setup();
    render(<RevisionList knowledgeBaseId="kb-1" canModify />);
    await user.click(
      screen.getByRole("button", { name: "Create revision candidate" }),
    );
    expect(createRevision).toHaveBeenCalledTimes(1);
  });

  test("draft revision offers a publish action for owners", async () => {
    const user = userEvent.setup();
    render(<RevisionList knowledgeBaseId="kb-1" canModify />);
    await user.click(screen.getByRole("button", { name: "Publish v1" }));
    expect(publishRevision).toHaveBeenCalledWith("rev-1");
  });

  test("published revision offers no publish action", () => {
    render(<RevisionList knowledgeBaseId="kb-1" canModify />);
    expect(
      screen.queryByRole("button", { name: "Publish v2" }),
    ).not.toBeInTheDocument();
  });

  test("publish is hidden for users who cannot modify", () => {
    render(<RevisionList knowledgeBaseId="kb-1" />);
    expect(
      screen.queryByRole("button", { name: "Publish v1" }),
    ).not.toBeInTheDocument();
  });

  test("expanding a revision loads its document manifest", async () => {
    const user = userEvent.setup();
    render(<RevisionList knowledgeBaseId="kb-1" />);
    await user.click(
      screen.getAllByRole("button", { name: "View details" })[0]!,
    );
    expect(screen.getByText(/guide\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/f1e2d3c4b5a6/)).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Hide details" });
    await user.click(toggle);
    expect(screen.queryByText(/guide\.txt/)).not.toBeInTheDocument();
  });
});
