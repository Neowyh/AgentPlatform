import { render, screen, cleanup } from "@testing-library/react";
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Pluggable is a transitive type from unified
type Pluggable = any;
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/components/ai-elements/message", () => ({
  MessageResponse: ({
    children,
    className,
    components,
  }: {
    children: React.ReactNode;
    className?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    components?: Record<string, React.ComponentType<any>>;
  }) => (
    <div data-testid="message-response" className={className}>
      {/* Actually render the content so components can be exercised */}
      {typeof children === "string" && components?.a ? (
        <span data-testid="rendered-with-a-component">
          <components.a href="https://example.com">{children}</components.a>
        </span>
      ) : typeof children === "string" ? (
        children
      ) : (
        String(children)
      )}
      {components && (
        <div data-testid="has-components">
          {Object.keys(components).join(",")}
        </div>
      )}
    </div>
  ),
}));

vi.mock("@/core/streamdown", () => ({
  streamdownPlugins: {
    remarkPlugins: [],
  },
  preprocessStreamdownMarkdown: (content: string) =>
    content === '```mermaid\nA -- "label" -.-> B\n```'
      ? '```mermaid\nA -. "label" .-> B\n```'
      : content,
}));

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

vi.mock("@/core/streamdown/plugins", () => ({
  streamdownPlugins: {
    remarkPlugins: [],
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let MarkdownContent: typeof import("@/components/workspace/messages/markdown-content").MarkdownContent;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/messages/markdown-content");
  MarkdownContent = mod.MarkdownContent;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("MarkdownContent", () => {
  const defaultRehypePlugins: Pluggable[] = [];

  test("renders content when provided", () => {
    render(
      <MarkdownContent
        content="Hello world"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    expect(screen.getByTestId("message-response")).toBeInTheDocument();
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  test("normalizes Mermaid markdown before rendering", () => {
    render(
      <MarkdownContent
        content={'```mermaid\nA -- "label" -.-> B\n```'}
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );

    expect(
      screen.getByText('```mermaid A -. "label" .-> B ```'),
    ).toBeInTheDocument();
  });

  test("returns null when content is empty", () => {
    const { container } = render(
      <MarkdownContent
        content=""
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("applies custom className", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
        className="my-md"
      />,
    );
    const wrapper = screen.getByTestId("message-response");
    expect(wrapper.getAttribute("class")).toContain("my-md");
  });

  test("passes rehypePlugins to MessageResponse", () => {
    const plugins = ["plugin1", "plugin2"];
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={plugins as never}
      />,
    );
    expect(screen.getByTestId("message-response")).toBeInTheDocument();
  });

  test("passes remarkPlugins to MessageResponse", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
        remarkPlugins={["remark-test"] as never}
      />,
    );
    expect(screen.getByTestId("message-response")).toBeInTheDocument();
  });

  test("includes a: component in components prop", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    expect(screen.getByTestId("has-components")).toBeInTheDocument();
    expect(screen.getByText(/a/)).toBeInTheDocument();
  });

  test("merges custom components with default a: component", () => {
    const CustomComponent = () => <div>Custom</div>;
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
        components={
          { custom: CustomComponent } as Record<string, React.ComponentType>
        }
      />,
    );
    const componentsText = screen.getByTestId("has-components").textContent;
    expect(componentsText).toContain("a");
    expect(componentsText).toContain("custom");
  });
});

describe("MarkdownContent a component", () => {
  const defaultRehypePlugins: Pluggable[] = [];

  // We need a mock that actually renders the a component to test its branches
  beforeAll(async () => {
    vi.resetModules();

    vi.doMock("@/components/ai-elements/message", () => ({
      MessageResponse: ({ children, className, components }: any) => {
        const AComponent = components?.a;
        return (
          <div data-testid="message-response" className={className}>
            {AComponent ? (
              <div data-testid="a-exercised">
                {/* Test external URL */}
                <AComponent
                  href="https://example.com"
                  children="External link"
                />
                {/* Test internal URL */}
                <AComponent href="/internal" children="Internal link" />
                {/* Test citation URL */}
                <AComponent href="/cite" children="citation:123" />
                {/* Test with existing className */}
                <AComponent
                  href="https://test.com"
                  className="custom-link"
                  children="Styled link"
                />
                {/* Test with existing target */}
                <AComponent
                  href="https://test.com"
                  target="_self"
                  children="Self target"
                />
                {/* Test with existing rel */}
                <AComponent
                  href="https://test.com"
                  rel="nofollow"
                  children="Custom rel"
                />
                {/* Test with non-string children (e.g., JSX) */}
                <AComponent href="https://test.com">
                  <span>JSX child</span>
                </AComponent>
              </div>
            ) : typeof children === "string" ? (
              children
            ) : (
              String(children)
            )}
          </div>
        );
      },
    }));

    vi.doMock("@/core/streamdown", () => ({
      streamdownPlugins: {
        remarkPlugins: [],
      },
      preprocessStreamdownMarkdown: (content: string) => content,
    }));

    vi.doMock("@/components/workspace/citations/citation-link", () => ({
      CitationLink: ({ children, href }: any) => (
        <a data-testid="citation-link" href={href}>
          {children}
        </a>
      ),
    }));

    vi.doMock("@/core/streamdown/plugins", () => ({
      streamdownPlugins: {
        remarkPlugins: [],
      },
    }));
  });

  let MarkdownContent: typeof import("@/components/workspace/messages/markdown-content").MarkdownContent;

  beforeAll(async () => {
    const mod =
      await import("@/components/workspace/messages/markdown-content");
    MarkdownContent = mod.MarkdownContent;
  });

  test("renders CitationLink for citation: children", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    expect(screen.getByTestId("citation-link")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
  });

  test("adds target=_blank for external URLs", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    const links = screen.getAllByRole("link");
    const externalLink = links.find(
      (l) => l.getAttribute("href") === "https://example.com",
    );
    expect(externalLink).toHaveAttribute("target", "_blank");
    expect(externalLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("does not add target for internal URLs", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    const links = screen.getAllByRole("link");
    const internalLink = links.find(
      (l) => l.getAttribute("href") === "/internal",
    );
    expect(internalLink).not.toHaveAttribute("target");
    expect(internalLink).not.toHaveAttribute("rel");
  });

  test("preserves existing target attribute", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    const links = screen.getAllByRole("link");
    const selfTarget = links.find((l) => l.textContent === "Self target");
    expect(selfTarget).toHaveAttribute("target", "_self");
  });

  test("preserves existing rel attribute", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    const links = screen.getAllByRole("link");
    const nofollow = links.find((l) => l.textContent === "Custom rel");
    expect(nofollow).toHaveAttribute("rel", "nofollow");
  });

  test("renders non-string children as-is", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    expect(screen.getByText("JSX child")).toBeInTheDocument();
  });

  test("applies custom className from props to links", () => {
    render(
      <MarkdownContent
        content="Content"
        isLoading={false}
        rehypePlugins={defaultRehypePlugins}
      />,
    );
    const links = screen.getAllByRole("link");
    const styledLink = links.find((l) => l.textContent === "Styled link");
    expect(styledLink?.getAttribute("class")).toContain("custom-link");
  });
});
