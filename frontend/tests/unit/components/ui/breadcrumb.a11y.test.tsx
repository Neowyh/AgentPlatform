import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

function BreadcrumbDemo() {
  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink href="/">Home</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbLink href="/docs">Docs</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbPage>Current Page</BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
}

describe("Breadcrumb accessibility", () => {
  it("nav has aria-label='breadcrumb'", () => {
    render(<BreadcrumbDemo />);
    expect(
      screen.getByRole("navigation", { name: /breadcrumb/i }),
    ).toBeInTheDocument();
  });

  it("breadcrumb uses ordered list", () => {
    render(<BreadcrumbDemo />);
    expect(screen.getByRole("list")).toBeInTheDocument();
  });

  it("links are navigable", () => {
    render(<BreadcrumbDemo />);
    expect(screen.getByRole("link", { name: /home/i })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: /docs/i })).toHaveAttribute(
      "href",
      "/docs",
    );
  });

  it("current page has aria-current='page'", () => {
    render(<BreadcrumbDemo />);
    const currentPage = screen.getByText("Current Page");
    expect(currentPage).toHaveAttribute("aria-current", "page");
  });

  it("current page has aria-disabled='true'", () => {
    render(<BreadcrumbDemo />);
    const currentPage = screen.getByText("Current Page");
    expect(currentPage).toHaveAttribute("aria-disabled", "true");
  });

  it("separators are hidden from screen readers", () => {
    render(<BreadcrumbDemo />);
    // BreadcrumbSeparator renders li[role="presentation"][aria-hidden="true"]
    const nav = screen.getByRole("navigation", { name: /breadcrumb/i });
    const listItems = nav.querySelectorAll("li[role='presentation']");
    expect(listItems.length).toBeGreaterThan(0);
    listItems.forEach((sep) => {
      expect(sep).toHaveAttribute("aria-hidden", "true");
    });
  });
});
