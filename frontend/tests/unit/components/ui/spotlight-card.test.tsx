import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import SpotlightCard from "@/components/ui/spotlight-card";

afterEach(() => {
  cleanup();
});

describe("SpotlightCard", () => {
  test("renders with children", () => {
    render(
      <SpotlightCard>
        <span>Card Content</span>
      </SpotlightCard>,
    );
    expect(screen.getByText("Card Content")).toBeInTheDocument();
  });

  test("renders a div with card-spotlight class", () => {
    const { container } = render(
      <SpotlightCard>
        <span>Content</span>
      </SpotlightCard>,
    );
    const card = container.querySelector(".card-spotlight");
    expect(card).toBeInTheDocument();
    expect(card!.tagName).toBe("DIV");
  });

  test("applies custom className", () => {
    const { container } = render(
      <SpotlightCard className="custom-sc">
        <span>Content</span>
      </SpotlightCard>,
    );
    const card = container.querySelector(".card-spotlight");
    expect(card).toHaveClass("custom-sc");
  });

  test("handles mouse move to set CSS variables", () => {
    const { container } = render(
      <SpotlightCard>
        <span>Content</span>
      </SpotlightCard>,
    );
    const card = container.querySelector(".card-spotlight")!;
    // Mock getBoundingClientRect
    card.getBoundingClientRect = vi.fn(() => ({
      left: 100,
      top: 100,
      width: 200,
      height: 200,
      x: 100,
      y: 100,
      right: 300,
      bottom: 300,
      toJSON: vi.fn(),
    }));
    fireEvent.mouseMove(card, { clientX: 150, clientY: 150 });
    expect((card as HTMLElement).style.getPropertyValue("--mouse-x")).toBe(
      "50px",
    );
    expect((card as HTMLElement).style.getPropertyValue("--mouse-y")).toBe(
      "50px",
    );
  });

  test("applies custom spotlightColor", () => {
    const { container } = render(
      <SpotlightCard spotlightColor="rgba(0, 255, 0, 0.5)">
        <span>Green spotlight</span>
      </SpotlightCard>,
    );
    const card = container.querySelector(".card-spotlight")!;
    card.getBoundingClientRect = vi.fn(() => ({
      left: 0,
      top: 0,
      width: 100,
      height: 100,
      x: 0,
      y: 0,
      right: 100,
      bottom: 100,
      toJSON: vi.fn(),
    }));
    fireEvent.mouseMove(card, { clientX: 50, clientY: 50 });
    expect(
      (card as HTMLElement).style.getPropertyValue("--spotlight-color"),
    ).toBe("rgba(0, 255, 0, 0.5)");
  });
});
