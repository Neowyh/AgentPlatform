import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupTextarea,
  InputGroupText,
  InputGroupButton,
} from "@/components/ui/input-group";

afterEach(() => {
  cleanup();
});

describe("InputGroup", () => {
  test("renders as a div element", () => {
    render(
      <InputGroup data-testid="ig">
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("ig").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(
      <InputGroup data-testid="ig-slot">
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("ig-slot")).toHaveAttribute(
      "data-slot",
      "input-group",
    );
  });

  test("has role group", () => {
    render(
      <InputGroup data-testid="ig-role">
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("ig-role")).toHaveAttribute("role", "group");
  });

  test("applies custom className", () => {
    render(
      <InputGroup className="custom-ig" data-testid="ig-custom">
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("ig-custom")).toHaveClass("custom-ig");
  });
});

describe("InputGroupAddon", () => {
  test("renders with children", () => {
    render(
      <InputGroup>
        <InputGroupAddon data-testid="iga">Addon</InputGroupAddon>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("iga")).toBeInTheDocument();
    expect(screen.getByText("Addon")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <InputGroup>
        <InputGroupAddon data-testid="iga-slot">Addon</InputGroupAddon>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("iga-slot")).toHaveAttribute(
      "data-slot",
      "input-group-addon",
    );
  });

  test("defaults to inline-start align", () => {
    render(
      <InputGroup>
        <InputGroupAddon data-testid="iga-default">Addon</InputGroupAddon>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("iga-default")).toHaveAttribute(
      "data-align",
      "inline-start",
    );
  });

  test("applies inline-end align", () => {
    render(
      <InputGroup>
        <InputGroupInput />
        <InputGroupAddon align="inline-end" data-testid="iga-end">
          Suffix
        </InputGroupAddon>
      </InputGroup>,
    );
    expect(screen.getByTestId("iga-end")).toHaveAttribute(
      "data-align",
      "inline-end",
    );
  });
});

describe("InputGroupInput", () => {
  test("renders as an input element", () => {
    render(
      <InputGroup>
        <InputGroupInput data-testid="igi" />
      </InputGroup>,
    );
    expect(screen.getByTestId("igi").tagName).toBe("INPUT");
  });

  test("applies data-slot attribute", () => {
    render(
      <InputGroup>
        <InputGroupInput data-testid="igi-slot" />
      </InputGroup>,
    );
    expect(screen.getByTestId("igi-slot")).toHaveAttribute(
      "data-slot",
      "input-group-control",
    );
  });

  test("applies custom className", () => {
    render(
      <InputGroup>
        <InputGroupInput className="custom-igi" data-testid="igi-custom" />
      </InputGroup>,
    );
    expect(screen.getByTestId("igi-custom")).toHaveClass("custom-igi");
  });
});

describe("InputGroupTextarea", () => {
  test("renders as a textarea element", () => {
    render(
      <InputGroup>
        <InputGroupTextarea data-testid="igt" />
      </InputGroup>,
    );
    expect(screen.getByTestId("igt").tagName).toBe("TEXTAREA");
  });

  test("applies data-slot attribute", () => {
    render(
      <InputGroup>
        <InputGroupTextarea data-testid="igt-slot" />
      </InputGroup>,
    );
    expect(screen.getByTestId("igt-slot")).toHaveAttribute(
      "data-slot",
      "input-group-control",
    );
  });
});

describe("InputGroupText", () => {
  test("renders as a span element", () => {
    render(
      <InputGroup>
        <InputGroupText data-testid="igt-text">Label</InputGroupText>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("igt-text").tagName).toBe("SPAN");
  });

  test("renders with text content", () => {
    render(
      <InputGroup>
        <InputGroupText>$</InputGroupText>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByText("$")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <InputGroup>
        <InputGroupText className="custom-igt" data-testid="igt-custom">
          T
        </InputGroupText>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("igt-custom")).toHaveClass("custom-igt");
  });
});

describe("InputGroupButton", () => {
  test("renders as a button", () => {
    render(
      <InputGroup>
        <InputGroupButton data-testid="igb">Action</InputGroupButton>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("igb").tagName).toBe("BUTTON");
  });

  test("renders with text content", () => {
    render(
      <InputGroup>
        <InputGroupButton>Submit</InputGroupButton>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByText("Submit")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <InputGroup>
        <InputGroupButton className="custom-igb" data-testid="igb-custom">
          B
        </InputGroupButton>
        <InputGroupInput />
      </InputGroup>,
    );
    expect(screen.getByTestId("igb-custom")).toHaveClass("custom-igb");
  });
});
