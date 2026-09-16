import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

const start = vi.fn();

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
  useStartKnowledgeEvaluation: () => ({ mutateAsync: start, isPending: false }),
  useRetryKnowledgeEvaluation: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

import { EvaluationPanel } from "@/components/workspace/library/evaluation-panel";

describe("EvaluationPanel", () => {
  test("lets the operator choose a profile and case set before starting", async () => {
    render(<EvaluationPanel knowledgeBaseId="kb-1" canModify />);

    expect(screen.getByLabelText("Profile")).toBeInTheDocument();
    expect(screen.getByLabelText("Case set")).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Configured" }),
    ).toBeInTheDocument();
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

    expect(start).toHaveBeenCalledWith({
      revisionId: "rev-1",
      profileId: "configured",
      topK: 8,
      caseIds: ["case-1"],
    });
  });
});
