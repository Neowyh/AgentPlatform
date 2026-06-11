import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Badge } from "@/components/ui/badge";

afterEach(() => {
  cleanup();
});

describe("Badge", () => {
  test("renders with text content", () => {
    render(<Badge>New</Badge>);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  test("renders as a span element by default", () => {
    render(<Badge data-testid="badge-span">Badge Element</Badge>);
    expect(screen.getByTestId("badge-span").tagName).toBe("SPAN");
  });

  test("applies data-slot attribute", () => {
    render(<Badge data-testid="badge-slot">Slot Test</Badge>);
    expect(screen.getByTestId("badge-slot")).toHaveAttribute(
      "data-slot",
      "badge",
    );
  });

  test("applies default variant classes", () => {
    render(<Badge data-testid="badge-default">Default Badge</Badge>);
    expect(screen.getByTestId("badge-default").className).toContain(
      "bg-primary",
    );
  });

  test("applies secondary variant classes", () => {
    render(
      <Badge variant="secondary" data-testid="badge-secondary">
        Secondary Badge
      </Badge>,
    );
    expect(screen.getByTestId("badge-secondary").className).toContain(
      "bg-secondary",
    );
  });

  test("applies destructive variant classes", () => {
    render(
      <Badge variant="destructive" data-testid="badge-destructive">
        Error Badge
      </Badge>,
    );
    expect(screen.getByTestId("badge-destructive").className).toContain(
      "bg-destructive",
    );
  });

  test("applies outline variant classes", () => {
    render(
      <Badge variant="outline" data-testid="badge-outline">
        Outline Badge
      </Badge>,
    );
    expect(screen.getByTestId("badge-outline").className).toContain(
      "text-foreground",
    );
  });

  test("applies custom className", () => {
    render(
      <Badge className="my-custom" data-testid="badge-custom">
        Custom Badge
      </Badge>,
    );
    expect(screen.getByTestId("badge-custom")).toHaveClass("my-custom");
  });

  test("renders as child component when asChild is true", () => {
    render(
      <Badge asChild>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a href="/link">Link Badge</a>
      </Badge>,
    );
    const link = screen.getByRole("link", { name: "Link Badge" });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/link");
    expect(link).toHaveAttribute("data-slot", "badge");
  });
});
