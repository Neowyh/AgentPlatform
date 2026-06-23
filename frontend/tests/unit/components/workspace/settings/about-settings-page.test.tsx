import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("streamdown", () => ({
  Streamdown: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="streamdown" className={className}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/workspace/settings/about-content", () => ({
  aboutMarkdown: "# About iDeer\n\nThis is about content.",
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let AboutSettingsPage: typeof import("@/components/workspace/settings/about-settings-page").AboutSettingsPage;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/settings/about-settings-page");
  AboutSettingsPage = mod.AboutSettingsPage;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("AboutSettingsPage", () => {
  test("renders the Streamdown component", () => {
    render(<AboutSettingsPage />);
    expect(screen.getByTestId("streamdown")).toBeInTheDocument();
  });

  test("displays the about markdown content", () => {
    render(<AboutSettingsPage />);
    expect(screen.getByText(/About iDeer/)).toBeInTheDocument();
  });

  test("renders without errors", () => {
    expect(() => render(<AboutSettingsPage />)).not.toThrow();
  });
});
