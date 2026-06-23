import { render, screen, cleanup } from "@testing-library/react";
import type { LanguageModelUsage } from "ai";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Context,
  ContextTrigger,
  ContextContent,
  ContextContentHeader,
  ContextContentBody,
  ContextContentFooter,
  ContextInputUsage,
  ContextOutputUsage,
  ContextReasoningUsage,
  ContextCacheUsage,
} from "@/components/ai-elements/context";

// Mock tokenlens
vi.mock("tokenlens", () => ({
  getUsage: vi.fn().mockReturnValue({
    costUSD: { totalUSD: 0.05 },
  }),
}));

afterEach(() => {
  cleanup();
});

const defaultUsage = {
  usedTokens: 5000,
  maxTokens: 10000,
  usage: {
    inputTokens: 3000,
    outputTokens: 2000,
    reasoningTokens: 500,
    cachedInputTokens: 100,
  } as unknown as LanguageModelUsage,
  modelId: "gpt-4",
};

describe("ContextTrigger", () => {
  test("renders default percentage text", () => {
    render(
      <Context {...defaultUsage}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  test("renders SVG icon", () => {
    render(
      <Context {...defaultUsage}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    const svg = screen.getByTestId("trigger").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("has aria-label on icon", () => {
    render(
      <Context {...defaultUsage}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    const svg = screen.getByTestId("trigger").querySelector("svg");
    expect(svg).toHaveAttribute("aria-label", "Model context usage");
  });

  test("renders custom children instead of default", () => {
    render(
      <Context {...defaultUsage}>
        <ContextTrigger data-testid="trigger">
          <span>Custom trigger</span>
        </ContextTrigger>
      </Context>,
    );
    expect(screen.getByText("Custom trigger")).toBeInTheDocument();
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  test("formats percentage correctly for different values", () => {
    render(
      <Context usedTokens={7500} maxTokens={10000}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  test("renders 0% when no tokens used", () => {
    render(
      <Context usedTokens={0} maxTokens={10000}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  test("renders 100% when all tokens used", () => {
    render(
      <Context usedTokens={10000} maxTokens={10000}>
        <ContextTrigger data-testid="trigger" />
      </Context>,
    );
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});

describe("ContextContent", () => {
  test("renders children inside hover card", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent data-testid="content">
          <p>Content details</p>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Content details")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent className="custom-content" data-testid="content" />
      </Context>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("ContextContentHeader", () => {
  test("renders default header with percentage and token count", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentHeader data-testid="header" />
        </ContextContent>
      </Context>,
    );
    // "50%" appears both in trigger and header, so use getAllByText
    const percentages = screen.getAllByText("50%");
    expect(percentages.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("5K / 10K")).toBeInTheDocument();
  });

  test("renders custom children instead of default", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentHeader data-testid="header">
            <span>Custom header</span>
          </ContextContentHeader>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom header")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentHeader
            className="custom-header"
            data-testid="header"
          />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });

  test("renders a progress bar", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentHeader data-testid="header" />
        </ContextContent>
      </Context>,
    );
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toBeInTheDocument();
  });
});

describe("ContextContentBody", () => {
  test("renders children", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentBody data-testid="body">
            <p>Body content</p>
          </ContextContentBody>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentBody className="custom-body" data-testid="body" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("body")).toHaveClass("custom-body");
  });

  test("has padding class", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentBody data-testid="body">
            <span>Content</span>
          </ContextContentBody>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("body").className).toContain("p-3");
  });
});

describe("ContextContentFooter", () => {
  test("renders total cost text", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentFooter data-testid="footer" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Total cost")).toBeInTheDocument();
  });

  test("renders cost value", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentFooter data-testid="footer" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("$0.05")).toBeInTheDocument();
  });

  test("renders custom children instead of default", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentFooter data-testid="footer">
            <span>Custom footer</span>
          </ContextContentFooter>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom footer")).toBeInTheDocument();
    expect(screen.queryByText("Total cost")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentFooter
            className="custom-footer"
            data-testid="footer"
          />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("footer")).toHaveClass("custom-footer");
  });
});

describe("ContextInputUsage", () => {
  test("renders input tokens and cost", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input-usage" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Input")).toBeInTheDocument();
  });

  test("renders nothing when inputTokens is 0", () => {
    const { container } = render(
      <Context
        usedTokens={0}
        maxTokens={10000}
        usage={
          { inputTokens: 0, outputTokens: 0 } as unknown as LanguageModelUsage
        }
        modelId="gpt-4"
        open
      >
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input-usage" />
        </ContextContent>
      </Context>,
    );
    expect(
      container.querySelector('[data-testid="input-usage"]'),
    ).not.toBeInTheDocument();
  });

  test("renders nothing when usage is undefined", () => {
    const { container } = render(
      <Context usedTokens={0} maxTokens={10000} open>
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input-usage" />
        </ContextContent>
      </Context>,
    );
    expect(
      container.querySelector('[data-testid="input-usage"]'),
    ).not.toBeInTheDocument();
  });

  test("renders custom children", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input-usage">
            <span>Custom input</span>
          </ContextInputUsage>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom input")).toBeInTheDocument();
    expect(screen.queryByText("Input")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage
            className="custom-input"
            data-testid="input-usage"
          />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("input-usage")).toHaveClass("custom-input");
  });
});

describe("ContextOutputUsage", () => {
  test("renders output tokens and cost", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextOutputUsage data-testid="output-usage" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

  test("renders nothing when outputTokens is 0", () => {
    const { container } = render(
      <Context
        usedTokens={0}
        maxTokens={10000}
        usage={
          { inputTokens: 0, outputTokens: 0 } as unknown as LanguageModelUsage
        }
        modelId="gpt-4"
        open
      >
        <ContextTrigger />
        <ContextContent>
          <ContextOutputUsage data-testid="output-usage" />
        </ContextContent>
      </Context>,
    );
    expect(
      container.querySelector('[data-testid="output-usage"]'),
    ).not.toBeInTheDocument();
  });

  test("renders custom children", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextOutputUsage data-testid="output-usage">
            <span>Custom output</span>
          </ContextOutputUsage>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom output")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextOutputUsage
            className="custom-output"
            data-testid="output-usage"
          />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByTestId("output-usage")).toHaveClass("custom-output");
  });
});

describe("ContextReasoningUsage", () => {
  test("renders reasoning tokens and cost", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextReasoningUsage data-testid="reasoning-usage" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
  });

  test("renders nothing when reasoningTokens is 0", () => {
    const { container } = render(
      <Context
        usedTokens={0}
        maxTokens={10000}
        usage={
          {
            inputTokens: 0,
            outputTokens: 0,
            reasoningTokens: 0,
          } as unknown as LanguageModelUsage
        }
        modelId="gpt-4"
        open
      >
        <ContextTrigger />
        <ContextContent>
          <ContextReasoningUsage data-testid="reasoning-usage" />
        </ContextContent>
      </Context>,
    );
    expect(
      container.querySelector('[data-testid="reasoning-usage"]'),
    ).not.toBeInTheDocument();
  });

  test("renders custom children", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextReasoningUsage data-testid="reasoning-usage">
            <span>Custom reasoning</span>
          </ContextReasoningUsage>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom reasoning")).toBeInTheDocument();
  });
});

