import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ui/skeleton", () => ({
  Skeleton: ({
    className,
    style,
    ...props
  }: {
    className?: string;
    style?: React.CSSProperties;
  }) => (
    <div
      data-testid="skeleton"
      className={className}
      style={style}
      {...props}
    />
  ),
}));

let SidebarMenuSkeleton: typeof import("@/components/ui/sidebar").SidebarMenuSkeleton;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/ui/sidebar");
  SidebarMenuSkeleton = mod.SidebarMenuSkeleton;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SidebarMenuSkeleton", () => {
  test("renders with data-slot and data-sidebar attributes", () => {
    render(<SidebarMenuSkeleton />);
    const el = document.querySelector('[data-slot="sidebar-menu-skeleton"]');
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute("data-sidebar", "menu-skeleton");
  });

  test("renders exactly one skeleton bar (text) by default", () => {
    render(<SidebarMenuSkeleton />);
    const bars = screen.getAllByTestId("skeleton");
    expect(bars).toHaveLength(1);
  });

  test("renders icon skeleton when showIcon is true", () => {
    render(<SidebarMenuSkeleton showIcon />);
    const bars = screen.getAllByTestId("skeleton");
    expect(bars).toHaveLength(2);
  });

  test("skeleton children have correct data-sidebar attributes", () => {
    render(<SidebarMenuSkeleton showIcon />);
    expect(
      document.querySelector('[data-sidebar="menu-skeleton-icon"]'),
    ).toBeInTheDocument();
    expect(
      document.querySelector('[data-sidebar="menu-skeleton-text"]'),
    ).toBeInTheDocument();
  });

  test("text skeleton has --skeleton-width CSS variable", () => {
    render(<SidebarMenuSkeleton />);
    const textSkeleton = screen.getByTestId("skeleton");
    expect(textSkeleton.getAttribute("style")).toMatch(
      /--skeleton-width:\s*\d+%/,
    );
  });

  test("applies custom className", () => {
    render(<SidebarMenuSkeleton className="my-custom-class" />);
    const el = document.querySelector('[data-slot="sidebar-menu-skeleton"]');
    expect(el).toHaveClass("my-custom-class");
  });

  test("forwards additional props to the container", () => {
    render(<SidebarMenuSkeleton data-testid="sidebar-menu-skeleton" />);
    expect(screen.getByTestId("sidebar-menu-skeleton")).toBeInTheDocument();
  });
});
