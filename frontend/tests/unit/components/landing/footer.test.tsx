import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Footer } from "@/components/landing/footer";

afterEach(() => {
  cleanup();
});

describe("Footer", () => {
  test("renders the copyright year", () => {
    render(<Footer />);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(year))).toBeInTheDocument();
  });

  test("renders the iDeer brand in copyright", () => {
    render(<Footer />);
    expect(screen.getByText(/iDeer/)).toBeInTheDocument();
  });

  test("renders the open source quote", () => {
    render(<Footer />);
    expect(screen.getByText(/Originated from Open Source/)).toBeInTheDocument();
  });

  test("renders MIT license text", () => {
    render(<Footer />);
    expect(screen.getByText(/MIT License/)).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(<Footer className="custom-footer" />);
    expect(container.firstChild).toHaveClass("custom-footer");
  });
});
