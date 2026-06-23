import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { GithubIcon } from "@/components/workspace/github-icon";

describe("GithubIcon", () => {
  test("renders an SVG element", () => {
    render(<GithubIcon />);
    // SVG with aria-hidden="true" is not in the accessibility tree, so query directly
    const svgEl = document.querySelector("svg");
    expect(svgEl).toBeInTheDocument();
  });

  test("has correct viewBox", () => {
    render(<GithubIcon />);
    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
  });

  test("has correct default dimensions", () => {
    render(<GithubIcon />);
    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("width", "32");
    expect(svg).toHaveAttribute("height", "32");
  });

  test("has aria-hidden attribute", () => {
    render(<GithubIcon />);
    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  test("has fill currentColor", () => {
    render(<GithubIcon />);
    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("fill", "currentColor");
  });

  test("contains a path element", () => {
    render(<GithubIcon />);
    const path = document.querySelector("svg path");
    expect(path).toBeInTheDocument();
  });

  test("passes additional SVG props", () => {
    render(<GithubIcon className="custom-class" data-testid="gh" />);
    const svg = screen.getByTestId("gh");
    expect(svg).toHaveClass("custom-class");
  });

  test("overrides default dimensions via props", () => {
    render(<GithubIcon width={24} height={24} />);
    const svg = document.querySelector("svg");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg).toHaveAttribute("height", "24");
  });
});
