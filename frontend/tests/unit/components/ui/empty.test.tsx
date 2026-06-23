import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
  EmptyMedia,
} from "@/components/ui/empty";

afterEach(() => {
  cleanup();
});

describe("Empty", () => {
  test("renders with children", () => {
    render(
      <Empty data-testid="empty">
        <span>Content</span>
      </Empty>,
    );
    expect(screen.getByTestId("empty")).toBeInTheDocument();
  });

  test("renders as a div element", () => {
    render(<Empty data-testid="empty-el">Content</Empty>);
    expect(screen.getByTestId("empty-el").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(<Empty data-testid="empty-slot">Content</Empty>);
    expect(screen.getByTestId("empty-slot")).toHaveAttribute(
      "data-slot",
      "empty",
    );
  });

  test("applies custom className", () => {
    render(
      <Empty className="custom-empty" data-testid="empty-custom">
        Content
      </Empty>,
    );
    expect(screen.getByTestId("empty-custom")).toHaveClass("custom-empty");
  });

  test("applies default styling classes", () => {
    render(<Empty data-testid="empty-styles">Content</Empty>);
    const el = screen.getByTestId("empty-styles");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("border-dashed");
  });
});

describe("EmptyHeader", () => {
  test("renders with children", () => {
    render(
      <EmptyHeader data-testid="eh">
        <span>Title</span>
      </EmptyHeader>,
    );
    expect(screen.getByTestId("eh")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<EmptyHeader data-testid="eh-slot">Header</EmptyHeader>);
    expect(screen.getByTestId("eh-slot")).toHaveAttribute(
      "data-slot",
      "empty-header",
    );
  });

  test("applies custom className", () => {
    render(
      <EmptyHeader className="custom-eh" data-testid="eh-custom">
        Header
      </EmptyHeader>,
    );
    expect(screen.getByTestId("eh-custom")).toHaveClass("custom-eh");
  });
});

describe("EmptyTitle", () => {
  test("renders with text content", () => {
    render(<EmptyTitle data-testid="et">No results</EmptyTitle>);
    expect(screen.getByText("No results")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<EmptyTitle data-testid="et-slot">Title</EmptyTitle>);
    expect(screen.getByTestId("et-slot")).toHaveAttribute(
      "data-slot",
      "empty-title",
    );
  });

  test("applies default font-medium class", () => {
    render(<EmptyTitle data-testid="et-style">Title</EmptyTitle>);
    expect(screen.getByTestId("et-style").className).toContain("font-medium");
  });
});

describe("EmptyDescription", () => {
  test("renders with text content", () => {
    render(
      <EmptyDescription data-testid="ed">
        Try adjusting filters
      </EmptyDescription>,
    );
    expect(screen.getByText("Try adjusting filters")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<EmptyDescription data-testid="ed-slot">Desc</EmptyDescription>);
    expect(screen.getByTestId("ed-slot")).toHaveAttribute(
      "data-slot",
      "empty-description",
    );
  });

  test("applies custom className", () => {
    render(
      <EmptyDescription className="custom-ed" data-testid="ed-custom">
        Desc
      </EmptyDescription>,
    );
    expect(screen.getByTestId("ed-custom")).toHaveClass("custom-ed");
  });
});

describe("EmptyContent", () => {
  test("renders with children", () => {
    render(
      <EmptyContent data-testid="ec">
        <button>Action</button>
      </EmptyContent>,
    );
    expect(screen.getByTestId("ec")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<EmptyContent data-testid="ec-slot">Content</EmptyContent>);
    expect(screen.getByTestId("ec-slot")).toHaveAttribute(
      "data-slot",
      "empty-content",
    );
  });
});

describe("EmptyMedia", () => {
  test("renders with children", () => {
    render(
      <EmptyMedia data-testid="em">
        <span>Icon</span>
      </EmptyMedia>,
    );
    expect(screen.getByTestId("em")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<EmptyMedia data-testid="em-slot">Media</EmptyMedia>);
    expect(screen.getByTestId("em-slot")).toHaveAttribute(
      "data-slot",
      "empty-icon",
    );
  });

  test("applies default variant", () => {
    render(<EmptyMedia data-testid="em-default">Media</EmptyMedia>);
    expect(screen.getByTestId("em-default")).toHaveAttribute(
      "data-variant",
      "default",
    );
  });

  test("applies icon variant", () => {
    render(
      <EmptyMedia variant="icon" data-testid="em-icon">
        Media
      </EmptyMedia>,
    );
    expect(screen.getByTestId("em-icon")).toHaveAttribute(
      "data-variant",
      "icon",
    );
  });

  test("applies custom className", () => {
    render(
      <EmptyMedia className="custom-em" data-testid="em-custom">
        Media
      </EmptyMedia>,
    );
    expect(screen.getByTestId("em-custom")).toHaveClass("custom-em");
  });
});

describe("Empty composition", () => {
  test("renders a full empty state", () => {
    render(
      <Empty data-testid="empty-full">
        <EmptyHeader>
          <EmptyMedia variant="icon">Icon</EmptyMedia>
          <EmptyTitle>No results</EmptyTitle>
          <EmptyDescription>Try a different search</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <button>Reset</button>
        </EmptyContent>
      </Empty>,
    );
    expect(screen.getByTestId("empty-full")).toBeInTheDocument();
    expect(screen.getByText("No results")).toBeInTheDocument();
    expect(screen.getByText("Try a different search")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset" })).toBeInTheDocument();
  });
});
