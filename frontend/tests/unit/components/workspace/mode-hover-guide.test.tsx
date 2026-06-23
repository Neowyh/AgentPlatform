import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockT = {
  inputBox: {
    flashMode: "Flash Mode",
    flashModeDescription: "Fast responses with minimal reasoning",
    reasoningMode: "Thinking Mode",
    reasoningModeDescription: "Deep reasoning for complex problems",
    proMode: "Pro Mode",
    proModeDescription: "Professional analysis with detailed output",
    ultraMode: "Ultra Mode",
    ultraModeDescription: "Maximum capability mode",
  },
};

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({ t: mockT }),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: string;
  }) => (
    <div data-testid="tooltip-wrapper" title={content}>
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ModeHoverGuide: typeof import("@/components/workspace/mode-hover-guide").ModeHoverGuide;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/mode-hover-guide");
  ModeHoverGuide = mod.ModeHoverGuide;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ModeHoverGuide", () => {
  test("renders children", () => {
    render(
      <ModeHoverGuide mode="flash">
        <button>Click me</button>
      </ModeHoverGuide>,
    );
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  test("shows flash mode tooltip with title by default", () => {
    render(
      <ModeHoverGuide mode="flash">
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      "Flash Mode: Fast responses with minimal reasoning",
    );
  });

  test("shows thinking mode tooltip", () => {
    render(
      <ModeHoverGuide mode="thinking">
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      "Thinking Mode: Deep reasoning for complex problems",
    );
  });

  test("shows pro mode tooltip", () => {
    render(
      <ModeHoverGuide mode="pro">
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      "Pro Mode: Professional analysis with detailed output",
    );
  });

  test("shows ultra mode tooltip", () => {
    render(
      <ModeHoverGuide mode="ultra">
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      "Ultra Mode: Maximum capability mode",
    );
  });

  test("hides title when showTitle is false", () => {
    render(
      <ModeHoverGuide mode="flash" showTitle={false}>
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      "Fast responses with minimal reasoning",
    );
  });

  test("shows title when showTitle is true", () => {
    render(
      <ModeHoverGuide mode="flash" showTitle={true}>
        <button>Click</button>
      </ModeHoverGuide>,
    );
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "title",
      expect.stringContaining("Flash Mode:"),
    );
  });
});
