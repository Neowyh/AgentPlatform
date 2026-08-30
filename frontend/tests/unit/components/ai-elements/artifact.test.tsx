import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Artifact,
  ArtifactHeader,
  ArtifactClose,
  ArtifactTitle,
  ArtifactDescription,
  ArtifactActions,
  ArtifactAction,
  ArtifactContent,
} from "@/components/ai-elements/artifact";

afterEach(() => {
  cleanup();
});

describe("Artifact", () => {
  test("renders with children", () => {
    render(
      <Artifact data-testid="artifact">
        <p>Artifact content</p>
      </Artifact>,
    );
    expect(screen.getByTestId("artifact")).toBeInTheDocument();
    expect(screen.getByText("Artifact content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<Artifact className="custom-artifact" data-testid="artifact" />);
    expect(screen.getByTestId("artifact")).toHaveClass("custom-artifact");
  });

  test("has default styling classes", () => {
    render(<Artifact data-testid="artifact" />);
    const el = screen.getByTestId("artifact");
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("border");
    expect(el.className).toContain("shadow-lg");
  });

  test("spreads additional HTML props", () => {
    render(
      <Artifact
        data-testid="artifact"
        role="region"
        aria-label="My artifact"
      />,
    );
    const el = screen.getByTestId("artifact");
    expect(el).toHaveAttribute("role", "region");
    expect(el).toHaveAttribute("aria-label", "My artifact");
  });
});

describe("ArtifactHeader", () => {
  test("renders with children", () => {
    render(
      <ArtifactHeader data-testid="header">
        <span>Header content</span>
      </ArtifactHeader>,
    );
    expect(screen.getByText("Header content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<ArtifactHeader className="custom-header" data-testid="header" />);
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });

  test("has border-bottom and flex layout", () => {
    render(<ArtifactHeader data-testid="header" />);
    const el = screen.getByTestId("header");
    expect(el.className).toContain("border-b");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("justify-between");
  });
});

describe("ArtifactClose", () => {
  test("renders with default X icon", () => {
    render(<ArtifactClose data-testid="close" />);
    const btn = screen.getByTestId("close");
    expect(btn).toBeInTheDocument();
    expect(btn.tagName).toBe("BUTTON");
    // Should contain an SVG (XIcon)
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  test("renders with custom children instead of default icon", () => {
    render(
      <ArtifactClose data-testid="close">
        <span>Close me</span>
      </ArtifactClose>,
    );
    expect(screen.getByText("Close me")).toBeInTheDocument();
  });

  test("has sr-only Close text", () => {
    render(<ArtifactClose data-testid="close" />);
    expect(
      screen.getByText("Close", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(<ArtifactClose className="custom-close" data-testid="close" />);
    expect(screen.getByTestId("close")).toHaveClass("custom-close");
  });

  test("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ArtifactClose onClick={onClick} data-testid="close" />);
    await user.click(screen.getByTestId("close"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("ArtifactTitle", () => {
  test("renders with children", () => {
    render(<ArtifactTitle data-testid="title">My Title</ArtifactTitle>);
    expect(screen.getByText("My Title")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ArtifactTitle className="custom-title" data-testid="title">
        Title
      </ArtifactTitle>,
    );
    expect(screen.getByTestId("title")).toHaveClass("custom-title");
  });

  test("has text-base and font-medium classes", () => {
    render(<ArtifactTitle data-testid="title">Title</ArtifactTitle>);
    const el = screen.getByTestId("title");
    expect(el.className).toContain("text-base");
    expect(el.className).toContain("font-medium");
  });
});

describe("ArtifactDescription", () => {
  test("renders with children", () => {
    render(
      <ArtifactDescription data-testid="desc">
        Description text
      </ArtifactDescription>,
    );
    expect(screen.getByText("Description text")).toBeInTheDocument();
  });

  test("renders as a paragraph element", () => {
    render(<ArtifactDescription data-testid="desc">Desc</ArtifactDescription>);
    expect(screen.getByTestId("desc").tagName).toBe("P");
  });

  test("applies custom className", () => {
    render(
      <ArtifactDescription className="custom-desc" data-testid="desc">
        Desc
      </ArtifactDescription>,
    );
    expect(screen.getByTestId("desc")).toHaveClass("custom-desc");
  });
});

describe("ArtifactActions", () => {
  test("renders with children", () => {
    render(
      <ArtifactActions data-testid="actions">
        <button>Action 1</button>
        <button>Action 2</button>
      </ArtifactActions>,
    );
    expect(screen.getByText("Action 1")).toBeInTheDocument();
    expect(screen.getByText("Action 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ArtifactActions className="custom-actions" data-testid="actions" />,
    );
    expect(screen.getByTestId("actions")).toHaveClass("custom-actions");
  });

  test("has flex and gap classes", () => {
    render(<ArtifactActions data-testid="actions" />);
    const el = screen.getByTestId("actions");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("gap-1");
  });
});

describe("ArtifactAction", () => {
  test("renders as a button", () => {
    render(<ArtifactAction data-testid="action">Click me</ArtifactAction>);
    const btn = screen.getByTestId("action");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("renders with custom children", () => {
    render(
      <ArtifactAction data-testid="action">
        <span>Custom action</span>
      </ArtifactAction>,
    );
    expect(screen.getByText("Custom action")).toBeInTheDocument();
  });

  test("renders with icon prop", () => {
    const MockIcon = React.forwardRef<SVGSVGElement, { className?: string }>(
      ({ className }, ref) => (
        <svg ref={ref} data-testid="mock-icon" className={className}>
          <circle />
        </svg>
      ),
    );
    MockIcon.displayName = "MockIcon";
    render(<ArtifactAction icon={MockIcon} data-testid="action" />);
    expect(screen.getByTestId("mock-icon")).toBeInTheDocument();
  });

  test("renders sr-only label text", () => {
    render(
      <ArtifactAction label="Delete" data-testid="action">
        <span>X</span>
      </ArtifactAction>,
    );
    expect(
      screen.getByText("Delete", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("renders sr-only tooltip as label fallback", () => {
    render(
      <ArtifactAction tooltip="Copy to clipboard" data-testid="action">
        <span>Copy</span>
      </ArtifactAction>,
    );
    expect(
      screen.getByText("Copy to clipboard", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <ArtifactAction onClick={onClick} data-testid="action">
        Click
      </ArtifactAction>,
    );
    await user.click(screen.getByTestId("action"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("applies custom className", () => {
    render(
      <ArtifactAction className="custom-action" data-testid="action">
        Click
      </ArtifactAction>,
    );
    expect(screen.getByTestId("action")).toHaveClass("custom-action");
  });
});

describe("ArtifactContent", () => {
  test("renders with children", () => {
    render(
      <ArtifactContent data-testid="content">
        <p>Content body</p>
      </ArtifactContent>,
    );
    expect(screen.getByText("Content body")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ArtifactContent className="custom-content" data-testid="content" />,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });

  test("has overflow and padding classes", () => {
    render(<ArtifactContent data-testid="content" />);
    const el = screen.getByTestId("content");
    expect(el.className).toContain("overflow-auto");
    expect(el.className).toContain("p-4");
    expect(el.className).toContain("flex-1");
  });
});

describe("Artifact composition", () => {
  test("renders a full artifact layout", () => {
    render(
      <Artifact data-testid="artifact">
        <ArtifactHeader data-testid="header">
          <ArtifactTitle data-testid="title">Document Viewer</ArtifactTitle>
          <ArtifactClose data-testid="close" />
        </ArtifactHeader>
        <ArtifactContent data-testid="content">
          <p>Document content here</p>
        </ArtifactContent>
      </Artifact>,
    );

    expect(screen.getByTestId("artifact")).toBeInTheDocument();
    expect(screen.getByTestId("header")).toBeInTheDocument();
    expect(screen.getByText("Document Viewer")).toBeInTheDocument();
    expect(screen.getByTestId("close")).toBeInTheDocument();
    expect(screen.getByText("Document content here")).toBeInTheDocument();
  });

  test("renders artifact with actions", () => {
    render(
      <Artifact>
        <ArtifactHeader>
          <ArtifactTitle>File</ArtifactTitle>
          <ArtifactActions>
            <ArtifactAction label="Download" data-testid="download">
              <span>D</span>
            </ArtifactAction>
            <ArtifactAction label="Share" data-testid="share">
              <span>S</span>
            </ArtifactAction>
          </ArtifactActions>
        </ArtifactHeader>
        <ArtifactContent>
          <p>File content</p>
        </ArtifactContent>
      </Artifact>,
    );

    expect(screen.getByTestId("download")).toBeInTheDocument();
    expect(screen.getByTestId("share")).toBeInTheDocument();
    expect(screen.getByText("File content")).toBeInTheDocument();
  });
});
