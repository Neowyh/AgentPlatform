import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Section } from "@/components/landing/section";

afterEach(() => {
  cleanup();
});

describe("Section", () => {
  test("renders the title", () => {
    render(<Section title="My Section">Content</Section>);
    expect(screen.getByText("My Section")).toBeInTheDocument();
  });

  test("renders the subtitle when provided", () => {
    render(
      <Section title="Title" subtitle="My Subtitle">
        Content
      </Section>,
    );
    expect(screen.getByText("My Subtitle")).toBeInTheDocument();
  });

  test("does not render subtitle when not provided", () => {
    const { container } = render(<Section title="Title">Content</Section>);
    expect(container.querySelectorAll("header > div").length).toBe(1);
  });

  test("renders children", () => {
    render(<Section title="Title">Child Content</Section>);
    expect(screen.getByText("Child Content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <Section title="Title" className="custom-section">
        Content
      </Section>,
    );
    expect(container.firstChild).toHaveClass("custom-section");
  });
});
