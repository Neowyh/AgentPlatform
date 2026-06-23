import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Loader } from "@/components/ai-elements/loader";

afterEach(() => {
  cleanup();
});

describe("Loader", () => {
  test("renders a spinning container", () => {
    render(<Loader data-testid="loader" />);
    const loader = screen.getByTestId("loader");
    expect(loader).toBeInTheDocument();
    expect(loader.className).toContain("animate-spin");
  });

  test("renders SVG icon", () => {
    render(<Loader data-testid="loader" />);
    const svg = screen.getByTestId("loader").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("has a title element in SVG", () => {
    render(<Loader data-testid="loader" />);
    expect(screen.getByText("Loader")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<Loader className="custom-loader" data-testid="loader" />);
    expect(screen.getByTestId("loader")).toHaveClass("custom-loader");
  });

  test("uses default size of 16", () => {
    render(<Loader data-testid="loader" />);
    const svg = screen.getByTestId("loader").querySelector("svg");
    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
  });

  test("accepts custom size prop", () => {
    render(<Loader size={24} data-testid="loader" />);
    const svg = screen.getByTestId("loader").querySelector("svg");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg).toHaveAttribute("height", "24");
  });

  test("has inline-flex and items-center classes", () => {
    render(<Loader data-testid="loader" />);
    const loader = screen.getByTestId("loader");
    expect(loader.className).toContain("inline-flex");
    expect(loader.className).toContain("items-center");
    expect(loader.className).toContain("justify-center");
  });

  test("spreads additional div props", () => {
    render(<Loader role="status" aria-label="Loading" data-testid="loader" />);
    const loader = screen.getByTestId("loader");
    expect(loader).toHaveAttribute("role", "status");
    expect(loader).toHaveAttribute("aria-label", "Loading");
  });
});
