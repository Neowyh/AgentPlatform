import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockRevisions = [
  {
    id: "rev-published",
    resource_id: "kb-1",
    revision_no: 2,
    status: "published",
    manifest_hash:
      "a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8",
    document_count: 1,
    created_at: "2026-09-13T00:00:00Z",
    published_at: "2026-09-13T01:00:00Z",
  },
  {
    id: "rev-draft",
    resource_id: "kb-1",
    revision_no: 3,
    status: "draft",
    manifest_hash:
      "b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1",
    document_count: 1,
    created_at: "2026-09-13T02:00:00Z",
    published_at: null,
  },
];

const listKnowledgeRevisions = vi.fn();

vi.mock("@/core/library/api", () => ({
  listKnowledgeRevisions: (...args: unknown[]) =>
    listKnowledgeRevisions(...args),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

type SelectorModule =
  typeof import("@/components/workspace/capabilities/knowledge-dependency-selector");

let KnowledgeDependencySelector: SelectorModule["KnowledgeDependencySelector"];
let onChangeCalls: unknown[];
let onChange: (next: unknown) => void;

beforeEach(async () => {
  vi.clearAllMocks();
  listKnowledgeRevisions.mockResolvedValue(mockRevisions);
  onChangeCalls = [];
  onChange = (next: unknown) => {
    onChangeCalls.push(next);
  };
  const mod =
    await import("@/components/workspace/capabilities/knowledge-dependency-selector");
  KnowledgeDependencySelector = mod.KnowledgeDependencySelector;
});

afterEach(() => {
  cleanup();
});

// ── Helpers ──────────────────────────────────────────────────────────────────

const KNOWLEDGE_BASES = [
  { id: "kb-1", slug: "research", display_name: "Research" },
];

function renderSelector(props: Record<string, unknown> = {}) {
  return render(
    <KnowledgeDependencySelector
      knowledgeBases={KNOWLEDGE_BASES}
      dependencies={[]}
      onChange={(next) => onChange(next)}
      {...props}
    />,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeDependencySelector", () => {
  test("renders the load error banner when dependencies failed to load", () => {
    renderSelector({ loadError: true });
    expect(
      screen.getByText(
        "Knowledge dependencies could not be loaded. Reload before saving.",
      ),
    ).toBeInTheDocument();
  });

  test("toggling a knowledge base declares a LIVE dependency", async () => {
    const user = userEvent.setup();
    renderSelector();
    await user.click(screen.getByRole("checkbox"));
    expect(onChangeCalls).toEqual([
      [
        {
          resource_id: "kb-1",
          dependency_mode: "live",
          revision_id: null,
          required: true,
          purpose: null,
        },
      ],
    ]);
  });

  test("pinned mode offers only published revisions", async () => {
    const user = userEvent.setup();
    renderSelector({
      dependencies: [
        {
          resource_id: "kb-1",
          dependency_mode: "pinned",
          revision_id: null,
          required: true,
          purpose: null,
        },
      ],
    });
    const select = await screen.findByLabelText("research published revision");
    await user.selectOptions(select, "rev-published");
    expect(onChangeCalls[onChangeCalls.length - 1]).toEqual([
      {
        resource_id: "kb-1",
        dependency_mode: "pinned",
        revision_id: "rev-published",
        required: true,
        purpose: null,
      },
    ]);
    const options = Array.from(select.options).map((option) => option.value);
    expect(options).toContain("rev-published");
    expect(options).not.toContain("rev-draft");
  });

  test("a failed revisions read blocks pinned selection instead of faking empty", async () => {
    const onRevisionsLoadError = vi.fn();
    listKnowledgeRevisions.mockRejectedValue(new Error("boom"));
    renderSelector({
      dependencies: [
        {
          resource_id: "kb-1",
          dependency_mode: "pinned",
          revision_id: null,
          required: true,
          purpose: null,
        },
      ],
      onRevisionsLoadError,
    });
    expect(
      await screen.findByText("Revisions unavailable"),
    ).toBeInTheDocument();
    expect(onRevisionsLoadError).toHaveBeenCalledWith(true);
  });
});
