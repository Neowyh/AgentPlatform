import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => (
    <div
      data-testid="react-flow"
      data-nodes={nodes.length}
      data-edges={edges.length}
    />
  ),
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
}));

vi.mock("@xyflow/react/dist/style.css", () => ({}));

vi.mock("@/components/ui/alert", () => ({
  Alert: ({
    children,
    variant,
  }: {
    children: React.ReactNode;
    variant?: string;
  }) => (
    <div data-testid="alert" data-variant={variant}>
      {children}
    </div>
  ),
  AlertTitle: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-title">{children}</div>
  ),
  AlertDescription: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-description">{children}</div>
  ),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    variant,
    className,
  }: {
    children: React.ReactNode;
    variant?: string;
    className?: string;
  }) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

const mockParseFaultTreeArtifact = vi.fn();
vi.mock("@/core/artifacts/fault-tree", () => ({
  parseFaultTreeArtifact: (...args: unknown[]) =>
    mockParseFaultTreeArtifact(...args),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let FaultTreeViewer: typeof import("@/components/workspace/artifacts/fault-tree-viewer").FaultTreeViewer;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/artifacts/fault-tree-viewer");
  FaultTreeViewer = mod.FaultTreeViewer;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("FaultTreeViewer", () => {
  test("shows error alert when parse returns error", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: "Invalid JSON",
      nodes: [],
      edges: [],
      summary: {},
      diagnostics: [],
    });

    render(<FaultTreeViewer content="bad json" />);
    expect(screen.getByTestId("alert")).toBeInTheDocument();
    expect(screen.getByTestId("alert-title")).toHaveTextContent(
      "Fault tree preview unavailable",
    );
    expect(screen.getByTestId("alert-description")).toHaveTextContent(
      "Invalid JSON",
    );
  });

  test("renders ReactFlow when parsing succeeds", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [
        {
          id: "1",
          label: "Top Event",
          kind: "top",
          status: "confirmed",
          confidence: "high",
          probability: "0.1",
          description: "A top event",
        },
      ],
      edges: [{ id: "e1", source: "1", target: "2", label: "causes" }],
      summary: {
        bottomEventCount: 5,
        toVerifyCount: 2,
        rejectedCount: 1,
        confidenceCounts: { high: 3 },
      },
      diagnostics: [],
    });

    render(<FaultTreeViewer content="valid json" />);
    expect(screen.getByTestId("react-flow")).toBeInTheDocument();
  });

  test("displays summary items", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [],
      edges: [],
      summary: {
        bottomEventCount: 10,
        toVerifyCount: 3,
        rejectedCount: 2,
        confidenceCounts: { high: 5 },
      },
      diagnostics: [],
    });

    render(<FaultTreeViewer content="{}" />);
    expect(screen.getByText("Bottom events")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("To verify")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  test("displays diagnostics when present", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [],
      edges: [],
      summary: {
        bottomEventCount: 0,
        toVerifyCount: 0,
        rejectedCount: 0,
        confidenceCounts: { high: 0 },
      },
      diagnostics: ["Warning: missing probability", "Note: estimated values"],
    });

    render(<FaultTreeViewer content="{}" />);
    expect(
      screen.getByText("Warning: missing probability Note: estimated values"),
    ).toBeInTheDocument();
  });

  test("does not display diagnostics when empty", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [],
      edges: [],
      summary: {
        bottomEventCount: 0,
        toVerifyCount: 0,
        rejectedCount: 0,
        confidenceCounts: { high: 0 },
      },
      diagnostics: [],
    });

    const { container } = render(<FaultTreeViewer content="{}" />);
    const diagnosticsEl = container.querySelector(".bg-muted\\/40");
    expect(diagnosticsEl).toBeNull();
  });

  test("renders nodes with badges for non-unknown status", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [
        {
          id: "1",
          label: "Node A",
          kind: "top",
          status: "confirmed",
          confidence: "high",
          probability: "0.5",
          description: "Description A",
        },
      ],
      edges: [],
      summary: {
        bottomEventCount: 0,
        toVerifyCount: 0,
        rejectedCount: 0,
        confidenceCounts: { high: 1 },
      },
      diagnostics: [],
    });

    render(<FaultTreeViewer content="{}" />);
    // The node should be rendered via ReactFlow
    expect(screen.getByTestId("react-flow")).toHaveAttribute("data-nodes", "1");
  });

  test("handles nodes with unknown status", () => {
    mockParseFaultTreeArtifact.mockReturnValue({
      error: null,
      nodes: [
        {
          id: "1",
          label: "Unknown Node",
          kind: "bottom",
          status: "unknown",
          confidence: "unknown",
          probability: null,
          description: null,
        },
      ],
      edges: [],
      summary: {
        bottomEventCount: 1,
        toVerifyCount: 0,
        rejectedCount: 0,
        confidenceCounts: { high: 0 },
      },
      diagnostics: [],
    });

    render(<FaultTreeViewer content="{}" />);
    expect(screen.getByTestId("react-flow")).toBeInTheDocument();
  });
});
