import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  ButtonGroup,
  ButtonGroupText,
  ButtonGroupSeparator,
} from "@/components/ui/button-group";

afterEach(() => {
  cleanup();
});

describe("ButtonGroup", () => {
  test("renders with children", () => {
    render(<ButtonGroup data-testid="bg-main">Group</ButtonGroup>);
    expect(screen.getByText("Group")).toBeInTheDocument();
  });

  test("renders as a div element", () => {
    render(<ButtonGroup data-testid="bg-el">Group</ButtonGroup>);
    expect(screen.getByTestId("bg-el").tagName).toBe("DIV");
  });

  test("has role group", () => {
    render(<ButtonGroup data-testid="bg-role">Group</ButtonGroup>);
    expect(screen.getByTestId("bg-role")).toHaveAttribute("role", "group");
  });

  test("applies data-slot attribute", () => {
    render(<ButtonGroup data-testid="bg-slot">Group</ButtonGroup>);
    expect(screen.getByTestId("bg-slot")).toHaveAttribute(
      "data-slot",
      "button-group",
    );
  });

  test("does not set data-orientation when no orientation prop passed", () => {
    render(<ButtonGroup data-testid="bg-default">Group</ButtonGroup>);
    expect(screen.getByTestId("bg-default")).not.toHaveAttribute(
      "data-orientation",
    );
  });

  test("applies vertical orientation", () => {
    render(
      <ButtonGroup orientation="vertical" data-testid="bg-vertical">
        Group
      </ButtonGroup>,
    );
    expect(screen.getByTestId("bg-vertical")).toHaveAttribute(
      "data-orientation",
      "vertical",
    );
  });

  test("applies custom className", () => {
    render(
      <ButtonGroup className="custom-group" data-testid="bg-custom">
        Group
      </ButtonGroup>,
    );
    expect(screen.getByTestId("bg-custom")).toHaveClass("custom-group");
  });

  test("applies horizontal orientation", () => {
    render(
      <ButtonGroup orientation="horizontal" data-testid="bg-horizontal">
        Group
      </ButtonGroup>,
    );
    expect(screen.getByTestId("bg-horizontal")).toHaveAttribute(
      "data-orientation",
      "horizontal",
    );
  });
});

describe("ButtonGroupText", () => {
  test("renders with text content", () => {
    render(<ButtonGroupText data-testid="bgt">Label</ButtonGroupText>);
    expect(screen.getByText("Label")).toBeInTheDocument();
  });

  test("renders as a div element by default", () => {
    render(<ButtonGroupText data-testid="bgt-el">Label</ButtonGroupText>);
    expect(screen.getByTestId("bgt-el").tagName).toBe("DIV");
  });

  test("applies custom className", () => {
    render(
      <ButtonGroupText className="custom-text" data-testid="bgt-custom">
        Label
      </ButtonGroupText>,
    );
    expect(screen.getByTestId("bgt-custom")).toHaveClass("custom-text");
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <ButtonGroupText asChild data-testid="bgt-slot">
        <span>Slot content</span>
      </ButtonGroupText>,
    );
    expect(screen.getByText("Slot content")).toBeInTheDocument();
  });
});

describe("ButtonGroupSeparator", () => {
  test("renders separator", () => {
    const { container } = render(
      <ButtonGroup>
        <button>Left</button>
        <ButtonGroupSeparator data-testid="separator" />
        <button>Right</button>
      </ButtonGroup>,
    );
    const separator = container.querySelector(
      "[data-slot='button-group-separator']",
    );
    expect(separator).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    const { container } = render(
      <ButtonGroup>
        <button>A</button>
        <ButtonGroupSeparator data-testid="sep" />
        <button>B</button>
      </ButtonGroup>,
    );
    const sep = container.querySelector("[data-slot='button-group-separator']");
    expect(sep).toHaveAttribute("data-slot", "button-group-separator");
  });

  test("renders with default vertical orientation", () => {
    const { container } = render(
      <ButtonGroup>
        <button>A</button>
        <ButtonGroupSeparator />
        <button>B</button>
      </ButtonGroup>,
    );
    const sep = container.querySelector("[data-slot='button-group-separator']");
    expect(sep).toBeInTheDocument();
  });

  test("renders with horizontal orientation", () => {
    const { container } = render(
      <ButtonGroup>
        <button>A</button>
        <ButtonGroupSeparator orientation="horizontal" />
        <button>B</button>
      </ButtonGroup>,
    );
    const sep = container.querySelector("[data-slot='button-group-separator']");
    expect(sep).toBeInTheDocument();
  });
});
