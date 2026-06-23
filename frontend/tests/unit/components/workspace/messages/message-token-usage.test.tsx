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
        unavailable: "Unavailable",
        unavailableShort: "N/A",
        sharedAttribution: "Shared",
      },
    },
  }),
}));

vi.mock("@/core/messages/usage", () => ({
  accumulateUsage: (messages: Array<{ type: string }>) => {
    const aiMessages = messages.filter((m) => m.type === "ai");
    if (aiMessages.length === 0) return null;
    return {
      inputTokens: 100,
      outputTokens: 50,
      totalTokens: 150,
    };
  },
  formatTokenCount: (count: number) => count.toLocaleString(),
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

// ── Dynamic import ───────────────────────────────────────────────────────────

let MessageTokenUsageList: typeof import("@/components/workspace/messages/message-token-usage").MessageTokenUsageList;
let MessageTokenUsageDebugList: typeof import("@/components/workspace/messages/message-token-usage").MessageTokenUsageDebugList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/messages/message-token-usage");
  MessageTokenUsageList = mod.MessageTokenUsageList;
  MessageTokenUsageDebugList = mod.MessageTokenUsageDebugList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("MessageTokenUsageList", () => {
  test("returns null when not enabled", () => {
    const { container } = render(
      <MessageTokenUsageList enabled={false} messages={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("returns null when no AI messages", () => {
    const { container } = render(
      <MessageTokenUsageList
        enabled={true}
        messages={[{ type: "human", content: "hello" } as never]}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("renders token usage summary when enabled with AI messages", () => {
    render(
      <MessageTokenUsageList
        enabled={true}
        messages={[{ type: "ai", content: "response" } as never]}
      />,
    );
    expect(screen.getByText("Tokens")).toBeInTheDocument();
    expect(screen.getByText("Input: 100")).toBeInTheDocument();
    expect(screen.getByText("Output: 50")).toBeInTheDocument();
    expect(screen.getByText("Total: 150")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <MessageTokenUsageList
        enabled={true}
        className="my-class"
        messages={[{ type: "ai", content: "response" } as never]}
      />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("my-class");
  });
});

describe("MessageTokenUsageDebugList", () => {
  test("returns null when not enabled", () => {
    const { container } = render(
      <MessageTokenUsageDebugList enabled={false} steps={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("returns null when loading", () => {
    const { container } = render(
      <MessageTokenUsageDebugList enabled={true} isLoading={true} steps={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("returns null when steps is empty", () => {
    const { container } = render(
      <MessageTokenUsageDebugList enabled={true} steps={[]} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("renders debug steps when enabled with steps", () => {
    render(
      <MessageTokenUsageDebugList
        enabled={true}
        steps={[
          {
            id: "step-1",
            messageId: "msg-1",
            label: "LLM Call",
            usage: {
              inputTokens: 100,
              outputTokens: 50,
              totalTokens: 150,
            },
            secondaryLabels: ["gpt-4"],
            sharedAttribution: false,
          },
        ]}
      />,
    );
    expect(screen.getByText("LLM Call")).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  test("renders unavailable when no usage data", () => {
    render(
      <MessageTokenUsageDebugList
        enabled={true}
        steps={[
          {
            id: "step-1",
            messageId: "msg-1",
            label: "Tool Call",
            usage: null,
            secondaryLabels: [],
            sharedAttribution: false,
          },
        ]}
      />,
    );
    expect(screen.getByText("Tool Call")).toBeInTheDocument();
    const naElements = screen.getAllByText("N/A");
    expect(naElements.length).toBeGreaterThan(0);
  });

  test("renders shared attribution text", () => {
    render(
      <MessageTokenUsageDebugList
        enabled={true}
        steps={[
          {
            id: "step-1",
            messageId: "msg-1",
            label: "Shared Step",
            usage: {
              inputTokens: 10,
              outputTokens: 5,
              totalTokens: 15,
            },
            secondaryLabels: [],
            sharedAttribution: true,
          },
        ]}
      />,
    );
    expect(screen.getByText("Shared")).toBeInTheDocument();
  });

  test("renders multiple steps", () => {
    render(
      <MessageTokenUsageDebugList
        enabled={true}
        steps={[
          {
            id: "step-1",
            messageId: "msg-1",
            label: "Step 1",
            usage: {
              inputTokens: 10,
              outputTokens: 5,
              totalTokens: 15,
            },
            secondaryLabels: [],
            sharedAttribution: false,
          },
          {
            id: "step-2",
            messageId: "msg-2",
            label: "Step 2",
            usage: {
              inputTokens: 20,
              outputTokens: 10,
              totalTokens: 30,
            },
            secondaryLabels: ["tag1"],
            sharedAttribution: false,
          },
        ]}
      />,
    );
    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Step 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <MessageTokenUsageDebugList
        enabled={true}
        className="debug-class"
        steps={[
          {
            id: "step-1",
            messageId: "msg-1",
            label: "Step",
            usage: null,
            secondaryLabels: [],
            sharedAttribution: false,
          },
        ]}
      />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.getAttribute("class")).toContain("debug-class");
  });
});
