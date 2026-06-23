import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";

afterEach(() => {
  cleanup();
});

describe("Collapsible", () => {
  test("renders with children", () => {
    render(
      <Collapsible data-testid="collapsible">
        <CollapsibleTrigger data-testid="trigger">Toggle</CollapsibleTrigger>
        <CollapsibleContent data-testid="content">
          Content here
        </CollapsibleContent>
      </Collapsible>,
    );
    expect(screen.getByTestId("collapsible")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Collapsible data-testid="collapsible-slot">
        <CollapsibleTrigger>Toggle</CollapsibleTrigger>
      </Collapsible>,
    );
    expect(screen.getByTestId("collapsible-slot")).toHaveAttribute(
      "data-slot",
      "collapsible",
    );
  });
});

describe("CollapsibleTrigger", () => {
  test("renders with text content", () => {
    render(
      <Collapsible>
        <CollapsibleTrigger data-testid="trigger-text">
          Show More
        </CollapsibleTrigger>
      </Collapsible>,
    );
    expect(screen.getByText("Show More")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Collapsible>
        <CollapsibleTrigger data-testid="trigger-slot">
          Toggle
        </CollapsibleTrigger>
      </Collapsible>,
    );
    expect(screen.getByTestId("trigger-slot")).toHaveAttribute(
      "data-slot",
      "collapsible-trigger",
    );
  });

  test("applies custom className", () => {
    render(
      <Collapsible>
        <CollapsibleTrigger
          className="custom-trigger"
          data-testid="trigger-custom"
        >
          Toggle
        </CollapsibleTrigger>
      </Collapsible>,
    );
    expect(screen.getByTestId("trigger-custom")).toHaveClass("custom-trigger");
  });
});

describe("CollapsibleContent", () => {
  test("applies data-slot attribute", () => {
    render(
      <Collapsible>
        <CollapsibleTrigger>Toggle</CollapsibleTrigger>
        <CollapsibleContent data-testid="content-slot">
          Hidden content
        </CollapsibleContent>
      </Collapsible>,
    );
    expect(screen.getByTestId("content-slot")).toHaveAttribute(
      "data-slot",
      "collapsible-content",
    );
  });
});
