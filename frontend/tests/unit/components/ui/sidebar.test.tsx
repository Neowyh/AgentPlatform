import {
  render,
  screen,
  cleanup,
  fireEvent,
  act,
} from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/hooks/use-mobile", () => ({
  useIsMobile: vi.fn(() => false),
}));

// Import the mocked module to get a reference to useIsMobile
import * as useMobileModule from "@/hooks/use-mobile";

vi.mock("@radix-ui/react-slot", () => ({
  Slot: ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => {
    // Slot merges props onto its single child element
    if (React.isValidElement(children)) {
      return React.cloneElement(children, props);
    }
    return <>{children}</>;
  },
}));

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

afterEach(() => {
  cleanup();
});

describe("SidebarProvider", () => {
  test("renders SidebarProvider", () => {
    render(
      <SidebarProvider>
        <div>content</div>
      </SidebarProvider>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  test("renders with data-slot", () => {
    render(
      <SidebarProvider data-testid="provider">
        <div>child</div>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("provider")).toHaveAttribute(
      "data-slot",
      "sidebar-wrapper",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider className="custom-class" data-testid="provider">
        <div>child</div>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("provider")).toHaveClass("custom-class");
  });

  test("applies custom style", () => {
    render(
      <SidebarProvider style={{ opacity: "0.5" }} data-testid="provider">
        <div>child</div>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("provider")).toHaveStyle({ opacity: "0.5" });
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <span>first</span>
        <span>second</span>
      </SidebarProvider>,
    );
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });
});

describe("Sidebar", () => {
  test("renders Sidebar with data-slot", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarHeader>Header</SidebarHeader>
          <SidebarContent>Content</SidebarContent>
          <SidebarFooter>Footer</SidebarFooter>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByText("Header")).toBeInTheDocument();
    expect(screen.getByText("Content")).toBeInTheDocument();
    expect(screen.getByText("Footer")).toBeInTheDocument();
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <div>child content</div>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  test("renders with collapsible none", () => {
    render(
      <SidebarProvider>
        <Sidebar collapsible="none" data-testid="sidebar">
          <div>static sidebar</div>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByText("static sidebar")).toBeInTheDocument();
  });
});

describe("SidebarTrigger", () => {
  test("renders SidebarTrigger", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger />
      </SidebarProvider>,
    );
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger data-testid="trigger" />
      </SidebarProvider>,
    );
    expect(screen.getByTestId("trigger")).toHaveAttribute(
      "data-slot",
      "sidebar-trigger",
    );
  });

  test("has sr-only toggle text", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger />
      </SidebarProvider>,
    );
    expect(screen.getByText("Toggle Sidebar")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger className="custom-trigger" data-testid="trigger" />
      </SidebarProvider>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });
});

describe("SidebarRail", () => {
  test("renders SidebarRail", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveAttribute(
      "data-slot",
      "sidebar-rail",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveAttribute("data-sidebar", "rail");
  });

  test("has aria-label for toggle", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveAttribute(
      "aria-label",
      "Toggle Sidebar",
    );
  });

  test("has title attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveAttribute(
      "title",
      "Toggle Sidebar",
    );
  });

  test("has tabIndex -1", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveAttribute("tabindex", "-1");
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarRail className="custom-rail" data-testid="rail" />
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("rail")).toHaveClass("custom-rail");
  });
});

describe("SidebarInset", () => {
  test("renders SidebarInset", () => {
    render(
      <SidebarProvider>
        <SidebarInset data-testid="inset">Inset Content</SidebarInset>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("inset")).toBeInTheDocument();
    expect(screen.getByText("Inset Content")).toBeInTheDocument();
  });

  test("renders as main element", () => {
    render(
      <SidebarProvider>
        <SidebarInset data-testid="inset">Content</SidebarInset>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("inset").tagName).toBe("MAIN");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <SidebarInset data-testid="inset">Content</SidebarInset>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("inset")).toHaveAttribute(
      "data-slot",
      "sidebar-inset",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <SidebarInset className="custom-inset" data-testid="inset">
          Content
        </SidebarInset>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("inset")).toHaveClass("custom-inset");
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <SidebarInset>
          <span>child one</span>
          <span>child two</span>
        </SidebarInset>
      </SidebarProvider>,
    );
    expect(screen.getByText("child one")).toBeInTheDocument();
    expect(screen.getByText("child two")).toBeInTheDocument();
  });
});

