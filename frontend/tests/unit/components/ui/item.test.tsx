import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Item,
  ItemGroup,
  ItemSeparator,
  ItemMedia,
  ItemContent,
  ItemTitle,
  ItemDescription,
  ItemActions,
  ItemHeader,
  ItemFooter,
} from "@/components/ui/item";

afterEach(() => {
  cleanup();
});

describe("Item", () => {
  test("renders with children", () => {
    render(<Item data-testid="item">Content</Item>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  test("renders as a div element", () => {
    render(<Item data-testid="item-el">Content</Item>);
    expect(screen.getByTestId("item-el").tagName).toBe("DIV");
  });

  test("applies data-slot attribute", () => {
    render(<Item data-testid="item-slot">Content</Item>);
    expect(screen.getByTestId("item-slot")).toHaveAttribute(
      "data-slot",
      "item",
    );
  });

  test("applies default variant", () => {
    render(<Item data-testid="item-default">Content</Item>);
    expect(screen.getByTestId("item-default")).toHaveAttribute(
      "data-variant",
      "default",
    );
  });

  test("applies outline variant", () => {
    render(
      <Item variant="outline" data-testid="item-outline">
        Content
      </Item>,
    );
    expect(screen.getByTestId("item-outline")).toHaveAttribute(
      "data-variant",
      "outline",
    );
  });

  test("applies muted variant", () => {
    render(
      <Item variant="muted" data-testid="item-muted">
        Content
      </Item>,
    );
    expect(screen.getByTestId("item-muted")).toHaveAttribute(
      "data-variant",
      "muted",
    );
  });

  test("applies default size", () => {
    render(<Item data-testid="item-size-default">Content</Item>);
    expect(screen.getByTestId("item-size-default")).toHaveAttribute(
      "data-size",
      "default",
    );
  });

  test("applies sm size", () => {
    render(
      <Item size="sm" data-testid="item-size-sm">
        Content
      </Item>,
    );
    expect(screen.getByTestId("item-size-sm")).toHaveAttribute(
      "data-size",
      "sm",
    );
  });

  test("applies custom className", () => {
    render(
      <Item className="custom-item" data-testid="item-custom">
        Content
      </Item>,
    );
    expect(screen.getByTestId("item-custom")).toHaveClass("custom-item");
  });
});

describe("ItemGroup", () => {
  test("renders as a div with role list", () => {
    render(<ItemGroup data-testid="ig">Items</ItemGroup>);
    expect(screen.getByTestId("ig")).toHaveAttribute("role", "list");
  });

  test("applies data-slot attribute", () => {
    render(<ItemGroup data-testid="ig-slot">Items</ItemGroup>);
    expect(screen.getByTestId("ig-slot")).toHaveAttribute(
      "data-slot",
      "item-group",
    );
  });
});

describe("ItemSeparator", () => {
  test("renders a separator", () => {
    render(<ItemSeparator data-testid="is" />);
    expect(screen.getByTestId("is")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemSeparator data-testid="is-slot" />);
    expect(screen.getByTestId("is-slot")).toHaveAttribute(
      "data-slot",
      "item-separator",
    );
  });
});

describe("ItemMedia", () => {
  test("renders with children", () => {
    render(
      <ItemMedia data-testid="im">
        <span>Icon</span>
      </ItemMedia>,
    );
    expect(screen.getByTestId("im")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemMedia data-testid="im-slot">M</ItemMedia>);
    expect(screen.getByTestId("im-slot")).toHaveAttribute(
      "data-slot",
      "item-media",
    );
  });

  test("applies default variant", () => {
    render(<ItemMedia data-testid="im-default">M</ItemMedia>);
    expect(screen.getByTestId("im-default")).toHaveAttribute(
      "data-variant",
      "default",
    );
  });

  test("applies icon variant", () => {
    render(
      <ItemMedia variant="icon" data-testid="im-icon">
        I
      </ItemMedia>,
    );
    expect(screen.getByTestId("im-icon")).toHaveAttribute(
      "data-variant",
      "icon",
    );
  });
});

describe("ItemContent", () => {
  test("renders with children", () => {
    render(<ItemContent data-testid="ic">Content</ItemContent>);
    expect(screen.getByTestId("ic")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemContent data-testid="ic-slot">C</ItemContent>);
    expect(screen.getByTestId("ic-slot")).toHaveAttribute(
      "data-slot",
      "item-content",
    );
  });
});

describe("ItemTitle", () => {
  test("renders with text content", () => {
    render(<ItemTitle data-testid="it">Title</ItemTitle>);
    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemTitle data-testid="it-slot">T</ItemTitle>);
    expect(screen.getByTestId("it-slot")).toHaveAttribute(
      "data-slot",
      "item-title",
    );
  });
});

describe("ItemDescription", () => {
  test("renders with text content", () => {
    render(<ItemDescription data-testid="id">Description</ItemDescription>);
    expect(screen.getByText("Description")).toBeInTheDocument();
  });

  test("renders as a p element", () => {
    render(<ItemDescription data-testid="id-el">Desc</ItemDescription>);
    expect(screen.getByTestId("id-el").tagName).toBe("P");
  });

  test("applies data-slot attribute", () => {
    render(<ItemDescription data-testid="id-slot">D</ItemDescription>);
    expect(screen.getByTestId("id-slot")).toHaveAttribute(
      "data-slot",
      "item-description",
    );
  });
});

describe("ItemActions", () => {
  test("renders with children", () => {
    render(
      <ItemActions data-testid="ia">
        <button>Action</button>
      </ItemActions>,
    );
    expect(screen.getByTestId("ia")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemActions data-testid="ia-slot">A</ItemActions>);
    expect(screen.getByTestId("ia-slot")).toHaveAttribute(
      "data-slot",
      "item-actions",
    );
  });
});

describe("ItemHeader", () => {
  test("renders with children", () => {
    render(
      <ItemHeader data-testid="ih">
        <span>Header</span>
      </ItemHeader>,
    );
    expect(screen.getByTestId("ih")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemHeader data-testid="ih-slot">H</ItemHeader>);
    expect(screen.getByTestId("ih-slot")).toHaveAttribute(
      "data-slot",
      "item-header",
    );
  });
});

describe("ItemFooter", () => {
  test("renders with children", () => {
    render(
      <ItemFooter data-testid="ifoot">
        <span>Footer</span>
      </ItemFooter>,
    );
    expect(screen.getByTestId("ifoot")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(<ItemFooter data-testid="ifoot-slot">F</ItemFooter>);
    expect(screen.getByTestId("ifoot-slot")).toHaveAttribute(
      "data-slot",
      "item-footer",
    );
  });
});
