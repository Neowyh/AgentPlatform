import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test } from "vitest";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

afterEach(() => {
  cleanup();
});

describe("Tabs", () => {
  test("renders tabs container", () => {
    render(
      <Tabs defaultValue="tab1" data-testid="tabs">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Tabs defaultValue="tab1" data-testid="tabs-slot">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tabs-slot")).toHaveAttribute(
      "data-slot",
      "tabs",
    );
  });

  test("applies horizontal orientation by default", () => {
    render(
      <Tabs defaultValue="tab1" data-testid="tabs-h">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tabs-h")).toHaveAttribute(
      "data-orientation",
      "horizontal",
    );
  });

  test("applies vertical orientation", () => {
    render(
      <Tabs defaultValue="tab1" orientation="vertical" data-testid="tabs-v">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tabs-v")).toHaveAttribute(
      "data-orientation",
      "vertical",
    );
  });
});

describe("TabsList", () => {
  test("renders tab triggers", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList data-testid="tl">
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tl")).toBeInTheDocument();
    expect(screen.getByText("Tab 1")).toBeInTheDocument();
    expect(screen.getByText("Tab 2")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList data-testid="tl-slot">
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tl-slot")).toHaveAttribute(
      "data-slot",
      "tabs-list",
    );
  });

  test("applies default variant", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList data-testid="tl-default">
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tl-default")).toHaveAttribute(
      "data-variant",
      "default",
    );
  });

  test("applies line variant", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList variant="line" data-testid="tl-line">
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tl-line")).toHaveAttribute(
      "data-variant",
      "line",
    );
  });
});

describe("TabsTrigger", () => {
  test("renders as a button", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1" data-testid="tt">
            Tab 1
          </TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tt").tagName).toBe("BUTTON");
  });

  test("applies data-slot attribute", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1" data-testid="tt-slot">
            Tab 1
          </TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    expect(screen.getByTestId("tt-slot")).toHaveAttribute(
      "data-slot",
      "tabs-trigger",
    );
  });

  test("can be clicked to switch tabs", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    );
    expect(screen.getByText("Content 1")).toBeInTheDocument();
    expect(screen.queryByText("Content 2")).not.toBeInTheDocument();
    // Click Tab 2 trigger button
    const tab2 = screen.getByRole("tab", { name: "Tab 2" });
    await user.click(tab2);
    expect(screen.getByText("Content 2")).toBeInTheDocument();
    expect(screen.queryByText("Content 1")).not.toBeInTheDocument();
  });
});

describe("TabsContent", () => {
  test("renders content for active tab", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1" data-testid="tc">
          Tab 1 Content
        </TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId("tc")).toBeInTheDocument();
    expect(screen.getByText("Tab 1 Content")).toBeInTheDocument();
  });

  test("does not render content for inactive tab", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          <TabsTrigger value="tab2">Tab 2</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1">Content 1</TabsContent>
        <TabsContent value="tab2">Content 2</TabsContent>
      </Tabs>,
    );
    expect(screen.getByText("Content 1")).toBeInTheDocument();
    expect(screen.queryByText("Content 2")).not.toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Tabs defaultValue="tab1">
        <TabsList>
          <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        </TabsList>
        <TabsContent value="tab1" data-testid="tc-slot">
          Content
        </TabsContent>
      </Tabs>,
    );
    expect(screen.getByTestId("tc-slot")).toHaveAttribute(
      "data-slot",
      "tabs-content",
    );
  });
});
