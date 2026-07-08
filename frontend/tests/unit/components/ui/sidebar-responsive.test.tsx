import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  SidebarProvider,
  Sidebar,
  SidebarTrigger,
} from "@/components/ui/sidebar";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

type Listener = (ev: MediaQueryListEvent) => void;

function createMatchMediaMock(matchesMobile: boolean) {
  const listeners = new Set<Listener>();

  const mql: MediaQueryList = {
    matches: matchesMobile,
    media: `(max-width: ${767}px)`,
    onchange: null,
    addEventListener: vi.fn((type: string, listener: EventListener) => {
      if (type === "change") listeners.add(listener as Listener);
    }),
    removeEventListener: vi.fn((type: string, listener: EventListener) => {
      if (type === "change") listeners.delete(listener as Listener);
    }),
    dispatchEvent: vi.fn((event: Event) => {
      listeners.forEach((l) => l(event as MediaQueryListEvent));
      return true;
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  };

  return { mql, listeners };
}

function setWindowWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    configurable: true,
    value: width,
  });
}

// ---------------------------------------------------------------------------
// tests
// ---------------------------------------------------------------------------

describe("Sidebar responsive behavior", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  describe("desktop mode (>= 768px)", () => {
    beforeEach(() => {
      const { mql } = createMatchMediaMock(false);
      vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(mql));
      setWindowWidth(1024);
    });

    it("renders sidebar on desktop with data-state=expanded", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
        </SidebarProvider>,
      );

      const sidebar = screen.getByTestId("test-sidebar");
      expect(sidebar).toBeTruthy();
      expect(sidebar.getAttribute("data-slot")).toBe("sidebar-container");
      // The wrapper (parent) carries data-state
      const wrapper = sidebar.parentElement;
      expect(wrapper?.getAttribute("data-state")).toBe("expanded");
    });

    it("toggleSidebar changes data-state from expanded to collapsed", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      const sidebar = screen.getByTestId("test-sidebar");
      const wrapper = sidebar.parentElement!;
      expect(wrapper.getAttribute("data-state")).toBe("expanded");

      fireEvent.click(screen.getByTestId("trigger"));

      expect(wrapper.getAttribute("data-state")).toBe("collapsed");
    });

    it("Ctrl+B keyboard shortcut toggles data-state", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
        </SidebarProvider>,
      );

      const sidebar = screen.getByTestId("test-sidebar");
      const wrapper = sidebar.parentElement!;
      expect(wrapper.getAttribute("data-state")).toBe("expanded");

      fireEvent.keyDown(window, { key: "b", ctrlKey: true });

      expect(wrapper.getAttribute("data-state")).toBe("collapsed");
    });

    it("collapsible=icon sets data-collapsible when collapsed", () => {
      render(
        <SidebarProvider>
          <Sidebar collapsible="icon" data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      const sidebar = screen.getByTestId("test-sidebar");
      const wrapper = sidebar.parentElement!;
      expect(wrapper.getAttribute("data-state")).toBe("expanded");
      expect(wrapper.getAttribute("data-collapsible")).toBe("");

      fireEvent.click(screen.getByTestId("trigger"));

      expect(wrapper.getAttribute("data-state")).toBe("collapsed");
      expect(wrapper.getAttribute("data-collapsible")).toBe("icon");
      // SIDEBAR_WIDTH_ICON = "3rem" is set as CSS variable on SidebarProvider
      const provider = sidebar.closest("[data-slot='sidebar-wrapper']");
      expect(provider?.getAttribute("style")).toContain(
        "--sidebar-width-icon: 3rem",
      );
    });

    it("collapsible=none renders without data-state", () => {
      render(
        <SidebarProvider>
          <Sidebar collapsible="none" data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
        </SidebarProvider>,
      );

      const sidebar = screen.getByTestId("test-sidebar");
      expect(sidebar.getAttribute("data-slot")).toBe("sidebar");
      // collapsible=none early-returns a flat div without data-state
      expect(sidebar.getAttribute("data-state")).toBeNull();
    });
  });

  describe("mobile mode (< 768px)", () => {
    beforeEach(() => {
      const { mql } = createMatchMediaMock(true);
      vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(mql));
      setWindowWidth(375);
    });

    it("sidebar is hidden by default on mobile", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
        </SidebarProvider>,
      );

      const dialog = screen.queryByRole("dialog");
      expect(dialog).toBeNull();
    });

    it("toggleSidebar opens the mobile sidebar sheet", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      fireEvent.click(screen.getByTestId("trigger"));

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeTruthy();
    });

    it("mobile sidebar has data-mobile attribute when open", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      fireEvent.click(screen.getByTestId("trigger"));

      const dialog = screen.getByRole("dialog");
      expect(dialog).toBeTruthy();
      expect(dialog.getAttribute("data-mobile")).toBe("true");
      expect(dialog.getAttribute("data-slot")).toBe("sidebar");
    });

    it("mobile sidebar has correct width style", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      fireEvent.click(screen.getByTestId("trigger"));

      const dialog = screen.getByRole("dialog");
      expect(dialog.getAttribute("style")).toContain("--sidebar-width: 18rem");
    });

    it("trigger closes the mobile sidebar", () => {
      render(
        <SidebarProvider>
          <Sidebar data-testid="test-sidebar">
            <div>Sidebar content</div>
          </Sidebar>
          <SidebarTrigger data-testid="trigger" />
        </SidebarProvider>,
      );

      // Open
      fireEvent.click(screen.getByTestId("trigger"));
      expect(screen.getByRole("dialog")).toBeTruthy();

      // Close
      fireEvent.click(screen.getByTestId("trigger"));
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });
});
