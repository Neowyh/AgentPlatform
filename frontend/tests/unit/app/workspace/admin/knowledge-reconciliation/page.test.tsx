import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/core/i18n/hooks", async () => {
  const { zhCN } = await import("@/core/i18n/locales/zh-CN");
  return {
    useI18n: () => ({ t: zhCN, locale: "zh-CN", changeLocale: vi.fn() }),
  };
});

const mockUseKnowledgeReconciliation = vi.fn();
const mockUseRunKnowledgeReconciliation = vi.fn();

vi.mock("@/core/knowledge-admin/hooks", () => ({
  useKnowledgeReconciliation: (...args: unknown[]) =>
    mockUseKnowledgeReconciliation(...args),
  useRunKnowledgeReconciliation: (...args: unknown[]) =>
    mockUseRunKnowledgeReconciliation(...args),
}));

describe("knowledge reconciliation page", () => {
  test("loads the global reconciliation state on the static route", async () => {
    mockUseKnowledgeReconciliation.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        revisions: [
          {
            revision_id: "revision-1",
            revision_no: 1,
            status: "superseded",
            integrity_status: "unverified",
            integrity_checked_at: null,
          },
        ],
        checks: [],
      },
    });
    mockUseRunKnowledgeReconciliation.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });

    const Page = (
      await import("@/app/workspace/admin/knowledge-reconciliation/page")
    ).default;
    render(<Page />);

    expect(mockUseKnowledgeReconciliation).toHaveBeenCalledWith(undefined);
    expect(await screen.findByText("v1 · superseded")).toBeInTheDocument();
  });
});
