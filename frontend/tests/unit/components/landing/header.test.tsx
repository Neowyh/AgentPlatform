import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/core/i18n/server", () => ({
  getI18n: async () => ({
    locale: "zh-CN",
    t: {
      home: { docs: "文档", blog: "博客" },
    },
  }),
}));

import { Header } from "@/components/landing/header";

afterEach(() => {
  cleanup();
});

describe("Header", () => {
  test("renders docs link pointing to /docs/manual", async () => {
    render(await Header({}));
    const link = screen.getByText("文档").closest("a");
    expect(link).toHaveAttribute("href", expect.stringContaining("/docs/manual"));
  });

  test("does not render blog link", async () => {
    render(await Header({}));
    expect(screen.queryByText("Blog")).not.toBeInTheDocument();
    expect(screen.queryByText("博客")).not.toBeInTheDocument();
  });

  test("renders iDeer brand", async () => {
    render(await Header({}));
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });
});
