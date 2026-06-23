import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("next/link", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: React.forwardRef(({ children, href, ...props }: any, ref: any) =>
      React.createElement("a", { ...props, ref, href }, children),
    ),
  };
});

vi.mock("@/core/i18n/server", () => ({
  getI18n: vi.fn().mockResolvedValue({
    locale: "en",
    t: { home: { docs: "Docs", blog: "Blog" } },
  }),
}));

vi.mock("@/core/i18n/locale", () => ({
  type: {},
}));

import { Header } from "@/components/landing/header";

afterEach(() => {
  cleanup();
});

describe("Header", () => {
  test("renders iDeer brand", async () => {
    render(await Header({}));
    expect(screen.getByText("iDeer")).toBeInTheDocument();
  });

  test("renders docs link", async () => {
    render(await Header({}));
    expect(screen.getByText("Docs")).toBeInTheDocument();
  });

  test("renders blog link", async () => {
    render(await Header({}));
    expect(screen.getByText("Blog")).toBeInTheDocument();
  });

  test("applies custom className", async () => {
    const { container } = render(await Header({ className: "custom-header" }));
    const header = container.querySelector("header");
    expect(header).toHaveClass("custom-header");
  });
});
