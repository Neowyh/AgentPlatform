import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      tokenUsage: {
        label: "Tokens",
        input: "Input",
        output: "Output",
        total: "Total",
        title: "Token Usage",
        unavailable: "Usage data unavailable",
        note: "Token usage may vary",
        view: "View",
        presets: {
          off: "Off",
          summary: "Summary",
          perTurn: "Per Turn",
          debug: "Debug",
        },
        presetDescriptions: {
          off: "Hide token usage",
          summary: "Show summary",
          perTurn: "Show per turn",
          debug: "Show debug info",
        },
      },
    },
  }),
}));

vi.mock("@/core/messages/usage", () => ({
  formatTokenCount: (count: number) => String(count),
  selectHeaderTokenUsage: ({
    backendUsage,
    messages,
  }: {
    backendUsage: {
      inputTokens: number;
      outputTokens: number;
      totalTokens: number;
    } | null;
    messages: unknown[];
  }) => {
    if (!backendUsage && messages.length === 0) return null;
    return (
      backendUsage || {
        inputTokens: 10,
        outputTokens: 5,
        totalTokens: 15,
      }
    );
  },
}));

vi.mock("@/core/messages/usage-model", () => ({
  getTokenUsageViewPreset: () => "summary",
  tokenUsagePreferencesFromPreset: (preset: string) => ({
    headerTotal: true,
    inlineMode:
      preset === "debug"
        ? "step_debug"
        : preset === "perTurn"
          ? "per_turn"
          : "off",
  }),
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-menu">{children}</div>
  ),
  DropdownMenuTrigger: ({
    children,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <div data-testid="dropdown-trigger">{children}</div>,
  DropdownMenuContent: ({
    children,
  }: {
    children: React.ReactNode;
    side?: string;
    align?: string;
    className?: string;
  }) => <div data-testid="dropdown-content">{children}</div>,
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-label">{children}</div>
  ),
  DropdownMenuRadioGroup: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (v: string) => void;
  }) => (
    <div data-testid="radio-group" data-value={value}>
      {children}
    </div>
  ),
  DropdownMenuRadioItem: ({
    children,
    value,
  }: {
    children: React.ReactNode;
    value: string;
  }) => (
    <div data-testid="radio-item" data-value={value}>
      {children}
    </div>
  ),
  DropdownMenuSeparator: () => <hr data-testid="dropdown-separator" />,
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let TokenUsageIndicator: typeof import("@/components/workspace/token-usage-indicator").TokenUsageIndicator;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/token-usage-indicator");
  TokenUsageIndicator = mod.TokenUsageIndicator;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("TokenUsageIndicator", () => {
  const defaultProps = {
    messages: [] as import("@langchain/langgraph-sdk").Message[],
    preferences: {
      headerTotal: true,
      inlineMode: "off" as const,
    },
    onPreferencesChange: vi.fn(),
  };

  test("returns null when not enabled", () => {
    const { container } = render(
      <TokenUsageIndicator {...defaultProps} enabled={false} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("renders when enabled", () => {
    render(<TokenUsageIndicator {...defaultProps} enabled={true} />);
    expect(screen.getByText("Tokens")).toBeInTheDocument();
  });

  test("renders the dropdown menu", () => {
    render(<TokenUsageIndicator {...defaultProps} enabled={true} />);
    expect(screen.getByTestId("dropdown-menu")).toBeInTheDocument();
  });

  test("shows usage data when backendUsage is provided", () => {
    render(
      <TokenUsageIndicator
        {...defaultProps}
        enabled={true}
        threadId="thread-1"
        backendUsage={{
          inputTokens: 100,
          outputTokens: 50,
          totalTokens: 150,
        }}
      />,
    );
    // formatTokenCount returns String(count), so 150 becomes "150"
    const elements = screen.getAllByText("150");
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  test("shows preset name when headerTotal is false", () => {
    render(
      <TokenUsageIndicator
        {...defaultProps}
        enabled={true}
        preferences={{
          headerTotal: false,
          inlineMode: "off",
        }}
      />,
    );
    const elements = screen.getAllByText("Summary");
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  test("shows dash when no usage data and headerTotal is true", () => {
    render(
      <TokenUsageIndicator
        {...defaultProps}
        enabled={true}
        messages={[]}
        preferences={{
          headerTotal: true,
          inlineMode: "off",
        }}
      />,
    );
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  test("renders all preset radio items", () => {
    render(<TokenUsageIndicator {...defaultProps} enabled={true} />);
    const radioItems = screen.getAllByTestId("radio-item");
    expect(radioItems.length).toBe(4);
  });

  test("applies custom className", () => {
    render(
      <TokenUsageIndicator
        {...defaultProps}
        enabled={true}
        className="my-indicator"
      />,
    );
    // The className should be on the button inside dropdown-trigger
    const trigger = screen.getByTestId("dropdown-trigger");
    const button = trigger.querySelector("button");
    expect(button?.getAttribute("class")).toContain("my-indicator");
  });

  test("renders the note text", () => {
    render(<TokenUsageIndicator {...defaultProps} enabled={true} />);
    expect(screen.getByText("Token usage may vary")).toBeInTheDocument();
  });

  test("renders view label", () => {
    render(<TokenUsageIndicator {...defaultProps} enabled={true} />);
    expect(screen.getByText("View")).toBeInTheDocument();
  });
});
