import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    variant,
    className,
  }: {
    children: React.ReactNode;
    variant?: string;
    className?: string;
  }) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

vi.mock("@/components/ui/hover-card", () => ({
  HoverCard: ({
    children,
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <div data-testid="hover-card">{children}</div>,
  HoverCardTrigger: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="hover-card-trigger">{children}</div>
  ),
  HoverCardContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div data-testid="hover-card-content" className={className}>
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let CitationLink: typeof import("@/components/workspace/citations/citation-link").CitationLink;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/citations/citation-link");
  CitationLink = mod.CitationLink;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("CitationLink", () => {
  test("renders the citation link with hover card", () => {
    render(<CitationLink href="https://example.com">My Source</CitationLink>);
    expect(screen.getByTestId("hover-card")).toBeInTheDocument();
    expect(screen.getByTestId("hover-card-trigger")).toBeInTheDocument();
  });

  test("renders a link with correct href", () => {
    render(<CitationLink href="https://example.com/page">Link</CitationLink>);
    const links = screen.getAllByRole("link");
    const mainLink = links.find(
      (l) => l.getAttribute("href") === "https://example.com/page",
    );
    expect(mainLink).toBeInTheDocument();
  });

  test("sets target=_blank on the link", () => {
    render(<CitationLink href="https://example.com">Link</CitationLink>);
    const links = screen.getAllByRole("link");
    const mainLink = links.find(
      (l) => l.getAttribute("href") === "https://example.com",
    );
    expect(mainLink).toHaveAttribute("target", "_blank");
  });

  test("sets rel=noopener noreferrer", () => {
    render(<CitationLink href="https://example.com">Link</CitationLink>);
    const links = screen.getAllByRole("link");
    const mainLink = links.find(
      (l) => l.getAttribute("href") === "https://example.com",
    );
    expect(mainLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("shows hover card content", () => {
    render(<CitationLink href="https://example.com/path">Link</CitationLink>);
    expect(screen.getByTestId("hover-card-content")).toBeInTheDocument();
  });

  test("shows visit source link in hover card", () => {
    render(<CitationLink href="https://example.com">Link</CitationLink>);
    expect(screen.getByText("Visit source")).toBeInTheDocument();
  });

  test("renders a badge", () => {
    render(<CitationLink href="https://example.com">Link</CitationLink>);
    expect(screen.getByTestId("badge")).toBeInTheDocument();
  });

  test("badge has secondary variant", () => {
    render(<CitationLink href="https://example.com">Link</CitationLink>);
    expect(screen.getByTestId("badge")).toHaveAttribute(
      "data-variant",
      "secondary",
    );
  });

  test("handles invalid URL gracefully", () => {
    render(<CitationLink href="not-a-url">Link Text</CitationLink>);
    const links = screen.getAllByRole("link");
    const mainLink = links.find((l) => l.getAttribute("href") === "not-a-url");
    expect(mainLink).toBeInTheDocument();
  });

  test("preserves custom className", () => {
    render(
      <CitationLink href="https://example.com" className="custom">
        Link
      </CitationLink>,
    );
    const hoverContent = screen.getByTestId("hover-card-content");
    expect(hoverContent.getAttribute("class")).toContain("custom");
  });

  test("click handler stops propagation", () => {
    const parentClick = vi.fn();
    render(
      <div onClick={parentClick}>
        <CitationLink href="https://example.com">Link</CitationLink>
      </div>,
    );
    const links = screen.getAllByRole("link");
    const mainLink = links.find(
      (l) => l.getAttribute("href") === "https://example.com",
    );
    mainLink?.click();
    expect(parentClick).not.toHaveBeenCalled();
  });
});