describe("SidebarInput", () => {
  test("renders SidebarInput", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input")).toBeInTheDocument();
  });

  test("renders as input element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input").tagName).toBe("INPUT");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input")).toHaveAttribute(
      "data-slot",
      "sidebar-input",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input")).toHaveAttribute(
      "data-sidebar",
      "input",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput className="custom-input" data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input")).toHaveClass("custom-input");
  });

  test("passes placeholder prop", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput placeholder="Search..." data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });

  test("passes type prop", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarInput type="password" data-testid="input" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("input")).toHaveAttribute("type", "password");
  });
});

describe("SidebarSeparator", () => {
  test("renders SidebarSeparator", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarSeparator data-testid="separator" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("separator")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarSeparator data-testid="separator" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("separator")).toHaveAttribute(
      "data-slot",
      "sidebar-separator",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarSeparator data-testid="separator" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("separator")).toHaveAttribute(
      "data-sidebar",
      "separator",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarSeparator className="custom-sep" data-testid="separator" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("separator")).toHaveClass("custom-sep");
  });
});

describe("SidebarGroup", () => {
  test("renders SidebarGroup", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup data-testid="group">Group Content</SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group")).toBeInTheDocument();
    expect(screen.getByText("Group Content")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup data-testid="group">Content</SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group")).toHaveAttribute(
      "data-slot",
      "sidebar-group",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup data-testid="group">Content</SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group")).toHaveAttribute(
      "data-sidebar",
      "group",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup className="custom-group" data-testid="group">
              Content
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group")).toHaveClass("custom-group");
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <span>child one</span>
              <span>child two</span>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("child one")).toBeInTheDocument();
    expect(screen.getByText("child two")).toBeInTheDocument();
  });
});

describe("SidebarGroupLabel", () => {
  test("renders SidebarGroupLabel", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel data-testid="group-label">
                Label Text
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("Label Text")).toBeInTheDocument();
  });

  test("renders as div by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel data-testid="group-label">
                Label
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-label").tagName).toBe("DIV");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel data-testid="group-label">
                Label
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-label")).toHaveAttribute(
      "data-slot",
      "sidebar-group-label",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel data-testid="group-label">
                Label
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-label")).toHaveAttribute(
      "data-sidebar",
      "group-label",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel
                className="custom-label"
                data-testid="group-label"
              >
                Label
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-label")).toHaveClass("custom-label");
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel asChild data-testid="group-label">
                <span>Custom Element</span>
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    // When asChild=true, the Slot renders the child element with merged props
    const element = screen.getByText("Custom Element");
    expect(element).toHaveAttribute("data-slot", "sidebar-group-label");
    expect(element).toHaveAttribute("data-sidebar", "group-label");
  });

  test("renders without asChild prop as div", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel data-testid="group-label">
                Default Label
              </SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByTestId("group-label");
    expect(element.tagName).toBe("DIV");
    expect(element).toHaveTextContent("Default Label");
  });
});

describe("SidebarGroupAction", () => {
  test("renders SidebarGroupAction", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction data-testid="group-action">
                Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-action")).toBeInTheDocument();
  });

  test("renders as button by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction data-testid="group-action">
                Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-action").tagName).toBe("BUTTON");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction data-testid="group-action">
                Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-action")).toHaveAttribute(
      "data-slot",
      "sidebar-group-action",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction data-testid="group-action">
                Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-action")).toHaveAttribute(
      "data-sidebar",
      "group-action",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction
                className="custom-action"
                data-testid="group-action"
              >
                Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-action")).toHaveClass("custom-action");
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction asChild data-testid="group-action">
                <span>Custom Action</span>
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByText("Custom Action");
    expect(element).toHaveAttribute("data-slot", "sidebar-group-action");
    expect(element).toHaveAttribute("data-sidebar", "group-action");
  });

  test("renders without asChild prop as button", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupAction data-testid="group-action">
                Default Action
              </SidebarGroupAction>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByTestId("group-action");
    expect(element.tagName).toBe("BUTTON");
    expect(element).toHaveTextContent("Default Action");
  });
});

