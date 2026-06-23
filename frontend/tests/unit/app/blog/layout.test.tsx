import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("nextra-theme-docs", () => ({
  Layout: ({ children }: any) => (
    <div data-testid="nextra-layout">{children}</div>
  ),
}));

vi.mock("nextra-theme-docs/style.css", () => ({}));

vi.mock("@/core/blog", () => ({
  getBlogIndexData: vi.fn().mockResolvedValue({ pageMap: [] }),
}));

vi.mock("@/components/landing/header", () => ({
  Header: (props: any) => <div data-testid="header">Header</div>,
}));

vi.mock("@/components/landing/footer", () => ({
  Footer: (props: any) => <div data-testid="footer">Footer</div>,
}));

afterEach(() => {
  cleanup();
});

import BlogLayout from "@/app/blog/layout";

describe("BlogLayout", () => {
  test("renders blog layout with children", async () => {
    render(await BlogLayout({ children: <div>Blog content</div> }));
    expect(screen.getByText("Blog content")).toBeInTheDocument();
  });

  test("renders nextra layout wrapper", async () => {
    render(await BlogLayout({ children: <div>content</div> }));
    expect(screen.getByTestId("nextra-layout")).toBeInTheDocument();
  });
});
