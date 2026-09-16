import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  start: vi.fn(),
  comparisonStart: vi.fn(),
  comparisonData: undefined as unknown,
  savePolicy: vi.fn(),
}));

vi.mock("@/core/library", () => ({
  useKnowledgeRevisions: () => ({
    revisions: [{ id: "rev-1", revision_no: 3, status: "published" }],
  }),
  useKnowledgeEvalCases: () => ({
    evalCases: [
      { id: "case-1", question: "Where?" },
      { id: "case-2", question: "Why?" },
    ],
  }),
  useKnowledgeEvaluations: () => ({ evaluations: [] }),
  useKnowledgeEvaluation: () => ({ data: undefined }),
  useStartKnowledgeEvaluation: () => ({
    mutateAsync: mocks.start,
    isPending: false,
  }),
  useRetryKnowledgeEvaluation: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useStartKnowledgeEvaluationComparison: () => ({
    mutateAsync: mocks.comparisonStart,
    isPending: false,
  }),
  useKnowledgeEvaluationComparison: () => ({ data: mocks.comparisonData }),
  useKnowledgeEvaluationPolicy: () => ({ data: { configured: false } }),
  useUpdateKnowledgeEvaluationPolicy: () => ({
    mutateAsync: mocks.savePolicy,
    isPending: false,
    error: null,
  }),
}));

import { EvaluationPanel } from "@/components/workspace/library/evaluation-panel";

describe("EvaluationPanel", () => {
  test("lets the operator choose a profile and case set before starting", async () => {
    render(<EvaluationPanel knowledgeBaseId="kb-1" canModify />);

    expect(screen.getByLabelText("Profile")).toBeInTheDocument();
    expect(screen.getByLabelText("Case set")).toBeInTheDocument();
    expect(
      screen.getAllByRole("option", { name: "Configured" }),
    ).not.toHaveLength(0);
    expect(
      screen.getByRole("option", { name: "Selected cases (0)" }),
    ).toBeInTheDocument();
  });

  test("starts the selected profile and case set", async () => {
    const user = userEvent.setup();
    render(<EvaluationPanel knowledgeBaseId="kb-1" canModify />);

    await user.selectOptions(screen.getByLabelText("Revision"), "rev-1");
    await user.selectOptions(screen.getByLabelText("Profile"), "configured");
    await user.selectOptions(screen.getByLabelText("Case set"), "selected");
    await user.click(screen.getByLabelText("Where?"));
    await user.click(screen.getByRole("button", { name: "Evaluate 1 cases" }));

    expect(mocks.start).toHaveBeenCalledWith({
      revisionId: "rev-1",
      profileId: "configured",
      topK: 8,
      caseIds: ["case-1"],
    });
  });

  test("starts a comparison with the selected case set", async () => {
    const user = userEvent.setup();
    mocks.comparisonStart.mockResolvedValueOnce({ id: "comparison-1" });
    render(<EvaluationPanel knowledgeBaseId="kb-1" canModify />);

    await user.selectOptions(screen.getByLabelText("Side A revision"), "rev-1");
    await user.selectOptions(screen.getByLabelText("Side B revision"), "rev-1");
    await user.selectOptions(screen.getByLabelText("Case set"), "selected");
    await user.click(screen.getByLabelText("Where?"));
    await user.click(screen.getByRole("button", { name: "Compare" }));

    expect(mocks.comparisonStart).toHaveBeenCalledWith({
      leftRevisionId: "rev-1",
      leftProfileId: "frozen",
      rightRevisionId: "rev-1",
      rightProfileId: "configured",
      topK: 8,
      caseIds: ["case-1"],
    });
  });

  test("renders all ranked evidence and comparison metadata", () => {
    mocks.comparisonData = {
      comparison: {
        eligible: true,
        reason: null,
        delta: { expected_hit_rate: 0.5, recall_at_k: 0.25, mrr_at_k: 0.25 },
        cases: [
          {
            case_id: "case-1",
            outcome: "improved",
            left: {
              id: "left-result",
              run_id: "left-run",
              case_id: "case-1",
              case_version_no: 1,
              case_content_hash: "case-hash",
              query: "Where?",
              expected_document_ids: ["doc-1"],
              status: "success",
              error_code: null,
              ranked_items: [
                { rank: 1, document_id: "doc-1", display_name: "Guide" },
                { rank: 2, document_id: "doc-2", display_name: "Appendix" },
              ],
              expected_hit: true,
              recall_at_k: 1,
              mrr_at_k: 1,
            },
            right: null,
          },
        ],
      },
      left: {
        revision_no: 3,
        profile_id: "frozen",
        manifest_hash: "manifest-left",
        profile_hash: "profile-left",
      },
      right: {
        revision_no: 4,
        profile_id: "configured",
        manifest_hash: "manifest-right",
        profile_hash: "profile-right",
      },
    };

    render(<EvaluationPanel knowledgeBaseId="kb-1" canModify />);

    expect(screen.getByText(/A: v3 · frozen/)).toBeInTheDocument();
    expect(screen.getByText(/#1 Guide · #2 Appendix/)).toBeInTheDocument();
    expect(
      screen.getByText(/does not establish single-variable causality/),
    ).toBeInTheDocument();
  });
});
