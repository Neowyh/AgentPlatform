import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const createEvalCase = vi.fn();
const updateEvalCase = vi.fn();
const deleteEvalCase = vi.fn();

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      library: {
        evalCases: "Eval Cases",
        evalCaseList: {
          selectKnowledgeBase: "Select a knowledge base to maintain eval cases",
          loading: "Loading...",
          loadFailed: "Unable to load eval cases.",
          empty: "No eval cases yet",
          restricted: "Read-only account.",
          createTitle: "New eval case",
          questionLabel: "Question",
          questionPlaceholder: "Enter the regression question",
          expectedDocsLabel: "Expected documents",
          expectedDocsEmpty: "No selectable documents",
          tagsLabel: "Tags (comma separated)",
          tagsPlaceholder: "e.g. regression",
          create: "Create case",
          creating: "Creating...",
          createFailed: "Unable to create the eval case.",
          viewDetails: "View details",
          hideDetails: "Hide details",
          versionsTitle: "Version history",
          versionAndHash: (no: number, hash: string) => `v${no} · hash ${hash}`,
          expectedDocsCount: (count: number) => `${count} expected document(s)`,
          edit: "Edit",
          cancel: "Cancel",
          save: "Save",
          saving: "Saving...",
          updateFailed: "Unable to update the eval case.",
          delete: "Delete",
          deleting: "Deleting...",
          deleteFailed: "Unable to delete the eval case.",
          deleteConfirm: "Delete this eval case?",
          applicabilityTitle: "Target revision applicability",
          applicabilityPlaceholder: "Select a target revision",
          revisionOption: (no: number, status: string) => `v${no} (${status})`,
          applicabilityLoading: "Checking applicability...",
          applicabilityLoadFailed: "Unable to load applicability results.",
          applicable: "Applicable",
          notApplicable: (count: number) =>
            `${count} expected document(s) missing from this revision`,
        },
      },
    },
  }),
}));

let mockState: {
  evalCases: Array<Record<string, unknown>>;
  isLoading: boolean;
  error: Error | null;
  documents: Array<{ id: string; name: string }>;
  revisions: Array<{ id: string; revision_no: number; status: string }>;
  applicability: Record<string, unknown> | undefined;
  applicabilityLoading: boolean;
  applicabilityError: Error | null;
};

vi.mock("@/core/library", () => ({
  useKnowledgeEvalCases: (_resourceId: string | undefined) => ({
    evalCases: mockState.evalCases,
    isLoading: mockState.isLoading,
    error: mockState.error,
  }),
  useKnowledgeEvalCase: () => ({
    data: undefined,
    isLoading: false,
    error: null,
  }),
  useDocuments: () => ({ documents: mockState.documents }),
  useKnowledgeRevisions: () => ({ revisions: mockState.revisions }),
  useEvalCaseRevisionApplicability: () => ({
    data: mockState.applicability,
    isLoading: mockState.applicabilityLoading,
    error: mockState.applicabilityError,
  }),
  useCreateKnowledgeEvalCase: () => ({
    isPending: false,
    error: null,
    mutateAsync: createEvalCase,
  }),
  useUpdateKnowledgeEvalCase: () => ({
    isPending: false,
    error: null,
    mutateAsync: updateEvalCase,
  }),
  useDeleteKnowledgeEvalCase: () => ({
    isPending: false,
    error: null,
    mutateAsync: deleteEvalCase,
  }),
}));

let EvalCaseList: typeof import("@/components/workspace/library/eval-case-list").EvalCaseList;

const caseOne = {
  id: "case-1",
  resource_id: "kb-1",
  question: "What is the retry policy?",
  expected_document_ids: ["doc-1"],
  tags: ["regression"],
  content_hash: "a".repeat(64),
  version_no: 2,
  created_by: "owner",
  updated_by: "owner",
  created_at: null,
  updated_at: null,
};

