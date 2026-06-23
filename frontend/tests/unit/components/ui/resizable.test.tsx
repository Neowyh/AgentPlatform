import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock react-resizable-panels since it uses APIs not available in jsdom
vi.mock("react-resizable-panels", () => ({
  Group: vi.fn(({ children, className, ...props }: any) => (
    <div data-testid="mock-group" className={className} {...props}>
      {children}
    </div>
  )),
  Panel: vi.fn(({ children, ...props }: any) => (
    <div data-testid="mock-panel" {...props}>
      {children}
    </div>
  )),
  PanelResizeHandle: vi.fn(({ children, ...props }: any) => (
    <div data-testid="mock-handle" {...props}>
      {children}
    </div>
  )),
  // Alias: the source imports as Separator from react-resizable-panels
  Separator: vi.fn(({ children, ...props }: any) => (
    <div data-testid="mock-separator" {...props}>
      {children}
    </div>
  )),
}));

import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";

afterEach(() => {
  cleanup();
});

describe("ResizablePanelGroup", () => {
  test("renders with children", () => {
    render(
      <ResizablePanelGroup data-testid="rpg">
        <ResizablePanel>Panel 1</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rpg")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <ResizablePanelGroup data-testid="rpg-slot">
        <ResizablePanel>P</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rpg-slot")).toHaveAttribute(
      "data-slot",
      "resizable-panel-group",
    );
  });

  test("applies custom className", () => {
    render(
      <ResizablePanelGroup className="custom-rpg" data-testid="rpg-custom">
        <ResizablePanel>P</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rpg-custom")).toHaveClass("custom-rpg");
  });
});

describe("ResizablePanel", () => {
  test("renders with children", () => {
    render(
      <ResizablePanelGroup>
        <ResizablePanel data-testid="rp">Panel Content</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rp")).toBeInTheDocument();
    expect(screen.getByText("Panel Content")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <ResizablePanelGroup>
        <ResizablePanel data-testid="rp-slot">P</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rp-slot")).toHaveAttribute(
      "data-slot",
      "resizable-panel",
    );
  });
});

describe("ResizableHandle", () => {
  test("applies data-slot attribute", () => {
    render(
      <ResizablePanelGroup>
        <ResizablePanel>A</ResizablePanel>
        <ResizableHandle data-testid="rh-slot" />
        <ResizablePanel>B</ResizablePanel>
      </ResizablePanelGroup>,
    );
    expect(screen.getByTestId("rh-slot")).toHaveAttribute(
      "data-slot",
      "resizable-handle",
    );
  });

  test("renders without handle icon by default", () => {
    const { container } = render(
      <ResizablePanelGroup>
        <ResizablePanel>A</ResizablePanel>
        <ResizableHandle data-testid="rh" />
        <ResizablePanel>B</ResizablePanel>
      </ResizablePanelGroup>,
    );
    const handle = screen.getByTestId("rh");
    // Without withHandle, no GripVerticalIcon should be rendered
    const svgIcon = handle.querySelector("svg");
    expect(svgIcon).not.toBeInTheDocument();
  });

  test("renders handle icon when withHandle is true", () => {
    const { container } = render(
      <ResizablePanelGroup>
        <ResizablePanel>A</ResizablePanel>
        <ResizableHandle withHandle data-testid="rh-handle" />
        <ResizablePanel>B</ResizablePanel>
      </ResizablePanelGroup>,
    );
    const handle = screen.getByTestId("rh-handle");
    const svgIcon = handle.querySelector("svg");
    expect(svgIcon).toBeInTheDocument();
  });
});