describe("SidebarGroupContent", () => {
  test("renders SidebarGroupContent", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent data-testid="group-content">
                Group Content
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-content")).toBeInTheDocument();
    expect(screen.getByText("Group Content")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent data-testid="group-content">
                Content
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-content")).toHaveAttribute(
      "data-slot",
      "sidebar-group-content",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent data-testid="group-content">
                Content
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-content")).toHaveAttribute(
      "data-sidebar",
      "group-content",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent
                className="custom-content"
                data-testid="group-content"
              >
                Content
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("group-content")).toHaveClass("custom-content");
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent>
                <span>inner child</span>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("inner child")).toBeInTheDocument();
  });
});

describe("SidebarMenuAction", () => {
  test("renders SidebarMenuAction", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-action")).toBeInTheDocument();
  });

  test("renders as button by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-action").tagName).toBe("BUTTON");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-action")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-action",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-action")).toHaveAttribute(
      "data-sidebar",
      "menu-action",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction
                  className="custom-action"
                  data-testid="menu-action"
                >
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-action")).toHaveClass("custom-action");
  });

  test("does not have showOnHover classes by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const action = screen.getByTestId("menu-action");
    expect(action.className).not.toContain("md:opacity-0");
  });

  test("applies showOnHover classes when showOnHover is true", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction showOnHover data-testid="menu-action">
                  More
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const action = screen.getByTestId("menu-action");
    expect(action.className).toContain("md:opacity-0");
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuAction asChild data-testid="menu-action">
                  <span>Custom Action</span>
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByText("Custom Action");
    expect(element).toHaveAttribute("data-slot", "sidebar-menu-action");
    expect(element).toHaveAttribute("data-sidebar", "menu-action");
  });
});

describe("SidebarMenuBadge", () => {
  test("renders SidebarMenuBadge", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuBadge data-testid="menu-badge">5</SidebarMenuBadge>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-badge")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuBadge data-testid="menu-badge">3</SidebarMenuBadge>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-badge")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-badge",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuBadge data-testid="menu-badge">3</SidebarMenuBadge>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-badge")).toHaveAttribute(
      "data-sidebar",
      "menu-badge",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuBadge
                  className="custom-badge"
                  data-testid="menu-badge"
                >
                  1
                </SidebarMenuBadge>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-badge")).toHaveClass("custom-badge");
  });

  test("renders text content", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
                <SidebarMenuBadge data-testid="menu-badge">
                  New
                </SidebarMenuBadge>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("New")).toBeInTheDocument();
  });
});

describe("SidebarMenuSkeleton", () => {
  test("renders SidebarMenuSkeleton", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-skeleton")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-skeleton")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-skeleton",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-skeleton")).toHaveAttribute(
      "data-sidebar",
      "menu-skeleton",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton
                  className="custom-skeleton"
                  data-testid="menu-skeleton"
                />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-skeleton")).toHaveClass("custom-skeleton");
  });

  test("does not render icon skeleton by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const skeleton = screen.getByTestId("menu-skeleton");
    const iconSkeleton = skeleton.querySelector(
      '[data-sidebar="menu-skeleton-icon"]',
    );
    expect(iconSkeleton).toBeNull();
  });

  test("renders icon skeleton when showIcon is true", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton showIcon data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const skeleton = screen.getByTestId("menu-skeleton");
    const iconSkeleton = skeleton.querySelector(
      '[data-sidebar="menu-skeleton-icon"]',
    );
    expect(iconSkeleton).toBeInTheDocument();
  });

  test("always renders text skeleton", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const skeleton = screen.getByTestId("menu-skeleton");
    const textSkeleton = skeleton.querySelector(
      '[data-sidebar="menu-skeleton-text"]',
    );
    expect(textSkeleton).toBeInTheDocument();
  });

  test("text skeleton has dynamic width style", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSkeleton data-testid="menu-skeleton" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const skeleton = screen.getByTestId("menu-skeleton");
    const textSkeleton = skeleton.querySelector(
      '[data-sidebar="menu-skeleton-text"]',
    )!;
    const style = textSkeleton.getAttribute("style") || "";
    expect(style).toMatch(/--skeleton-width:\s*\d+%/);
  });
});