beforeEach(async () => {
  vi.clearAllMocks();
  mockState = {
    evalCases: [],
    isLoading: false,
    error: null,
    documents: [{ id: "doc-1", name: "guide.txt" }],
    revisions: [{ id: "rev-1", revision_no: 1, status: "published" }],
    applicability: undefined,
    applicabilityLoading: false,
    applicabilityError: null,
  };
  const mod = await import("@/components/workspace/library/eval-case-list");
  EvalCaseList = mod.EvalCaseList;
});

afterEach(() => cleanup());

describe("EvalCaseList", () => {
  test("prompts to select a knowledge base when none is selected", () => {
    render(<EvalCaseList knowledgeBaseId={undefined} canModify />);
    expect(
      screen.getByText("Select a knowledge base to maintain eval cases"),
    ).toBeInTheDocument();
  });

  test("renders loading and error states", async () => {
    mockState.isLoading = true;
    const { unmount } = render(
      <EvalCaseList knowledgeBaseId="kb-1" canModify />,
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    unmount();

    mockState.isLoading = false;
    mockState.error = new Error("boom");
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to load eval cases.",
    );
  });

  test("renders empty state and a restricted note without modify rights", () => {
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify={false} />);
    expect(screen.getByText("No eval cases yet")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Read-only account.");
    expect(screen.queryByText("New eval case")).not.toBeInTheDocument();
  });

  test("creates a case from the form using canonical document ids", async () => {
    const user = userEvent.setup();
    createEvalCase.mockResolvedValueOnce({});
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify />);

    await user.type(
      screen.getByLabelText("Question"),
      "What is the retry policy?",
    );
    await user.click(screen.getByRole("checkbox"));
    await user.type(
      screen.getByLabelText("Tags (comma separated)"),
      "regression, smoke",
    );
    await user.click(screen.getByRole("button", { name: "Create case" }));

    expect(createEvalCase).toHaveBeenCalledWith({
      question: "What is the retry policy?",
      expectedDocumentIds: ["doc-1"],
      tags: ["regression", "smoke"],
    });
  });

  test("blocks submission when question or expected documents are missing", async () => {
    const user = userEvent.setup();
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify />);
    await user.click(screen.getByRole("button", { name: "Create case" }));
    expect(createEvalCase).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Unable to create the eval case.",
    );
  });

  test("lists cases with question, tags, version and expected document names", () => {
    mockState.evalCases = [caseOne];
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify />);
    expect(screen.getByText("What is the retry policy?")).toBeInTheDocument();
    expect(screen.getByText("regression")).toBeInTheDocument();
    expect(screen.getByText("v2 · hash aaaaaaaaaaaa")).toBeInTheDocument();
    expect(
      screen.getByText(/1 expected document\(s\) · guide\.txt/),
    ).toBeInTheDocument();
  });

  test("deletes a case after confirmation", async () => {
    mockState.evalCases = [caseOne];
    deleteEvalCase.mockResolvedValueOnce(undefined);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify />);
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteEvalCase).toHaveBeenCalledWith("case-1");
    confirmSpy.mockRestore();
  });

  test("shows revision applicability including explicit missing documents", async () => {
    mockState.evalCases = [caseOne];
    mockState.applicability = {
      revision_id: "rev-1",
      revision_no: 1,
      status: "published",
      manifest_hash: "b".repeat(64),
      items: [
        {
          case_id: "case-1",
          question: "What is the retry policy?",
          content_hash: "a".repeat(64),
          version_no: 2,
          expected_document_count: 2,
          missing_document_ids: ["doc-9"],
          applicable: false,
        },
      ],
      total: 1,
    };
    const user = userEvent.setup();
    render(<EvalCaseList knowledgeBaseId="kb-1" canModify={false} />);
    await user.selectOptions(
      screen.getByLabelText("Target revision applicability"),
      "rev-1",
    );
    // The question appears both on the case card and in the applicability list.
    expect(screen.getAllByText("What is the retry policy?").length).toBe(2);
    expect(
      screen.getByText(/1 expected document\(s\) missing from this revision/),
    ).toBeInTheDocument();
  });
});
