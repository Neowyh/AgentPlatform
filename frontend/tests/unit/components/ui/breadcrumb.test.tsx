import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
  BreadcrumbEllipsis,
} from "@/components/ui/breadcrumb";

afterEach(() => {
  cleanup();
});

describe("Breadcrumb", () => {
  test("renders as nav element", () => {
    render(<Breadcrumb data-testid="bc-nav">Content</Breadcrumb>);
    expect(screen.getByTestId("bc-nav").tagName).toBe("NAV");
  });

  test("has aria-label breadcrumb", () => {
    render(<Breadcrumb data-testid="bc-aria">Content</Breadcrumb>);
    expect(screen.getByTestId("bc-aria")).toHaveAttribute(
      "aria-label",
      "breadcrumb",
    );
  });

  test("applies data-slot attribute", () => {
    render(<Breadcrumb data-testid="bc-slot">Content</Breadcrumb>);
    expect(screen.getByTestId("bc-slot")).toHaveAttribute(
      "data-slot",
      "breadcrumb",
    );
  });
});

describe("BreadcrumbList", () => {
  test("renders as ol element", () => {
    render(<BreadcrumbList data-testid="bc-list">Items</BreadcrumbList>);
    expect(screen.getByTestId("bc-list").tagName).toBe("OL");
  });

  test("applies data-slot attribute", () => {
    render(<BreadcrumbList data-testid="bc-list-slot">Items</BreadcrumbList>);
    expect(screen.getByTestId("bc-list-slot")).toHaveAttribute(
      "data-slot",
      "breadcrumb-list",
    );
  });

  test("applies custom className", () => {
    render(
      <BreadcrumbList className="custom-list" data-testid="bc-list-custom">
        Items
      </BreadcrumbList>,
    );
    expect(screen.getByTestId("bc-list-custom")).toHaveClass("custom-list");
  });
});

describe("BreadcrumbItem", () => {
  test("renders as li element", () => {
    render(<BreadcrumbItem data-testid="bc-item">Item</BreadcrumbItem>);
    expect(screen.getByTestId("bc-item").tagName).toBe("LI");
  });

  test("applies data-slot attribute", () => {
    render(<BreadcrumbItem data-testid="bc-item-slot">Item</BreadcrumbItem>);
    expect(screen.getByTestId("bc-item-slot")).toHaveAttribute(
      "data-slot",
      "breadcrumb-item",
    );
  });
});

describe("BreadcrumbLink", () => {
  test("renders as anchor element by default", () => {
    render(
      <BreadcrumbLink href="/home" data-testid="bc-link">
        Home
      </BreadcrumbLink>,
    );
    expect(screen.getByTestId("bc-link").tagName).toBe("A");
    expect(screen.getByTestId("bc-link")).toHaveAttribute("href", "/home");
  });

  test("applies data-slot attribute", () => {
    render(
      <BreadcrumbLink href="/" data-testid="bc-link-slot">
        Link
      </BreadcrumbLink>,
    );
    expect(screen.getByTestId("bc-link-slot")).toHaveAttribute(
      "data-slot",
      "breadcrumb-link",
    );
  });

  test("renders as child element when asChild is true", () => {
    render(
      <BreadcrumbLink asChild>
        <span data-testid="bc-link-child">Link Text</span>
      </BreadcrumbLink>,
    );
    expect(screen.getByTestId("bc-link-child").tagName).toBe("SPAN");
    expect(screen.getByTestId("bc-link-child")).toHaveAttribute(
      "data-slot",
      "breadcrumb-link",
    );
  });
});

describe("BreadcrumbPage", () => {
  test("renders as span element", () => {
    render(<BreadcrumbPage data-testid="bc-page">Current</BreadcrumbPage>);
    expect(screen.getByTestId("bc-page").tagName).toBe("SPAN");
  });

  test("has role link and aria-current page", () => {
    render(<BreadcrumbPage data-testid="bc-page-role">Current</BreadcrumbPage>);
    expect(screen.getByTestId("bc-page-role")).toHaveAttribute("role", "link");
    expect(screen.getByTestId("bc-page-role")).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("applies data-slot attribute", () => {
    render(<BreadcrumbPage data-testid="bc-page-slot">Current</BreadcrumbPage>);
    expect(screen.getByTestId("bc-page-slot")).toHaveAttribute(
      "data-slot",
      "breadcrumb-page",
    );
  });
});

describe("BreadcrumbSeparator", () => {
  test("renders as li element", () => {
    render(<BreadcrumbSeparator data-testid="bc-sep">/</BreadcrumbSeparator>);
    expect(screen.getByTestId("bc-sep").tagName).toBe("LI");
  });

  test("has role presentation and aria-hidden", () => {
    render(
      <BreadcrumbSeparator data-testid="bc-sep-role">/</BreadcrumbSeparator>,
    );
    expect(screen.getByTestId("bc-sep-role")).toHaveAttribute(
      "role",
      "presentation",
    );
    expect(screen.getByTestId("bc-sep-role")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  test("renders default chevron when no children", () => {
    const { container } = render(<BreadcrumbSeparator />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  test("renders custom separator content", () => {
    render(
      <BreadcrumbSeparator data-testid="bc-sep-custom">|</BreadcrumbSeparator>,
    );
    expect(screen.getByTestId("bc-sep-custom")).toHaveTextContent("|");
  });
});

describe("BreadcrumbEllipsis", () => {
  test("renders with More text", () => {
    render(<BreadcrumbEllipsis data-testid="bc-ellipsis" />);
    expect(screen.getByText("More")).toBeInTheDocument();
  });

  test("has role presentation and aria-hidden", () => {
    render(<BreadcrumbEllipsis data-testid="bc-el-role" />);
    expect(screen.getByTestId("bc-el-role")).toHaveAttribute(
      "role",
      "presentation",
    );
    expect(screen.getByTestId("bc-el-role")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  test("renders an svg icon", () => {
    const { container } = render(<BreadcrumbEllipsis />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});

describe("Breadcrumb composition", () => {
  test("renders a full breadcrumb trail", () => {
    render(
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
      </Breadcrumb>,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Docs")).toBeInTheDocument();
    expect(screen.getByText("Current Page")).toBeInTheDocument();
  });
});