describe("SidebarMenuSub", () => {
  test("renders SidebarMenuSub", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub data-testid="menu-sub">
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton>Sub Item</SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub")).toBeInTheDocument();
    expect(screen.getByText("Sub Item")).toBeInTheDocument();
  });

  test("renders as ul element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub data-testid="menu-sub" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub").tagName).toBe("UL");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub data-testid="menu-sub" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-sub",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub data-testid="menu-sub" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub")).toHaveAttribute(
      "data-sidebar",
      "menu-sub",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub className="custom-sub" data-testid="menu-sub" />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub")).toHaveClass("custom-sub");
  });

  test("renders multiple children", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub data-testid="menu-sub">
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton>Item 1</SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton>Item 2</SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("Item 2")).toBeInTheDocument();
  });
});

describe("SidebarMenuSubItem", () => {
  test("renders SidebarMenuSubItem", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem data-testid="menu-sub-item">
                    Sub Item Content
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub-item")).toBeInTheDocument();
    expect(screen.getByText("Sub Item Content")).toBeInTheDocument();
  });

  test("renders as li element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem data-testid="menu-sub-item">
                    Content
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub-item").tagName).toBe("LI");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem data-testid="menu-sub-item">
                    Content
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub-item")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-sub-item",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem data-testid="menu-sub-item">
                    Content
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub-item")).toHaveAttribute(
      "data-sidebar",
      "menu-sub-item",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem
                    className="custom-sub-item"
                    data-testid="menu-sub-item"
                  >
                    Content
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-sub-item")).toHaveClass("custom-sub-item");
  });

  test("renders children", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <span>inner content</span>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("inner content")).toBeInTheDocument();
  });
});

describe("SidebarMenuSubButton", () => {
  test("renders SidebarMenuSubButton", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toBeInTheDocument();
    expect(screen.getByText("Sub Button")).toBeInTheDocument();
  });

  test("renders as a element by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button").tagName).toBe("A");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-sub-button",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute(
      "data-sidebar",
      "menu-sub-button",
    );
  });

  test("defaults to size md", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute("data-size", "md");
  });

  test("applies size sm", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton size="sm" data-testid="sub-button">
                      Small Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute("data-size", "sm");
  });

  test("applies size md explicitly", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton size="md" data-testid="sub-button">
                      Medium Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute("data-size", "md");
  });

  test("defaults isActive to false", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute(
      "data-active",
      "false",
    );
  });

  test("applies isActive true", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton isActive data-testid="sub-button">
                      Active Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton
                      className="custom-sub-button"
                      data-testid="sub-button"
                    >
                      Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("sub-button")).toHaveClass("custom-sub-button");
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton asChild data-testid="sub-button">
                      <span>Custom Sub Button</span>
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByText("Custom Sub Button");
    expect(element).toHaveAttribute("data-slot", "sidebar-menu-sub-button");
    expect(element).toHaveAttribute("data-sidebar", "menu-sub-button");
  });

  test("renders without asChild prop as a element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-button">
                      Default Sub Button
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByTestId("sub-button");
    expect(element.tagName).toBe("A");
    expect(element).toHaveTextContent("Default Sub Button");
  });
});

