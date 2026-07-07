import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
    prefetch: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Import component after mocks
// ---------------------------------------------------------------------------

import SkillApplicationsPage from "@/app/workspace/admin/skill-applications/page";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SkillApplicationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────────────

  test("renders the redirect message", () => {
    render(<SkillApplicationsPage />);
    expect(screen.getByText("正在跳转到统一审批中心...")).toBeInTheDocument();
  });

  test("renders a centered container", () => {
    render(<SkillApplicationsPage />);
    const container =
      screen.getByText("正在跳转到统一审批中心...").parentElement;
    expect(container).toHaveClass(
      "flex",
      "size-full",
      "items-center",
      "justify-center",
    );
  });

  // ── Redirect behavior ─────────────────────────────────────────────

  test("calls router.replace with the correct URL on mount", () => {
    render(<SkillApplicationsPage />);
    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith(
      "/workspace/admin/visibility-applications",
    );
  });
});