describe("ContextCacheUsage", () => {
  test("renders cache tokens and cost", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextCacheUsage data-testid="cache-usage" />
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Cache")).toBeInTheDocument();
  });

  test("renders nothing when cachedInputTokens is 0", () => {
    const { container } = render(
      <Context
        usedTokens={0}
        maxTokens={10000}
        usage={
          {
            inputTokens: 0,
            outputTokens: 0,
            cachedInputTokens: 0,
          } as unknown as LanguageModelUsage
        }
        modelId="gpt-4"
        open
      >
        <ContextTrigger />
        <ContextContent>
          <ContextCacheUsage data-testid="cache-usage" />
        </ContextContent>
      </Context>,
    );
    expect(
      container.querySelector('[data-testid="cache-usage"]'),
    ).not.toBeInTheDocument();
  });

  test("renders custom children", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextCacheUsage data-testid="cache-usage">
            <span>Custom cache</span>
          </ContextCacheUsage>
        </ContextContent>
      </Context>,
    );
    expect(screen.getByText("Custom cache")).toBeInTheDocument();
  });
});

describe("Context composition", () => {
  test("renders a full context hover card layout", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger data-testid="trigger" />
        <ContextContent data-testid="content">
          <ContextContentHeader data-testid="header" />
          <ContextContentBody data-testid="body">
            <p>Detailed usage information</p>
          </ContextContentBody>
          <ContextContentFooter data-testid="footer" />
        </ContextContent>
      </Context>,
    );

    // "50%" appears in both trigger and header
    const percentages = screen.getAllByText("50%");
    expect(percentages.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("header")).toBeInTheDocument();
    expect(screen.getByText("Detailed usage information")).toBeInTheDocument();
    expect(screen.getByText("Total cost")).toBeInTheDocument();
  });

  test("renders all usage types together", () => {
    render(
      <Context {...defaultUsage} open>
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input" />
          <ContextOutputUsage data-testid="output" />
          <ContextReasoningUsage data-testid="reasoning" />
          <ContextCacheUsage data-testid="cache" />
        </ContextContent>
      </Context>,
    );

    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.getByText("Output")).toBeInTheDocument();
    expect(screen.getByText("Reasoning")).toBeInTheDocument();
    expect(screen.getByText("Cache")).toBeInTheDocument();
  });

  test("hides usage types with zero tokens", () => {
    const { container } = render(
      <Context
        usedTokens={100}
        maxTokens={1000}
        usage={
          {
            inputTokens: 100,
            outputTokens: 0,
            reasoningTokens: 0,
            cachedInputTokens: 0,
          } as unknown as LanguageModelUsage
        }
        modelId="gpt-4"
        open
      >
        <ContextTrigger />
        <ContextContent>
          <ContextInputUsage data-testid="input" />
          <ContextOutputUsage data-testid="output" />
          <ContextReasoningUsage data-testid="reasoning" />
          <ContextCacheUsage data-testid="cache" />
        </ContextContent>
      </Context>,
    );

    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="output"]'),
    ).not.toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="reasoning"]'),
    ).not.toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="cache"]'),
    ).not.toBeInTheDocument();
  });

  test("formats large token counts in compact notation", () => {
    render(
      <Context usedTokens={1500000} maxTokens={2000000} open>
        <ContextTrigger />
        <ContextContent>
          <ContextContentHeader data-testid="header" />
        </ContextContent>
      </Context>,
    );
    // 75% appears in both trigger and header
    const percentages = screen.getAllByText("75%");
    expect(percentages.length).toBeGreaterThanOrEqual(2);
    // 1.5M / 2M
    expect(screen.getByText("1.5M / 2M")).toBeInTheDocument();
  });
});

describe("useContextValue error", () => {
  test("throws when ContextTrigger used outside Context", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<ContextTrigger />);
    }).toThrow("Context components must be used within Context");
    spy.mockRestore();
  });
});
