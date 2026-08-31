import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test } from "vitest";

import {
  Sources,
  SourcesTrigger,
  SourcesContent,
  Source,
} from "@/components/ai-elements/sources";

afterEach(() => {
  cleanup();
});

describe("Sources", () => {
  test("renders as a collapsible container with data-testid", () => {
    render(
      <Sources data-testid="sources-test">
        <p>Content</p>
      </Sources>,
    );
    expect(screen.getByTestId("sources-test")).toBeInTheDocument();
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Sources className="custom-sources" data-testid="sources-test">
        <p>Content</p>
      </Sources>,
    );
    expect(screen.getByTestId("sources-test")).toHaveClass("custom-sources");
  });

  test("applies default not-prose and text-primary classes", () => {
    render(
      <Sources data-testid="sources-test">
        <p>Content</p>
      </Sources>,
    );
    const el = screen.getByTestId("sources-test");
    expect(el.className).toContain("not-prose");
    expect(el.className).toContain("text-primary");
    expect(el.className).toContain("type-body");
  });

  test("has default data-testid of sources-container", () => {
    render(
      <Sources>
        <p>Content</p>
      </Sources>,
    );
    expect(screen.getByTestId("sources-container")).toBeInTheDocument();
  });

  test("spreads additional props", () => {
    render(
      <Sources aria-label="source list" data-testid="sources-test">
        <p>Content</p>
      </Sources>,
    );
    expect(screen.getByTestId("sources-test")).toHaveAttribute(
      "aria-label",
      "source list",
    );
  });
});

describe("SourcesTrigger", () => {
  test("renders default text with count", () => {
    render(
      <Sources>
        <SourcesTrigger count={5} data-testid="trigger-test" />
      </Sources>,
    );
    expect(screen.getByText("Used 5 sources")).toBeInTheDocument();
  });

  test("renders custom children instead of default", () => {
    render(
      <Sources>
        <SourcesTrigger count={3} data-testid="trigger-test">
          Custom trigger text
        </SourcesTrigger>
      </Sources>,
    );
    expect(screen.getByText("Custom trigger text")).toBeInTheDocument();
    expect(screen.queryByText("Used 3 sources")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Sources>
        <SourcesTrigger
          className="custom-trigger"
          count={2}
          data-testid="trigger-test"
        />
      </Sources>,
    );
    expect(screen.getByTestId("trigger-test")).toHaveClass("custom-trigger");
  });

  test("has default data-testid of sources-trigger", () => {
    render(
      <Sources>
        <SourcesTrigger count={1} />
      </Sources>,
    );
    expect(screen.getByTestId("sources-trigger")).toBeInTheDocument();
  });

  test("displays count of 0", () => {
    render(
      <Sources>
        <SourcesTrigger count={0} />
      </Sources>,
    );
    expect(screen.getByText("Used 0 sources")).toBeInTheDocument();
  });
});

describe("SourcesContent", () => {
  test("renders children", () => {
    render(
      <Sources defaultOpen>
        <SourcesContent data-testid="content-test">
          <p>Source content</p>
        </SourcesContent>
      </Sources>,
    );
    expect(screen.getByText("Source content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Sources defaultOpen>
        <SourcesContent className="custom-content" data-testid="content-test">
          <p>Content</p>
        </SourcesContent>
      </Sources>,
    );
    expect(screen.getByTestId("content-test")).toHaveClass("custom-content");
  });

  test("spreads additional props", () => {
    render(
      <Sources defaultOpen>
        <SourcesContent
          aria-label="source list content"
          data-testid="content-test"
        >
          <p>Content</p>
        </SourcesContent>
      </Sources>,
    );
    expect(screen.getByTestId("content-test")).toHaveAttribute(
      "aria-label",
      "source list content",
    );
  });
});

describe("Source", () => {
  test("renders as a link with href", () => {
    render(<Source href="https://example.com" data-testid="source-test" />);
    const link = screen.getByTestId("source-test");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "https://example.com");
  });

  test("opens in new tab with noopener noreferrer", () => {
    render(<Source href="https://example.com" data-testid="source-test" />);
    const link = screen.getByTestId("source-test");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("renders default content with title", () => {
    render(<Source href="https://example.com" title="My Source" />);
    expect(screen.getByText("My Source")).toBeInTheDocument();
    expect(screen.getByTestId("source-link")).toBeInTheDocument();
  });

  test("renders custom children instead of default title", () => {
    render(
      <Source href="https://example.com" title="Should Not Show">
        Custom child content
      </Source>,
    );
    expect(screen.getByText("Custom child content")).toBeInTheDocument();
    expect(screen.queryByText("Should Not Show")).not.toBeInTheDocument();
  });

  test("applies additional props", () => {
    render(
      <Source
        href="https://example.com"
        className="custom-source"
        data-testid="source-test"
      />,
    );
    expect(screen.getByTestId("source-test")).toHaveClass("custom-source");
  });

  test("has default data-testid of source-link", () => {
    render(<Source href="https://example.com" title="Test" />);
    expect(screen.getByTestId("source-link")).toBeInTheDocument();
  });
});

describe("Sources composition", () => {
  test("renders full sources with trigger and content", async () => {
    const user = userEvent.setup();
    render(
      <Sources defaultOpen>
        <SourcesTrigger count={2} />
        <SourcesContent>
          <Source href="https://example.com" title="Example" />
          <Source href="https://test.com" title="Test" />
        </SourcesContent>
      </Sources>,
    );

    expect(screen.getByText("Used 2 sources")).toBeInTheDocument();
    expect(screen.getByText("Example")).toBeInTheDocument();
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  test("toggle reveals content on click", async () => {
    const user = userEvent.setup();
    render(
      <Sources>
        <SourcesTrigger count={1} />
        <SourcesContent>
          <Source href="https://example.com" title="Hidden Source" />
        </SourcesContent>
      </Sources>,
    );

    // Initially content is hidden
    expect(screen.queryByText("Hidden Source")).not.toBeInTheDocument();

    // Click trigger to open
    await user.click(screen.getByTestId("sources-trigger"));
    await waitFor(() => {
      expect(screen.getByText("Hidden Source")).toBeInTheDocument();
    });
  });

  test("renders multiple sources with links", () => {
    render(
      <Sources defaultOpen>
        <SourcesTrigger count={3} />
        <SourcesContent>
          <Source href="https://example.com" title="Source 1" />
          <Source href="https://test.org" title="Source 2" />
          <Source href="https://docs.dev" title="Source 3" />
        </SourcesContent>
      </Sources>,
    );

    const links = screen.getAllByTestId("source-link");
    expect(links).toHaveLength(3);
    expect(links[0]).toHaveAttribute("href", "https://example.com");
    expect(links[1]).toHaveAttribute("href", "https://test.org");
    expect(links[2]).toHaveAttribute("href", "https://docs.dev");
  });

  test("source link contains book icon by default", () => {
    render(<Source href="https://example.com" title="With Icon" />);
    const link = screen.getByTestId("source-link");
    expect(link.querySelector("svg")).toBeInTheDocument();
  });

  test("sources trigger shows correct count for large numbers", () => {
    render(
      <Sources>
        <SourcesTrigger count={42} />
      </Sources>,
    );
    expect(screen.getByText("Used 42 sources")).toBeInTheDocument();
  });

  test("sources content applies animation classes", () => {
    render(
      <Sources defaultOpen>
        <SourcesContent data-testid="content-test">
          <Source href="https://example.com" title="Test" />
        </SourcesContent>
      </Sources>,
    );
    const content = screen.getByTestId("content-test");
    expect(content.className).toContain("slide-in-from-top-2");
  });
});
