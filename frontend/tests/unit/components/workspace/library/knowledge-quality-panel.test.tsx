import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const searchParamsState = vi.hoisted(() => ({ kb: null as string | null }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => (key === "kb" ? searchParamsState.kb : null),
  }),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      library: {
        revisions: "Revisions",
        evalCases: "Eval Cases",
        retrievalTestTab: "Retrieval Test",
        evaluation: "Evaluation",
        quality: {
          title: "Revisions & evaluation",
          description:
            "Manage revisions, eval cases, retrieval tests, and evaluations for a knowledge base.",
          selectKnowledgeBase: "Select knowledge base",
        },
      },
    },
  }),
}));

const mockKnowledgeBases = [
  { id: "kb-1", display_name: "Knowledge Base 1", can_modify: true },
  { id: "kb-2", display_name: "Knowledge Base 2", can_modify: false },
];

vi.mock("@/core/library", () => ({
  useKnowledgeBases: () => ({ knowledgeBases: mockKnowledgeBases }),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
  }) => (
    <div data-testid="select" data-value={value}>
      {children}
    </div>
  ),
  SelectTrigger: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <div role="combobox" {...props}>
      {children}
    </div>
  ),
  SelectValue: ({ placeholder }: { placeholder?: string }) => (
    <span>{placeholder}</span>
  ),
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectItem: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <div data-testid="select-item" data-value={value}>
      {children}
    </div>
  ),
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

function mockPanel(testId: string) {
  return ({
    knowledgeBaseId,
    canModify,
  }: {
    knowledgeBaseId?: string;
    canModify?: boolean;
  }) => (
    <div
      data-testid={testId}
      data-kb={knowledgeBaseId}
      data-can-modify={String(canModify)}
    />
  );
}

vi.mock("@/components/workspace/library/revision-list", () => ({
  RevisionList: mockPanel("revision-list"),
}));

vi.mock("@/components/workspace/library/eval-case-list", () => ({
  EvalCaseList: mockPanel("eval-case-list"),
}));

vi.mock("@/components/workspace/library/retrieval-test-panel", () => ({
  RetrievalTestPanel: mockPanel("retrieval-test-panel"),
}));

vi.mock("@/components/workspace/library/evaluation-panel", () => ({
  EvaluationPanel: mockPanel("evaluation-panel"),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let KnowledgeQualityPanel: typeof import("@/components/workspace/library/knowledge-quality-panel").KnowledgeQualityPanel;

beforeEach(async () => {
  vi.clearAllMocks();
  searchParamsState.kb = null;
  const mod =
    await import("@/components/workspace/library/knowledge-quality-panel");
  KnowledgeQualityPanel = mod.KnowledgeQualityPanel;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeQualityPanel", () => {
  test("renders page title and description", () => {
    render(<KnowledgeQualityPanel />);
    expect(screen.getByText("Revisions & evaluation")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Manage revisions, eval cases, retrieval tests, and evaluations for a knowledge base.",
      ),
    ).toBeInTheDocument();
  });

  test("renders a knowledge base selector", () => {
    render(<KnowledgeQualityPanel />);
    expect(
      screen.getByRole("combobox", { name: "Select knowledge base" }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("select-item")).toHaveLength(2);
  });

  test("renders the four governance tabs", () => {
    render(<KnowledgeQualityPanel />);
    const triggers = screen.getAllByTestId("tabs-trigger");
    expect(triggers.map((trigger) => trigger.textContent)).toEqual([
      "Revisions",
      "Eval Cases",
      "Retrieval Test",
      "Evaluation",
    ]);
    expect(screen.getByTestId("revision-list")).toBeInTheDocument();
    expect(screen.getByTestId("eval-case-list")).toBeInTheDocument();
    expect(screen.getByTestId("retrieval-test-panel")).toBeInTheDocument();
    expect(screen.getByTestId("evaluation-panel")).toBeInTheDocument();
  });

  test("defaults to the first knowledge base", () => {
    render(<KnowledgeQualityPanel />);
    expect(screen.getByTestId("select").getAttribute("data-value")).toBe(
      "kb-1",
    );
    expect(screen.getByTestId("revision-list").getAttribute("data-kb")).toBe(
      "kb-1",
    );
    expect(
      screen.getByTestId("revision-list").getAttribute("data-can-modify"),
    ).toBe("true");
  });

  test("preselects the knowledge base from the kb query parameter", () => {
    searchParamsState.kb = "kb-2";
    render(<KnowledgeQualityPanel />);
    expect(screen.getByTestId("select").getAttribute("data-value")).toBe(
      "kb-2",
    );
    expect(screen.getByTestId("eval-case-list").getAttribute("data-kb")).toBe(
      "kb-2",
    );
    expect(
      screen.getByTestId("eval-case-list").getAttribute("data-can-modify"),
    ).toBe("false");
  });

  test("falls back to the first knowledge base for an unknown query parameter", () => {
    searchParamsState.kb = "kb-missing";
    render(<KnowledgeQualityPanel />);
    expect(screen.getByTestId("select").getAttribute("data-value")).toBe(
      "kb-1",
    );
  });
});
