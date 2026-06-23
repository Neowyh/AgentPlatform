import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/components/ui/hover-card";

afterEach(() => {
  cleanup();
});

describe("HoverCard", () => {
  test("renders with trigger", () => {
    render(
      <HoverCard>
        <HoverCardTrigger data-testid="hc-trigger">Hover me</HoverCardTrigger>
      </HoverCard>,
    );
    expect(screen.getByTestId("hc-trigger")).toBeInTheDocument();
  });

  test("trigger has data-slot attribute", () => {
    render(
      <HoverCard>
        <HoverCardTrigger data-testid="hct-slot">Hover</HoverCardTrigger>
      </HoverCard>,
    );
    expect(screen.getByTestId("hct-slot")).toHaveAttribute(
      "data-slot",
      "hover-card-trigger",
    );
  });

  test("renders as an anchor element", () => {
    render(
      <HoverCard>
        <HoverCardTrigger data-testid="hct-tag">Hover</HoverCardTrigger>
      </HoverCard>,
    );
    expect(screen.getByTestId("hct-tag").tagName).toBe("A");
  });
});

describe("HoverCardContent", () => {
  test("renders content when open", () => {
    render(
      <HoverCard open>
        <HoverCardTrigger>Trigger</HoverCardTrigger>
        <HoverCardContent>Hover Content</HoverCardContent>
      </HoverCard>,
    );
    expect(screen.getByText("Hover Content")).toBeInTheDocument();
  });

  test("applies data-slot attribute on content", () => {
    render(
      <HoverCard open>
        <HoverCardTrigger>Trigger</HoverCardTrigger>
        <HoverCardContent data-testid="hcc-slot">Content</HoverCardContent>
      </HoverCard>,
    );
    expect(screen.getByTestId("hcc-slot")).toHaveAttribute(
      "data-slot",
      "hover-card-content",
    );
  });

  test("applies custom className", () => {
    render(
      <HoverCard open>
        <HoverCardTrigger>Trigger</HoverCardTrigger>
        <HoverCardContent className="custom-hcc" data-testid="hcc-custom">
          Content
        </HoverCardContent>
      </HoverCard>,
    );
    expect(screen.getByTestId("hcc-custom")).toHaveClass("custom-hcc");
  });
});