describe("SidebarMenu and SidebarMenuItem", () => {
  test("renders SidebarMenu and SidebarMenuItem", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Menu Item</SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByText("Menu Item")).toBeInTheDocument();
  });

  test("SidebarMenu renders as ul element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu data-testid="menu" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu").tagName).toBe("UL");
  });

  test("SidebarMenuItem renders as li element", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem data-testid="menu-item" />
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-item").tagName).toBe("LI");
  });

  test("SidebarMenu has correct data-slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu data-testid="menu" />
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu")).toHaveAttribute(
      "data-slot",
      "sidebar-menu",
    );
  });

  test("SidebarMenuItem has correct data-slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem data-testid="menu-item" />
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-item")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-item",
    );
  });
});

describe("SidebarMenuButton", () => {
  test("renders SidebarMenuButton", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton data-testid="menu-button">
                  Button Text
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toBeInTheDocument();
    expect(screen.getByText("Button Text")).toBeInTheDocument();
  });

  test("renders as button by default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button").tagName).toBe("BUTTON");
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-slot",
      "sidebar-menu-button",
    );
  });

  test("defaults isActive to false", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-active",
      "false",
    );
  });

  test("applies isActive true", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive data-testid="menu-button">
                  Active
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  test("defaults size to default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-size",
      "default",
    );
  });

  test("applies size sm", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton size="sm" data-testid="menu-button">
                  Small
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-size",
      "sm",
    );
  });

  test("applies size lg", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton size="lg" data-testid="menu-button">
                  Large
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toHaveAttribute(
      "data-size",
      "lg",
    );
  });

  test("renders with asChild prop using Slot", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild data-testid="menu-button">
                  <span>Custom Button</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const element = screen.getByText("Custom Button");
    expect(element).toHaveAttribute("data-slot", "sidebar-menu-button");
    expect(element).toHaveAttribute("data-sidebar", "menu-button");
  });
});

describe("SidebarHeader", () => {
  test("renders SidebarHeader", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader data-testid="header">Header Content</SidebarHeader>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("header")).toBeInTheDocument();
    expect(screen.getByText("Header Content")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader data-testid="header">Content</SidebarHeader>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("header")).toHaveAttribute(
      "data-slot",
      "sidebar-header",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader data-testid="header">Content</SidebarHeader>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("header")).toHaveAttribute(
      "data-sidebar",
      "header",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarHeader className="custom-header" data-testid="header">
            Content
          </SidebarHeader>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });
});

describe("SidebarFooter", () => {
  test("renders SidebarFooter", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarFooter data-testid="footer">Footer Content</SidebarFooter>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("footer")).toBeInTheDocument();
    expect(screen.getByText("Footer Content")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarFooter data-testid="footer">Content</SidebarFooter>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("footer")).toHaveAttribute(
      "data-slot",
      "sidebar-footer",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarFooter data-testid="footer">Content</SidebarFooter>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("footer")).toHaveAttribute(
      "data-sidebar",
      "footer",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarFooter className="custom-footer" data-testid="footer">
            Content
          </SidebarFooter>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("footer")).toHaveClass("custom-footer");
  });
});

