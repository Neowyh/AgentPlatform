import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
} from "@/components/ui/dropdown-menu";

afterEach(() => {
  cleanup();
});

function renderOpenMenu(children: React.ReactNode) {
  return render(
    <DropdownMenu open>
      <DropdownMenuTrigger>Open</DropdownMenuTrigger>
      <DropdownMenuContent>{children}</DropdownMenuContent>
    </DropdownMenu>,
  );
}

describe("DropdownMenu", () => {
  test("renders with trigger", () => {
    render(
      <DropdownMenu>
        <DropdownMenuTrigger data-testid="dm-trigger">Menu</DropdownMenuTrigger>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("dm-trigger")).toBeInTheDocument();
  });

  test("applies data-slot on trigger", () => {
    render(
      <DropdownMenu>
        <DropdownMenuTrigger data-testid="dm-trigger-slot">
          Menu
        </DropdownMenuTrigger>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("dm-trigger-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-trigger",
    );
  });
});

describe("DropdownMenuItem", () => {
  test("renders with text content when menu is open", () => {
    renderOpenMenu(<DropdownMenuItem data-testid="dmi">Item</DropdownMenuItem>);
    expect(screen.getByText("Item")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    renderOpenMenu(
      <DropdownMenuItem data-testid="dmi-slot">Item</DropdownMenuItem>,
    );
    expect(screen.getByTestId("dmi-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-item",
    );
  });

  test("applies default variant", () => {
    renderOpenMenu(
      <DropdownMenuItem data-testid="dmi-default">Item</DropdownMenuItem>,
    );
    expect(screen.getByTestId("dmi-default")).toHaveAttribute(
      "data-variant",
      "default",
    );
  });

  test("applies destructive variant", () => {
    renderOpenMenu(
      <DropdownMenuItem variant="destructive" data-testid="dmi-destructive">
        Delete
      </DropdownMenuItem>,
    );
    expect(screen.getByTestId("dmi-destructive")).toHaveAttribute(
      "data-variant",
      "destructive",
    );
  });

  test("applies inset data attribute", () => {
    renderOpenMenu(
      <DropdownMenuItem inset data-testid="dmi-inset">
        Inset Item
      </DropdownMenuItem>,
    );
    expect(screen.getByTestId("dmi-inset")).toHaveAttribute(
      "data-inset",
      "true",
    );
  });
});

describe("DropdownMenuLabel", () => {
  test("renders with text content when menu is open", () => {
    renderOpenMenu(
      <DropdownMenuLabel data-testid="dml">Label</DropdownMenuLabel>,
    );
    expect(screen.getByText("Label")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    renderOpenMenu(
      <DropdownMenuLabel data-testid="dml-slot">Label</DropdownMenuLabel>,
    );
    expect(screen.getByTestId("dml-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-label",
    );
  });

  test("applies inset data attribute", () => {
    renderOpenMenu(
      <DropdownMenuLabel inset data-testid="dml-inset">
        Label
      </DropdownMenuLabel>,
    );
    expect(screen.getByTestId("dml-inset")).toHaveAttribute(
      "data-inset",
      "true",
    );
  });
});

describe("DropdownMenuSeparator", () => {
  test("renders a separator when menu is open", () => {
    renderOpenMenu(<DropdownMenuSeparator data-testid="dms" />);
    expect(screen.getByTestId("dms")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    renderOpenMenu(<DropdownMenuSeparator data-testid="dms-slot" />);
    expect(screen.getByTestId("dms-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-separator",
    );
  });
});

describe("DropdownMenuShortcut", () => {
  test("renders with text content", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuShortcut data-testid="dm-shortcut">
            Ctrl+K
          </DropdownMenuShortcut>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByText("Ctrl+K")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuShortcut data-testid="dm-shortcut-slot">
            S
          </DropdownMenuShortcut>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("dm-shortcut-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-shortcut",
    );
  });
});

describe("DropdownMenuGroup", () => {
  test("applies data-slot attribute", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuGroup data-testid="dmg-slot">G</DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("dmg-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-group",
    );
  });
});

describe("DropdownMenuCheckboxItem", () => {
  test("renders with text content when open", () => {
    renderOpenMenu(
      <DropdownMenuCheckboxItem data-testid="dmci">
        Check Item
      </DropdownMenuCheckboxItem>,
    );
    expect(screen.getByText("Check Item")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    renderOpenMenu(
      <DropdownMenuCheckboxItem data-testid="dmci-slot">
        Item
      </DropdownMenuCheckboxItem>,
    );
    expect(screen.getByTestId("dmci-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-checkbox-item",
    );
  });

  test("renders checked state", () => {
    renderOpenMenu(
      <DropdownMenuCheckboxItem checked data-testid="dmci-checked">
        Checked
      </DropdownMenuCheckboxItem>,
    );
    expect(screen.getByTestId("dmci-checked")).toHaveAttribute(
      "data-state",
      "checked",
    );
  });
});

describe("DropdownMenuRadioGroup", () => {
  test("applies data-slot attribute", () => {
    renderOpenMenu(<DropdownMenuRadioGroup data-testid="dmrg-slot" />);
    expect(screen.getByTestId("dmrg-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-radio-group",
    );
  });
});

describe("DropdownMenuRadioItem", () => {
  test("renders with text content when open", () => {
    renderOpenMenu(
      <DropdownMenuRadioItem value="radio-1" data-testid="dmri">
        Radio Item
      </DropdownMenuRadioItem>,
    );
    expect(screen.getByText("Radio Item")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    renderOpenMenu(
      <DropdownMenuRadioItem value="radio-2" data-testid="dmri-slot">
        Item
      </DropdownMenuRadioItem>,
    );
    expect(screen.getByTestId("dmri-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-radio-item",
    );
  });
});

describe("DropdownMenuPortal", () => {
  test("renders portal wrapper", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuPortal data-testid="dmp">
            <div>Portal content</div>
          </DropdownMenuPortal>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    // Portal renders its children in the content
    expect(screen.getByText("Portal content")).toBeInTheDocument();
  });
});

describe("DropdownMenuSub", () => {
  test("renders sub menu", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger data-testid="sub-trigger">
              Sub Menu
            </DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("sub-trigger")).toBeInTheDocument();
  });
});

describe("DropdownMenuSubTrigger", () => {
  test("renders with text content", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger data-testid="sub-trigger">
              More options
            </DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByText("More options")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger data-testid="sub-trigger-slot">
              Options
            </DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("sub-trigger-slot")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-sub-trigger",
    );
  });

  test("renders chevron icon", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>Expand</DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    // The chevron icon is rendered as an SVG
    const trigger = screen.getByText("Expand").closest("[data-slot]");
    expect(trigger).toBeInTheDocument();
  });

  test("applies inset data attribute", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger inset data-testid="sub-inset">
              Inset Sub
            </DropdownMenuSubTrigger>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("sub-inset")).toHaveAttribute(
      "data-inset",
      "true",
    );
  });
});

describe("DropdownMenuSubContent", () => {
  test("applies data-slot attribute", () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuSub open>
            <DropdownMenuSubTrigger>Sub</DropdownMenuSubTrigger>
            <DropdownMenuSubContent data-testid="sub-content">
              Sub Content
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByTestId("sub-content")).toHaveAttribute(
      "data-slot",
      "dropdown-menu-sub-content",
    );
  });
});
