import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/workspace"),
}));

vi.mock("next-themes", () => ({
  ThemeProvider: ({ children, ...props }: any) => (
    <div data-testid="next-themes-provider" data-props={JSON.stringify(props)}>
      {children}
    </div>
  ),
}));

import { ThemeProvider } from "@/components/theme-provider";

afterEach(() => {
  cleanup();
});

describe("ThemeProvider", () => {
  test("renders children", () => {
    render(
      <ThemeProvider>
        <span>child content</span>
      </ThemeProvider>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  test("renders NextThemesProvider", () => {
    render(
      <ThemeProvider>
        <span>content</span>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("next-themes-provider")).toBeInTheDocument();
  });

  test("does not force dark theme on non-root paths", () => {
    render(
      <ThemeProvider>
        <span>content</span>
      </ThemeProvider>,
    );
    const provider = screen.getByTestId("next-themes-provider");
    const props = JSON.parse(provider.getAttribute("data-props") || "{}");
    expect(props.forcedTheme).toBeUndefined();
  });
});
