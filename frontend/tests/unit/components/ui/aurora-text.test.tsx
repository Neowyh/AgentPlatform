import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { AuroraText } from "@/components/ui/aurora-text";

afterEach(() => {
  cleanup();
});

describe("AuroraText", () => {
  test("renders children text in sr-only span", () => {
    render(<AuroraText>Hello World</AuroraText>);
    const srOnly = screen.getByText("Hello World", { selector: ".sr-only" });
    expect(srOnly).toBeInTheDocument();
  });

  test("renders a span element as root", () => {
    const { container } = render(<AuroraText>Text</AuroraText>);
    const rootSpan = container.querySelector("span.relative.inline-block");
    expect(rootSpan).toBeInTheDocument();
    expect(rootSpan).not.toBeNull();
    expect(rootSpan!.tagName).toBe("SPAN");
  });

  test("renders two child spans (sr-only + aria-hidden)", () => {
    const { container } = render(<AuroraText>Text</AuroraText>);
    const srOnly = container.querySelector(".sr-only");
    const ariaHidden = container.querySelector("[aria-hidden='true']");
    expect(srOnly).toBeInTheDocument();
    expect(ariaHidden).toBeInTheDocument();
  });

  test("applies custom className to root span", () => {
    const { container } = render(
      <AuroraText className="custom-aurora">Text</AuroraText>,
    );
    const rootSpan = container.querySelector("span.relative.inline-block");
    expect(rootSpan).not.toBeNull();
    expect(rootSpan!.className).toContain("custom-aurora");
  });

  test("renders with custom colors", () => {
    const { container } = render(
      <AuroraText colors={["#ff0000", "#00ff00"]}>Colored</AuroraText>,
    );
    expect(container.textContent).toContain("Colored");
  });

  test("renders with custom speed", () => {
    const { container } = render(<AuroraText speed={2}>Fast Text</AuroraText>);
    expect(container.textContent).toContain("Fast Text");
  });

  test("uses default colors and speed", () => {
    const { container } = render(<AuroraText>Default</AuroraText>);
    const animatedSpan = container.querySelector("[aria-hidden='true']");
    expect(animatedSpan).toHaveStyle({
      animationDuration: "10s",
    });
  });
});
