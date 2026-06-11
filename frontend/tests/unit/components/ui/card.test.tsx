import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

afterEach(() => {
  cleanup();
});

describe("Card", () => {
  test("renders with content", () => {
    render(<Card data-testid="card-main">Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  test("renders as a div element", () => {
    render(<Card data-testid="card-element">Card Element</Card>);
    expect(screen.getByTestId("card-element").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(<Card data-testid="card-slot">Card Slot</Card>);
    expect(screen.getByTestId("card-slot")).toHaveAttribute(
      "data-slot",
      "card",
    );
  });

  test("applies default styling classes", () => {
    render(<Card data-testid="card-styles">Card Styles</Card>);
    const card = screen.getByTestId("card-styles");
    expect(card.className).toContain("flex");
    expect(card.className).toContain("rounded-xl");
    expect(card.className).toContain("border");
  });

  test("applies custom className", () => {
    render(
      <Card className="custom-card" data-testid="card-custom">
        Card Custom
      </Card>,
    );
    expect(screen.getByTestId("card-custom")).toHaveClass("custom-card");
  });
});

describe("CardHeader", () => {
  test("renders with content", () => {
    render(<CardHeader data-testid="header-main">Header Content</CardHeader>);
    expect(screen.getByText("Header Content")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<CardHeader data-testid="header-slot">Header Slot</CardHeader>);
    expect(screen.getByTestId("header-slot")).toHaveAttribute(
      "data-slot",
      "card-header",
    );
  });
});

describe("CardTitle", () => {
  test("renders with content", () => {
    render(<CardTitle data-testid="title-main">My Title</CardTitle>);
    expect(screen.getByText("My Title")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<CardTitle data-testid="title-slot">Title Slot</CardTitle>);
    expect(screen.getByTestId("title-slot")).toHaveAttribute(
      "data-slot",
      "card-title",
    );
  });

  test("applies font-semibold class", () => {
    render(<CardTitle data-testid="title-font">Title Font</CardTitle>);
    expect(screen.getByTestId("title-font").className).toContain(
      "font-semibold",
    );
  });
});

describe("CardDescription", () => {
  test("renders with content", () => {
    render(
      <CardDescription data-testid="desc-main">
        Description text
      </CardDescription>,
    );
    expect(screen.getByText("Description text")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <CardDescription data-testid="desc-slot">
        Description Slot
      </CardDescription>,
    );
    expect(screen.getByTestId("desc-slot")).toHaveAttribute(
      "data-slot",
      "card-description",
    );
  });
});

describe("CardContent", () => {
  test("renders with content", () => {
    render(<CardContent data-testid="content-main">Content Body</CardContent>);
    expect(screen.getByText("Content Body")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<CardContent data-testid="content-slot">Content Slot</CardContent>);
    expect(screen.getByTestId("content-slot")).toHaveAttribute(
      "data-slot",
      "card-content",
    );
  });
});

describe("CardFooter", () => {
  test("renders with content", () => {
    render(<CardFooter data-testid="footer-main">Footer Content</CardFooter>);
    expect(screen.getByText("Footer Content")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<CardFooter data-testid="footer-slot">Footer Slot</CardFooter>);
    expect(screen.getByTestId("footer-slot")).toHaveAttribute(
      "data-slot",
      "card-footer",
    );
  });
});

describe("Card composition", () => {
  test("renders full card with all sub-components", () => {
    render(
      <Card data-testid="card-composition">
        <CardHeader>
          <CardTitle>Card Title</CardTitle>
          <CardDescription>Card Description</CardDescription>
          <CardAction>
            <button>Action Button</button>
          </CardAction>
        </CardHeader>
        <CardContent>Card Body</CardContent>
        <CardFooter>Card Footer</CardFooter>
      </Card>,
    );

    expect(screen.getByTestId("card-composition")).toBeInTheDocument();
    expect(screen.getByText("Card Title")).toBeInTheDocument();
    expect(screen.getByText("Card Description")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Action Button" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Card Body")).toBeInTheDocument();
    expect(screen.getByText("Card Footer")).toBeInTheDocument();
  });
});
