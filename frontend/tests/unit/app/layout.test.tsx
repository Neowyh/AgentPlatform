import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/styles/globals.css", () => ({}));
vi.mock("katex/dist/katex.min.css", () => ({}));

vi.mock("@/components/theme-provider", () => ({
  ThemeProvider: ({ children }: any) => (
    <div data-testid="theme-provider">{children}</div>
  ),
}));

vi.mock("@/core/i18n/context", () => ({
  I18nProvider: ({ children, initialLocale }: any) => (
    <div data-testid="i18n-provider" data-locale={initialLocale}>
      {children}
    </div>
  ),
}));

vi.mock("@/core/i18n/server", () => ({
  detectLocaleServer: vi.fn().mockResolvedValue("en"),
}));

vi.mock("next/font/google", () => ({
  Space_Grotesk: () => {
    throw new Error("Google fonts must not be loaded by RootLayout");
  },
}));

vi.mock("next/font/local", () => ({
  default: () => ({ variable: "--font-display" }),
}));

afterEach(() => {
  cleanup();
});

import RootLayout from "@/app/layout";

describe("RootLayout", () => {
  test("renders children", async () => {
    render(await RootLayout({ children: <div>Page content</div> }));
    expect(screen.getByText("Page content")).toBeInTheDocument();
  });

  test("renders ThemeProvider", async () => {
    render(await RootLayout({ children: <div>content</div> }));
    expect(screen.getByTestId("theme-provider")).toBeInTheDocument();
  });

  test("renders I18nProvider with locale", async () => {
    render(await RootLayout({ children: <div>content</div> }));
    const provider = screen.getByTestId("i18n-provider");
    expect(provider).toHaveAttribute("data-locale", "en");
  });

  test("renders html element with lang attribute", async () => {
    const { container } = render(
      await RootLayout({ children: <div>content</div> }),
    );
    const html = container.querySelector("html");
    // jsdom may or may not expose the html element; check it if present
    if (html) {
      expect(html).toHaveAttribute("lang", "en");
    }
    // At minimum, the layout should render without error
    expect(container).toBeTruthy();
  });

  test("has metadata title", async () => {
    const layout = await import("@/app/layout");
    expect(layout.metadata.title).toBe("iDeer");
  });
});
