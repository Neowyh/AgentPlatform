import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { ArtifactsContextType } from "@/components/workspace/artifacts/context";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockSetArtifactsOpen = vi.fn();

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      common: {
        artifacts: "Artifacts",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
  }) => (
    <div data-testid="tooltip-wrapper" data-tooltip-content={String(content)}>
      {children}
    </div>
  ),
}));

// We need to control what useArtifacts returns for each test.
// Use a mutable reference that tests can override.
let mockArtifactsContext: Partial<ArtifactsContextType> = {};

vi.mock("@/components/workspace/artifacts/context", () => ({
  useArtifacts: () => mockArtifactsContext,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ArtifactTrigger: typeof import("@/components/workspace/artifacts/artifact-trigger").ArtifactTrigger;

beforeEach(async () => {
  vi.clearAllMocks();
  mockArtifactsContext = {
    artifacts: ["file1.py", "file2.ts"],
    setOpen: mockSetArtifactsOpen,
  };
  const mod = await import("@/components/workspace/artifacts/artifact-trigger");
  ArtifactTrigger = mod.ArtifactTrigger;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ArtifactTrigger", () => {
  // ── Null / empty guard ───────────────────────────────────────────────────

  test("renders nothing when artifacts is null", () => {
    mockArtifactsContext = {
      artifacts: null as unknown as string[],
      setOpen: mockSetArtifactsOpen,
    };
    const { container } = render(<ArtifactTrigger />);
    expect(container.firstChild).toBeNull();
  });

  test("renders nothing when artifacts is an empty array", () => {
    mockArtifactsContext = {
      artifacts: [],
      setOpen: mockSetArtifactsOpen,
    };
    const { container } = render(<ArtifactTrigger />);
    expect(container.firstChild).toBeNull();
  });

  // ── Visible rendering ────────────────────────────────────────────────────

  test("renders the trigger button when artifacts exist", () => {
    render(<ArtifactTrigger />);
    expect(screen.getByTestId("artifact-trigger-button")).toBeInTheDocument();
  });

  test("displays the artifacts label text", () => {
    render(<ArtifactTrigger />);
    expect(screen.getByText("Artifacts")).toBeInTheDocument();
  });

  test("renders the Tooltip wrapper with correct content", () => {
    render(<ArtifactTrigger />);
    const tooltip = screen.getByTestId("tooltip-wrapper");
    expect(tooltip).toHaveAttribute(
      "data-tooltip-content",
      "Show artifacts of this conversation",
    );
  });

  test("button has ghost variant attribute", () => {
    render(<ArtifactTrigger />);
    const button = screen.getByTestId("artifact-trigger-button");
    expect(button).toHaveAttribute("data-variant", "ghost");
  });

  // ── Interaction ──────────────────────────────────────────────────────────

  test("clicking the button calls setOpen(true)", () => {
    render(<ArtifactTrigger />);
    fireEvent.click(screen.getByTestId("artifact-trigger-button"));
    expect(mockSetArtifactsOpen).toHaveBeenCalledWith(true);
  });

  test("clicking the button only calls setOpen once", () => {
    render(<ArtifactTrigger />);
    fireEvent.click(screen.getByTestId("artifact-trigger-button"));
    expect(mockSetArtifactsOpen).toHaveBeenCalledTimes(1);
  });

  // ── Single artifact ──────────────────────────────────────────────────────

  test("renders when there is exactly one artifact", () => {
    mockArtifactsContext = {
      artifacts: ["single.py"],
      setOpen: mockSetArtifactsOpen,
    };
    render(<ArtifactTrigger />);
    expect(screen.getByTestId("artifact-trigger-button")).toBeInTheDocument();
  });

  // ── Multiple artifacts ───────────────────────────────────────────────────

  test("renders when there are many artifacts", () => {
    mockArtifactsContext = {
      artifacts: Array.from({ length: 50 }, (_, i) => `file-${i}.txt`),
      setOpen: mockSetArtifactsOpen,
    };
    render(<ArtifactTrigger />);
    expect(screen.getByTestId("artifact-trigger-button")).toBeInTheDocument();
  });

  // ── Icon rendering ──────────────────────────────────────────────────────

  test("renders an svg icon inside the button", () => {
    render(<ArtifactTrigger />);
    const button = screen.getByTestId("artifact-trigger-button");
    const svg = button.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  // ── Re-click behavior ───────────────────────────────────────────────────

  test("multiple clicks call setOpen each time", () => {
    render(<ArtifactTrigger />);
    const button = screen.getByTestId("artifact-trigger-button");
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(mockSetArtifactsOpen).toHaveBeenCalledTimes(3);
    expect(mockSetArtifactsOpen).toHaveBeenCalledWith(true);
  });

  // ── Button class attributes ─────────────────────────────────────────────

  test("button has text-muted-foreground class", () => {
    render(<ArtifactTrigger />);
    const button = screen.getByTestId("artifact-trigger-button");
    expect(button.className).toContain("text-muted-foreground");
  });
});
