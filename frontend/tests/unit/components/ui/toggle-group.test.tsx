import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

afterEach(() => {
  cleanup();
});

describe("ToggleGroup", () => {
  test("renders with children", () => {
    render(
      <ToggleGroup type="single" data-testid="tg">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
        <ToggleGroupItem value="b">B</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tg")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <ToggleGroup type="single" data-testid="tg-slot">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tg-slot")).toHaveAttribute(
      "data-slot",
      "toggle-group",
    );
  });

  test("applies custom className", () => {
    render(
      <ToggleGroup type="single" className="custom-tg" data-testid="tg-custom">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tg-custom")).toHaveClass("custom-tg");
  });

  test("applies variant data attribute", () => {
    render(
      <ToggleGroup type="single" variant="outline" data-testid="tg-outline">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tg-outline")).toHaveAttribute(
      "data-variant",
      "outline",
    );
  });

  test("applies size data attribute", () => {
    render(
      <ToggleGroup type="single" size="sm" data-testid="tg-sm">
        <ToggleGroupItem value="a">A</ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tg-sm")).toHaveAttribute("data-size", "sm");
  });
});

describe("ToggleGroupItem", () => {
  test("renders as a button", () => {
    render(
      <ToggleGroup type="single">
        <ToggleGroupItem value="a" data-testid="tgi">
          A
        </ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tgi").tagName).toBe("BUTTON");
  });

  test("applies data-slot attribute", () => {
    render(
      <ToggleGroup type="single">
        <ToggleGroupItem value="a" data-testid="tgi-slot">
          A
        </ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tgi-slot")).toHaveAttribute(
      "data-slot",
      "toggle-group-item",
    );
  });

  test("handles selection in single mode", () => {
    render(
      <ToggleGroup type="single" defaultValue="a">
        <ToggleGroupItem value="a" data-testid="tgi-a">
          A
        </ToggleGroupItem>
        <ToggleGroupItem value="b" data-testid="tgi-b">
          B
        </ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tgi-a")).toHaveAttribute("data-state", "on");
    expect(screen.getByTestId("tgi-b")).toHaveAttribute("data-state", "off");
    fireEvent.click(screen.getByTestId("tgi-b"));
    expect(screen.getByTestId("tgi-a")).toHaveAttribute("data-state", "off");
    expect(screen.getByTestId("tgi-b")).toHaveAttribute("data-state", "on");
  });

  test("handles multiple selection", () => {
    render(
      <ToggleGroup type="multiple" defaultValue={["a"]}>
        <ToggleGroupItem value="a" data-testid="tgi-a">
          A
        </ToggleGroupItem>
        <ToggleGroupItem value="b" data-testid="tgi-b">
          B
        </ToggleGroupItem>
      </ToggleGroup>,
    );
    expect(screen.getByTestId("tgi-a")).toHaveAttribute("data-state", "on");
    expect(screen.getByTestId("tgi-b")).toHaveAttribute("data-state", "off");
    fireEvent.click(screen.getByTestId("tgi-b"));
    expect(screen.getByTestId("tgi-a")).toHaveAttribute("data-state", "on");
    expect(screen.getByTestId("tgi-b")).toHaveAttribute("data-state", "on");
  });
});
