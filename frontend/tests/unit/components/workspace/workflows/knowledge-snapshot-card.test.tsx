import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      workflows: {
        knowledgeSnapshot: {
          title: "Knowledge used by this run",
          entry: (kb: string, no: number | string, hash: string) =>
            `KB ${kb} · v${no} · manifest ${hash}`,
        },
      },
    },
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let KnowledgeSnapshotCard: typeof import("@/components/workspace/workflows/knowledge-snapshot-card").KnowledgeSnapshotCard;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/workflows/knowledge-snapshot-card");
  KnowledgeSnapshotCard = mod.KnowledgeSnapshotCard;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeSnapshotCard", () => {
  test("renders nothing without a snapshot", () => {
    const { container } = render(<KnowledgeSnapshotCard />);
    expect(container).toBeEmptyDOMElement();
  });

  test("renders nothing when no knowledge revisions were frozen", () => {
    const { container } = render(
      <KnowledgeSnapshotCard
        snapshot={{ run_evidence: { knowledge_scope: { revisions: {} } } }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test("renders the frozen revision identities without provider identifiers", () => {
    render(
      <KnowledgeSnapshotCard
        snapshot={{
          run_evidence: {
            knowledge_scope: {
              revisions: {
                "6f1fbe1a-2b3c-4d5e-8f90-1a2b3c4d5e6f": {
                  revision_id: "rev-1",
                  revision_no: 1,
                  manifest_hash:
                    "a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8",
                },
              },
            },
          },
        }}
      />,
    );
    expect(screen.getByText("Knowledge used by this run")).toBeInTheDocument();
    expect(screen.getByText(/KB 6f1fbe1a · v1 · manifest a1b2c3d4e5f6/));
    expect(screen.queryByText(/dataset/i)).not.toBeInTheDocument();
  });
});