describe("SidebarContent", () => {
  test("renders SidebarContent", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent data-testid="content">Content Area</SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByText("Content Area")).toBeInTheDocument();
  });

  test("has correct data-slot attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent data-testid="content">Content</SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("content")).toHaveAttribute(
      "data-slot",
      "sidebar-content",
    );
  });

  test("has correct data-sidebar attribute", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent data-testid="content">Content</SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("content")).toHaveAttribute(
      "data-sidebar",
      "content",
    );
  });

  test("applies custom className", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent className="custom-content" data-testid="content">
            Content
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("useSidebar hook", () => {
  test("returns sidebar context when used inside SidebarProvider", () => {
    let contextValue: ReturnType<typeof useSidebar> | null = null;

    function TestComponent() {
      contextValue = useSidebar();
      return <div>Test</div>;
    }

    render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(contextValue).not.toBeNull();
    expect(contextValue!.open).toBe(true);
    expect(contextValue!.state).toBe("expanded");
    expect(contextValue!.isMobile).toBe(false);
    expect(contextValue!.openMobile).toBe(false);
    expect(typeof contextValue!.setOpen).toBe("function");
    expect(typeof contextValue!.setOpenMobile).toBe("function");
    expect(typeof contextValue!.toggleSidebar).toBe("function");
  });

  test("throws error when used outside SidebarProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function TestComponent() {
      useSidebar();
      return <div>Test</div>;
    }

    expect(() => {
      render(<TestComponent />);
    }).toThrow("useSidebar must be used within a SidebarProvider.");

    consoleSpy.mockRestore();
  });

  test("toggleSidebar toggles open state on desktop", () => {
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    const { rerender } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(true);
    expect(latest.current!.state).toBe("expanded");

    act(() => {
      latest.current!.toggleSidebar();
    });

    // Re-render to get updated context
    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(false);
    expect(latest.current!.state).toBe("collapsed");
  });

  test("setOpen controls sidebar state", () => {
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    const { rerender } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(true);

    act(() => {
      latest.current!.setOpen(false);
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(false);
    expect(latest.current!.state).toBe("collapsed");

    act(() => {
      latest.current!.setOpen(true);
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(true);
    expect(latest.current!.state).toBe("expanded");
  });

  test("setOpenMobile controls mobile sidebar state", () => {
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    const { rerender } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.openMobile).toBe(false);

    act(() => {
      latest.current!.setOpenMobile(true);
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.openMobile).toBe(true);

    act(() => {
      latest.current!.setOpenMobile(false);
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.openMobile).toBe(false);
  });

  test("toggles with keyboard shortcut (Ctrl+B)", () => {
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    const { rerender } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(true);

    act(() => {
      fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(false);
  });

  test("toggles with keyboard shortcut (Meta+B)", () => {
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    const { rerender } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(true);

    act(() => {
      fireEvent.keyDown(window, { key: "b", metaKey: true });
    });

    rerender(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(latest.current!.open).toBe(false);
  });

  test("respects defaultOpen=false", () => {
    let contextValue: ReturnType<typeof useSidebar> | null = null;

    function TestComponent() {
      contextValue = useSidebar();
      return <div>Test</div>;
    }

    render(
      <SidebarProvider defaultOpen={false}>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(contextValue!.open).toBe(false);
    expect(contextValue!.state).toBe("collapsed");
  });

  test("respects controlled open prop", () => {
    let contextValue: ReturnType<typeof useSidebar> | null = null;

    function TestComponent() {
      contextValue = useSidebar();
      return <div>Test</div>;
    }

    render(
      <SidebarProvider open={false}>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(contextValue!.open).toBe(false);
    expect(contextValue!.state).toBe("collapsed");
  });

  test("calls onOpenChange callback when setOpen is called", () => {
    const onOpenChange = vi.fn();
    const latest = { current: null } as {
      current: ReturnType<typeof useSidebar> | null;
    };

    function TestComponent() {
      latest.current = useSidebar();
      return <div>Test</div>;
    }

    render(
      <SidebarProvider open onOpenChange={onOpenChange}>
        <TestComponent />
      </SidebarProvider>,
    );

    act(() => {
      latest.current!.setOpen(false);
    });

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("useSidebar hook with mobile", () => {
  test("isMobile is false by default mock", () => {
    let contextValue: ReturnType<typeof useSidebar> | null = null;

    function TestComponent() {
      contextValue = useSidebar();
      return <div>Test</div>;
    }

    render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    expect(contextValue!.isMobile).toBe(false);
  });
});

describe("SidebarMenuButton variants", () => {
  test("applies variant default", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton variant="default" data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toBeInTheDocument();
  });

  test("applies variant outline", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton variant="outline" data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    const button = screen.getByTestId("menu-button");
    expect(button.className).toContain("shadow-[0_0_0_1px");
  });
});

describe("SidebarMenuButton with tooltip", () => {
  test("renders with string tooltip", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Tip text" data-testid="menu-button">
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toBeInTheDocument();
  });

  test("renders with object tooltip", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip={{ children: "Object Tip" }}
                  data-testid="menu-button"
                >
                  Button
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );
    expect(screen.getByTestId("menu-button")).toBeInTheDocument();
  });
});

describe("SidebarTrigger custom onClick", () => {
  test("calls custom onClick handler before toggling", () => {
    const onClick = vi.fn();
    render(
      <SidebarProvider>
        <SidebarTrigger onClick={onClick} data-testid="trigger" />
      </SidebarProvider>,
    );

    fireEvent.click(screen.getByTestId("trigger"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("Sidebar mobile rendering", () => {
  afterEach(() => {
    vi.mocked(useMobileModule.useIsMobile).mockReturnValue(false);
  });

  test("renders mobile sidebar in Sheet when isMobile is true", () => {
    vi.mocked(useMobileModule.useIsMobile).mockReturnValue(true);

    // Render with a component that opens the mobile sidebar
    function MobileSidebarTest() {
      const { setOpenMobile } = useSidebar();
      React.useEffect(() => {
        setOpenMobile(true);
      }, [setOpenMobile]);
      return (
        <Sidebar data-testid="sidebar">
          <div>Mobile content</div>
        </Sidebar>
      );
    }

    render(
      <SidebarProvider>
        <MobileSidebarTest />
      </SidebarProvider>,
    );

    // When isMobile=true and openMobile=true, children should be visible
    expect(screen.getByText("Mobile content")).toBeInTheDocument();
  });
});

describe("Sidebar full layout composition", () => {
  test("renders a complete sidebar layout", () => {
    render(
      <SidebarProvider>
        <Sidebar data-testid="sidebar">
          <SidebarHeader data-testid="header">Logo</SidebarHeader>
          <SidebarContent data-testid="content">
            <SidebarGroup>
              <SidebarGroupLabel>Navigation</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton data-testid="nav-button">
                      Dashboard
                    </SidebarMenuButton>
                    <SidebarMenuBadge>12</SidebarMenuBadge>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton isActive data-testid="active-nav">
                      Settings
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarSeparator data-testid="separator" />
            <SidebarInput placeholder="Search..." data-testid="search" />
          </SidebarContent>
          <SidebarFooter data-testid="footer">Footer</SidebarFooter>
          <SidebarRail data-testid="rail" />
        </Sidebar>
        <SidebarInset data-testid="inset">Main Content</SidebarInset>
      </SidebarProvider>,
    );

    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("header")).toHaveTextContent("Logo");
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByText("Navigation")).toBeInTheDocument();
    expect(screen.getByTestId("nav-button")).toHaveTextContent("Dashboard");
    expect(screen.getByTestId("active-nav")).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByTestId("separator")).toBeInTheDocument();
    expect(screen.getByTestId("search")).toBeInTheDocument();
    expect(screen.getByTestId("footer")).toHaveTextContent("Footer");
    expect(screen.getByTestId("rail")).toBeInTheDocument();
    expect(screen.getByTestId("inset")).toHaveTextContent("Main Content");
  });

  test("renders SidebarGroup with label, action, and content", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarGroup data-testid="group">
              <SidebarGroupLabel data-testid="group-label">
                Group Title
              </SidebarGroupLabel>
              <SidebarGroupAction data-testid="group-action">
                Add
              </SidebarGroupAction>
              <SidebarGroupContent data-testid="group-content">
                <p>Group body</p>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );

    expect(screen.getByTestId("group")).toBeInTheDocument();
    expect(screen.getByText("Group Title")).toBeInTheDocument();
    expect(screen.getByText("Add")).toBeInTheDocument();
    expect(screen.getByText("Group body")).toBeInTheDocument();
  });

  test("renders nested sub menu structure", () => {
    render(
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Parent Item</SidebarMenuButton>
                <SidebarMenuSub data-testid="sub-menu">
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton data-testid="sub-btn-1">
                      Child 1
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton size="sm" data-testid="sub-btn-2">
                      Child 2
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );

    expect(screen.getByText("Parent Item")).toBeInTheDocument();
    expect(screen.getByTestId("sub-menu")).toBeInTheDocument();
    expect(screen.getByText("Child 1")).toBeInTheDocument();
    expect(screen.getByText("Child 2")).toBeInTheDocument();
    expect(screen.getByTestId("sub-btn-2")).toHaveAttribute("data-size", "sm");
  });
});
