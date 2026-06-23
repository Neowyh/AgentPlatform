import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Plan,
  PlanHeader,
  PlanTitle,
  PlanDescription,
  PlanAction,
  PlanContent,
  PlanFooter,
  PlanTrigger,
} from "@/components/ai-elements/plan";

afterEach(() => {
  cleanup();
});

// Mock Shimmer component
vi.mock("@/components/ai-elements/shimmer", () => ({
  Shimmer: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="shimmer">{children}</span>
  ),
}));

describe("Plan", () => {
  test("renders with children", () => {
    render(
      <Plan data-testid="plan">
        <p>Plan content</p>
      </Plan>,
    );
    expect(screen.getByTestId("plan")).toBeInTheDocument();
    expect(screen.getByText("Plan content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan className="custom-plan" data-testid="plan">
        <p>Content</p>
      </Plan>,
    );
    expect(screen.getByTestId("plan")).toHaveClass("custom-plan");
  });

  test("has shadow-none class", () => {
    render(
      <Plan data-testid="plan">
        <p>Content</p>
      </Plan>,
    );
    expect(screen.getByTestId("plan").className).toContain("shadow-none");
  });
});

describe("PlanHeader", () => {
  test("renders with children", () => {
    render(
      <Plan>
        <PlanHeader data-testid="header">
          <span>Header content</span>
        </PlanHeader>
      </Plan>,
    );
    expect(screen.getByText("Header content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanHeader className="custom-header" data-testid="header">
          <span>Header</span>
        </PlanHeader>
      </Plan>,
    );
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });

  test("has flex and justify-between classes", () => {
    render(
      <Plan>
        <PlanHeader data-testid="header">
          <span>Header</span>
        </PlanHeader>
      </Plan>,
    );
    const el = screen.getByTestId("header");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("justify-between");
  });
});

describe("PlanTitle", () => {
  test("renders children text", () => {
    render(
      <Plan>
        <PlanTitle data-testid="title">Research Plan</PlanTitle>
      </Plan>,
    );
    expect(screen.getByText("Research Plan")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanTitle className="custom-title" data-testid="title">
          Title
        </PlanTitle>
      </Plan>,
    );
    expect(screen.getByTestId("title")).toHaveClass("custom-title");
  });

  test("renders Shimmer when isStreaming=true", () => {
    render(
      <Plan isStreaming>
        <PlanTitle data-testid="title">Streaming title</PlanTitle>
      </Plan>,
    );
    expect(screen.getByTestId("shimmer")).toBeInTheDocument();
    expect(screen.getByText("Streaming title")).toBeInTheDocument();
  });

  test("renders plain text when isStreaming=false", () => {
    render(
      <Plan isStreaming={false}>
        <PlanTitle data-testid="title">Static title</PlanTitle>
      </Plan>,
    );
    expect(screen.queryByTestId("shimmer")).not.toBeInTheDocument();
    expect(screen.getByText("Static title")).toBeInTheDocument();
  });

  test("defaults isStreaming to false", () => {
    render(
      <Plan>
        <PlanTitle data-testid="title">Default title</PlanTitle>
      </Plan>,
    );
    expect(screen.queryByTestId("shimmer")).not.toBeInTheDocument();
  });
});

describe("PlanDescription", () => {
  test("renders children text", () => {
    render(
      <Plan>
        <PlanDescription data-testid="desc">Plan description</PlanDescription>
      </Plan>,
    );
    expect(screen.getByText("Plan description")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanDescription className="custom-desc" data-testid="desc">
          Desc
        </PlanDescription>
      </Plan>,
    );
    expect(screen.getByTestId("desc")).toHaveClass("custom-desc");
  });

  test("renders Shimmer when isStreaming=true", () => {
    render(
      <Plan isStreaming>
        <PlanDescription data-testid="desc">
          Streaming description
        </PlanDescription>
      </Plan>,
    );
    expect(screen.getByTestId("shimmer")).toBeInTheDocument();
  });

  test("renders plain text when isStreaming=false", () => {
    render(
      <Plan isStreaming={false}>
        <PlanDescription data-testid="desc">Static description</PlanDescription>
      </Plan>,
    );
    expect(screen.queryByTestId("shimmer")).not.toBeInTheDocument();
  });

  test("has text-balance class", () => {
    render(
      <Plan>
        <PlanDescription data-testid="desc">Desc</PlanDescription>
      </Plan>,
    );
    expect(screen.getByTestId("desc").className).toContain("text-balance");
  });
});

describe("PlanAction", () => {
  test("renders children", () => {
    render(
      <Plan>
        <PlanAction data-testid="action">
          <button>Action button</button>
        </PlanAction>
      </Plan>,
    );
    expect(screen.getByText("Action button")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanAction className="custom-action" data-testid="action">
          <span>Action</span>
        </PlanAction>
      </Plan>,
    );
    expect(screen.getByTestId("action")).toHaveClass("custom-action");
  });
});

describe("PlanContent", () => {
  test("renders children", () => {
    render(
      <Plan defaultOpen>
        <PlanContent data-testid="content">
          <p>Detailed plan content</p>
        </PlanContent>
      </Plan>,
    );
    expect(screen.getByText("Detailed plan content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan defaultOpen>
        <PlanContent className="custom-content" data-testid="content">
          <p>Content</p>
        </PlanContent>
      </Plan>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("PlanFooter", () => {
  test("renders children", () => {
    render(
      <Plan>
        <PlanFooter data-testid="footer">
          <span>Footer content</span>
        </PlanFooter>
      </Plan>,
    );
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanFooter className="custom-footer" data-testid="footer">
          <span>Footer</span>
        </PlanFooter>
      </Plan>,
    );
    expect(screen.getByTestId("footer")).toHaveClass("custom-footer");
  });
});

describe("PlanTrigger", () => {
  test("renders as a button", () => {
    render(
      <Plan>
        <PlanTrigger data-testid="trigger" />
      </Plan>,
    );
    const btn = screen.getByTestId("trigger");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("renders chevron icon", () => {
    render(
      <Plan>
        <PlanTrigger data-testid="trigger" />
      </Plan>,
    );
    const svg = screen.getByTestId("trigger").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("has sr-only Toggle plan text", () => {
    render(
      <Plan>
        <PlanTrigger data-testid="trigger" />
      </Plan>,
    );
    expect(
      screen.getByText("Toggle plan", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Plan>
        <PlanTrigger className="custom-trigger" data-testid="trigger" />
      </Plan>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });
});

describe("Plan composition", () => {
  test("renders a full plan layout", () => {
    render(
      <Plan defaultOpen data-testid="plan">
        <PlanHeader>
          <PlanTitle data-testid="title">Research Plan</PlanTitle>
          <PlanTrigger data-testid="trigger" />
        </PlanHeader>
        <PlanDescription data-testid="desc">
          A plan to research the topic
        </PlanDescription>
        <PlanContent data-testid="content">
          <p>Step 1: Gather information</p>
          <p>Step 2: Analyze data</p>
        </PlanContent>
        <PlanFooter data-testid="footer">
          <span>Last updated: today</span>
        </PlanFooter>
      </Plan>,
    );

    expect(screen.getByText("Research Plan")).toBeInTheDocument();
    expect(
      screen.getByText("A plan to research the topic"),
    ).toBeInTheDocument();
    expect(screen.getByText("Step 1: Gather information")).toBeInTheDocument();
    expect(screen.getByText("Step 2: Analyze data")).toBeInTheDocument();
    expect(screen.getByText("Last updated: today")).toBeInTheDocument();
  });

  test("streaming state applies shimmer to title and description", () => {
    render(
      <Plan isStreaming>
        <PlanTitle data-testid="title">Streaming title</PlanTitle>
        <PlanDescription data-testid="desc">
          Streaming description
        </PlanDescription>
      </Plan>,
    );

    const shimmers = screen.getAllByTestId("shimmer");
    expect(shimmers).toHaveLength(2);
    expect(shimmers[0]).toHaveTextContent("Streaming title");
    expect(shimmers[1]).toHaveTextContent("Streaming description");
  });
});

describe("usePlan error", () => {
  test("throws when PlanTitle used outside Plan context", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<PlanTitle>test</PlanTitle>);
    }).toThrow("Plan components must be used within Plan");
    spy.mockRestore();
  });
});
