import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetFooter,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "@/components/ui/sheet";

afterEach(() => {
  cleanup();
});

describe("Sheet", () => {
  test("renders a sheet trigger", () => {
    render(
      <Sheet>
        <SheetTrigger data-testid="sheet-trigger">Open</SheetTrigger>
      </Sheet>,
    );
    expect(screen.getByTestId("sheet-trigger")).toBeInTheDocument();
  });

  test("trigger applies data-slot attribute", () => {
    render(
      <Sheet>
        <SheetTrigger data-testid="st-trigger">Open</SheetTrigger>
      </Sheet>,
    );
    expect(screen.getByTestId("st-trigger")).toHaveAttribute(
      "data-slot",
      "sheet-trigger",
    );
  });
});

describe("SheetTrigger", () => {
  test("renders a trigger button", () => {
    render(
      <Sheet>
        <SheetTrigger data-testid="st">Open Sheet</SheetTrigger>
      </Sheet>,
    );
    expect(screen.getByTestId("st")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet>
        <SheetTrigger data-testid="st-slot">Open</SheetTrigger>
      </Sheet>,
    );
    expect(screen.getByTestId("st-slot")).toHaveAttribute(
      "data-slot",
      "sheet-trigger",
    );
  });
});

describe("SheetContent", () => {
  test("renders content when open", () => {
    render(
      <Sheet open>
        <SheetContent data-testid="sc">Content</SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent data-testid="sc-slot">Content</SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-slot")).toHaveAttribute(
      "data-slot",
      "sheet-content",
    );
  });

  test("defaults to right side", () => {
    render(
      <Sheet open>
        <SheetContent data-testid="sc-right">Content</SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-right").className).toContain("right-0");
  });

  test("applies left side", () => {
    render(
      <Sheet open>
        <SheetContent side="left" data-testid="sc-left">
          Content
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-left").className).toContain("left-0");
  });

  test("applies top side", () => {
    render(
      <Sheet open>
        <SheetContent side="top" data-testid="sc-top">
          Content
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-top").className).toContain("top-0");
  });

  test("applies bottom side", () => {
    render(
      <Sheet open>
        <SheetContent side="bottom" data-testid="sc-bottom">
          Content
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-bottom").className).toContain("bottom-0");
  });
});

describe("SheetHeader", () => {
  test("renders with children", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetHeader data-testid="sh">Header</SheetHeader>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sh")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetHeader data-testid="sh-slot">H</SheetHeader>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sh-slot")).toHaveAttribute(
      "data-slot",
      "sheet-header",
    );
  });
});

describe("SheetFooter", () => {
  test("renders with children", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetFooter data-testid="sf">Footer</SheetFooter>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sf")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetFooter data-testid="sf-slot">F</SheetFooter>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sf-slot")).toHaveAttribute(
      "data-slot",
      "sheet-footer",
    );
  });
});

describe("SheetTitle", () => {
  test("renders with text content", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetTitle>Sheet Title</SheetTitle>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByText("Sheet Title")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetTitle data-testid="st-title-slot">T</SheetTitle>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("st-title-slot")).toHaveAttribute(
      "data-slot",
      "sheet-title",
    );
  });
});

describe("SheetDescription", () => {
  test("renders with text content", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetDescription>Desc text</SheetDescription>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByText("Desc text")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetDescription data-testid="sd-slot">D</SheetDescription>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sd-slot")).toHaveAttribute(
      "data-slot",
      "sheet-description",
    );
  });
});

describe("SheetClose", () => {
  test("renders a close button", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetClose data-testid="sc-close">X</SheetClose>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-close")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Sheet open>
        <SheetContent>
          <SheetClose data-testid="sc-close-slot">X</SheetClose>
        </SheetContent>
      </Sheet>,
    );
    expect(screen.getByTestId("sc-close-slot")).toHaveAttribute(
      "data-slot",
      "sheet-close",
    );
  });
});
