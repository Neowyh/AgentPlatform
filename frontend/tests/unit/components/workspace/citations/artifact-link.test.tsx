import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/workspace/citations/citation-link", () => ({
  CitationLink: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href?: string;
  }) => (
    <a data-testid="citation-link" href={href}>
      {children}
    </a>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ArtifactLink: typeof import("@/components/workspace/citations/artifact-link").ArtifactLink;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/citations/artifact-link");
  ArtifactLink = mod.ArtifactLink;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ArtifactLink", () => {
  test("renders citation: prefix children as CitationLink", () => {
    render(
      <ArtifactLink href="https://example.com">citation:Source A</ArtifactLink>,
    );
    expect(screen.getByTestId("citation-link")).toBeInTheDocument();
    expect(screen.getByText("Source A")).toBeInTheDocument();
  });

  test("renders regular link for non-citation children", () => {
    render(
      <ArtifactLink href="https://example.com">Regular Link</ArtifactLink>,
    );
    expect(screen.queryByTestId("citation-link")).not.toBeInTheDocument();
    expect(screen.getByText("Regular Link")).toBeInTheDocument();
  });

  test("applies underline class to regular links", () => {
    render(
      <ArtifactLink href="https://example.com">Regular Link</ArtifactLink>,
    );
    const link = screen.getByText("Regular Link");
    expect(link.getAttribute("class")).toContain("underline");
  });

  test("sets target=_blank for external URLs", () => {
    render(<ArtifactLink href="https://example.com">External</ArtifactLink>);
    const link = screen.getByText("External");
    expect(link).toHaveAttribute("target", "_blank");
  });

  test("sets rel=noopener noreferrer for external URLs", () => {
    render(<ArtifactLink href="https://example.com">External</ArtifactLink>);
    const link = screen.getByText("External");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("does not set target=_blank for internal URLs", () => {
    render(<ArtifactLink href="/internal/page">Internal</ArtifactLink>);
    const link = screen.getByText("Internal");
    expect(link).not.toHaveAttribute("target", "_blank");
  });

  test("preserves custom target attribute", () => {
    render(
      <ArtifactLink href="https://example.com" target="_self">
        Custom
      </ArtifactLink>,
    );
    const link = screen.getByText("Custom");
    expect(link).toHaveAttribute("target", "_self");
  });

  test("preserves custom className", () => {
    render(
      <ArtifactLink href="https://example.com" className="my-class">
        Styled
      </ArtifactLink>,
    );
    const link = screen.getByText("Styled");
    expect(link.getAttribute("class")).toContain("my-class");
  });

  test("renders with no href", () => {
    render(<ArtifactLink>No Href</ArtifactLink>);
    const link = screen.getByText("No Href");
    expect(link).toBeInTheDocument();
  });

  test("handles non-string children gracefully", () => {
    render(
      <ArtifactLink href="https://example.com">
        <span>Nested element</span>
      </ArtifactLink>,
    );
    expect(screen.getByText("Nested element")).toBeInTheDocument();
    expect(screen.queryByTestId("citation-link")).not.toBeInTheDocument();
  });
});
