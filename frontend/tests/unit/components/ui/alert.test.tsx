import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

afterEach(() => {
  cleanup();
});

describe("Alert", () => {
  test("renders with text content", () => {
    render(<Alert>Something happened</Alert>);
    expect(screen.getByText("Something happened")).toBeInTheDocument();
  });

  test("renders as a div element", () => {
    render(<Alert data-testid="alert-el">Test</Alert>);
    expect(screen.getByTestId("alert-el").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(<Alert data-testid="alert-slot">Test</Alert>);
    expect(screen.getByTestId("alert-slot")).toHaveAttribute(
      "data-slot",
      "alert",
    );
  });

  test("has role alert", () => {
    render(<Alert data-testid="alert-role">Test</Alert>);
    expect(screen.getByTestId("alert-role")).toHaveAttribute("role", "alert");
  });

  test("applies default variant classes", () => {
    render(<Alert data-testid="alert-default">Test</Alert>);
    expect(screen.getByTestId("alert-default").className).toContain("bg-card");
  });

  test("applies destructive variant classes", () => {
    render(
      <Alert variant="destructive" data-testid="alert-destructive">
        Error
      </Alert>,
    );
    expect(screen.getByTestId("alert-destructive").className).toContain(
      "text-destructive",
    );
  });

  test("applies custom className", () => {
    render(
      <Alert className="my-alert" data-testid="alert-custom">
        Test
      </Alert>,
    );
    expect(screen.getByTestId("alert-custom")).toHaveClass("my-alert");
  });

  test("forwards additional props", () => {
    render(
      <Alert data-testid="alert-props" id="alert-1">
        Test
      </Alert>,
    );
    expect(screen.getByTestId("alert-props")).toHaveAttribute("id", "alert-1");
  });
});

describe("AlertTitle", () => {
  test("renders with text content", () => {
    render(<AlertTitle>Heads up!</AlertTitle>);
    expect(screen.getByText("Heads up!")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<AlertTitle data-testid="title-slot">Title</AlertTitle>);
    expect(screen.getByTestId("title-slot")).toHaveAttribute(
      "data-slot",
      "alert-title",
    );
  });

  test("applies custom className", () => {
    render(
      <AlertTitle className="custom-title" data-testid="title-custom">
        Title
      </AlertTitle>,
    );
    expect(screen.getByTestId("title-custom")).toHaveClass("custom-title");
  });
});

describe("AlertDescription", () => {
  test("renders with text content", () => {
    render(<AlertDescription>Description text</AlertDescription>);
    expect(screen.getByText("Description text")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<AlertDescription data-testid="desc-slot">Desc</AlertDescription>);
    expect(screen.getByTestId("desc-slot")).toHaveAttribute(
      "data-slot",
      "alert-description",
    );
  });

  test("applies custom className", () => {
    render(
      <AlertDescription className="custom-desc" data-testid="desc-custom">
        Desc
      </AlertDescription>,
    );
    expect(screen.getByTestId("desc-custom")).toHaveClass("custom-desc");
  });
});

describe("Alert composition", () => {
  test("renders full alert with title and description", () => {
    render(
      <Alert data-testid="alert-composition">
        <AlertTitle>Warning</AlertTitle>
        <AlertDescription>Your session will expire soon.</AlertDescription>
      </Alert>,
    );
    expect(screen.getByTestId("alert-composition")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(
      screen.getByText("Your session will expire soon."),
    ).toBeInTheDocument();
  });
});
