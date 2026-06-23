import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockPathname = "/workspace/chats";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      breadcrumb: {
        workspace: "Workspace",
        chats: "Chats",
      },
      common: {
        home: "Home",
      },
    },
  }),
}));

vi.mock("@/components/ui/breadcrumb", () => ({
  Breadcrumb: ({ children }: { children: React.ReactNode }) => (
    <nav>{children}</nav>
  ),
  BreadcrumbList: ({ children }: { children: React.ReactNode }) => (
    <ol>{children}</ol>
  ),
  BreadcrumbItem: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <li className={className}>{children}</li>,
  BreadcrumbLink: ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <span>{children}</span>,
  BreadcrumbPage: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
  BreadcrumbSeparator: ({ className }: { className?: string }) => (
    <span className={className}>/</span>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let WorkspaceContainer: typeof import("@/components/workspace/workspace-container").WorkspaceContainer;
let WorkspaceBody: typeof import("@/components/workspace/workspace-container").WorkspaceBody;
let WorkspaceHeader: typeof import("@/components/workspace/workspace-container").WorkspaceHeader;

beforeEach(async () => {
  vi.clearAllMocks();
  mockPathname = "/workspace/chats";
  const mod = await import("@/components/workspace/workspace-container");
  WorkspaceContainer = mod.WorkspaceContainer;
  WorkspaceBody = mod.WorkspaceBody;
  WorkspaceHeader = mod.WorkspaceHeader;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("WorkspaceContainer", () => {
  test("renders children", () => {
    render(
      <WorkspaceContainer>
        <div>Child content</div>
      </WorkspaceContainer>,
    );
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  test("applies flex h-screen w-full classes", () => {
    const { container } = render(
      <WorkspaceContainer>
        <div>Content</div>
      </WorkspaceContainer>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute("class", expect.stringContaining("flex"));
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("h-screen"),
    );
  });

  test("applies custom className", () => {
    const { container } = render(
      <WorkspaceContainer className="custom-class">
        <div>Content</div>
      </WorkspaceContainer>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute(
      "class",
      expect.stringContaining("custom-class"),
    );
  });

  test("passes additional props", () => {
    const { container } = render(
      <WorkspaceContainer data-testid="container">
        <div>Content</div>
      </WorkspaceContainer>,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveAttribute("data-testid", "container");
  });
});

describe("WorkspaceBody", () => {
  test("renders children", () => {
    render(
      <WorkspaceBody>
        <div>Body content</div>
      </WorkspaceBody>,
    );
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });

  test("renders as main element", () => {
    const { container } = render(
      <WorkspaceBody>
        <div>Content</div>
      </WorkspaceBody>,
    );
    const main = container.querySelector("main");
    expect(main).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <WorkspaceBody className="body-class">
        <div>Content</div>
      </WorkspaceBody>,
    );
    const main = container.querySelector("main");
    expect(main).toHaveAttribute(
      "class",
      expect.stringContaining("body-class"),
    );
  });

  test("passes additional props", () => {
    const { container } = render(
      <WorkspaceBody data-testid="body">
        <div>Content</div>
      </WorkspaceBody>,
    );
    const main = container.querySelector("main");
    expect(main).toHaveAttribute("data-testid", "body");
  });
});

describe("WorkspaceHeader", () => {
  test("renders header element", () => {
    mockPathname = "/workspace/chats";
    const { container } = render(
      <WorkspaceHeader>
        <span>extra</span>
      </WorkspaceHeader>,
    );
    const header = container.querySelector("header");
    expect(header).toBeInTheDocument();
  });

  test("renders breadcrumb with workspace and chats segments", () => {
    mockPathname = "/workspace/chats";
    render(
      <WorkspaceHeader>
        <span>extra</span>
      </WorkspaceHeader>,
    );
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Chats")).toBeInTheDocument();
    expect(screen.getByText("extra")).toBeInTheDocument();
  });

  test("renders first segment only when no second segment", () => {
    mockPathname = "/workspace";
    render(<WorkspaceHeader />);
    expect(screen.getByText("Workspace")).toBeInTheDocument();
  });

  test("shows nameOfSegment fallback capitalization for unknown segment", () => {
    mockPathname = "/agents";
    render(<WorkspaceHeader />);
    expect(screen.getByText("Agents")).toBeInTheDocument();
  });

  test("shows no breadcrumbs for root path", () => {
    mockPathname = "/";
    render(<WorkspaceHeader />);
    // segments = [""], segments[0] is empty/falsy, so no breadcrumbs render
    expect(screen.queryByText("Home")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    mockPathname = "/workspace";
    const { container } = render(<WorkspaceHeader className="header-custom" />);
    const header = container.querySelector("header");
    expect(header).toHaveAttribute(
      "class",
      expect.stringContaining("header-custom"),
    );
  });

  test("passes extra props to header", () => {
    mockPathname = "/workspace";
    const { container } = render(<WorkspaceHeader data-testid="hdr" />);
    const header = container.querySelector("header");
    expect(header).toHaveAttribute("data-testid", "hdr");
  });

  test("renders breadcrumb separator between two segments", () => {
    mockPathname = "/workspace/chats";
    render(<WorkspaceHeader />);
    // The separator "/" should appear between segments
    const separators = screen.getAllByText("/");
    expect(separators.length).toBeGreaterThanOrEqual(1);
  });

  test("chats segment with only one segment shows as BreadcrumbPage", () => {
    mockPathname = "/chats";
    render(<WorkspaceHeader />);
    // nameOfSegment("chats", t) => t.breadcrumb.chats
    expect(screen.getByText("Chats")).toBeInTheDocument();
  });
});
