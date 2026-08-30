import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const { mockImportPage, mockGenerateStaticParamsFor, mockNotFound } =
  vi.hoisted(() => ({
    mockImportPage: vi.fn(),
    mockGenerateStaticParamsFor: vi.fn().mockReturnValue(() => []),
    mockNotFound: vi.fn(() => {
      throw new Error("NEXT_NOT_FOUND");
    }),
  }));

vi.mock("next/navigation", () => ({
  notFound: mockNotFound,
}));

vi.mock("nextra/pages", () => ({
  generateStaticParamsFor: mockGenerateStaticParamsFor,
  importPage: mockImportPage,
}));

vi.mock("@/mdx-components", () => ({
  useMDXComponents: () => ({
    wrapper: ({ children, toc, metadata, sourceCode }: any) => (
      <div data-testid="mdx-wrapper">
        <span data-testid="toc">{JSON.stringify(toc)}</span>
        <span data-testid="metadata">{JSON.stringify(metadata)}</span>
        {children}
      </div>
    ),
  }),
}));

vi.mock("nextra-theme-docs", () => ({
  Layout: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("nextra-theme-docs/style.css", () => ({}));

import DocPage, {
  generateMetadata,
  generateStaticParams,
} from "@/app/[lang]/docs/[[...mdxPath]]/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Docs catch-all page", () => {
  test("generateStaticParams is a function", () => {
    expect(typeof generateStaticParams).toBe("function");
  });

  test("generateMetadata returns metadata from importPage", async () => {
    mockImportPage.mockResolvedValue({
      metadata: { title: "Test Doc", description: "A test doc" },
    });

    const metadata = await generateMetadata({
      params: Promise.resolve({ mdxPath: ["getting-started"], lang: "en" }),
    });

    expect(metadata).toEqual({ title: "Test Doc", description: "A test doc" });
    expect(mockImportPage).toHaveBeenCalledWith(["getting-started"], "en");
  });

  test("generateMetadata handles single segment mdxPath", async () => {
    mockImportPage.mockResolvedValue({
      metadata: { title: "Overview" },
    });

    const metadata = await generateMetadata({
      params: Promise.resolve({ mdxPath: ["overview"], lang: "zh" }),
    });

    expect(metadata).toEqual({ title: "Overview" });
    expect(mockImportPage).toHaveBeenCalledWith(["overview"], "zh");
  });

  test("normalizes a multi-segment string mdxPath for Nextra", async () => {
    mockImportPage.mockResolvedValue({
      metadata: { title: "Deployment Guide" },
      default: () => <div>Content</div>,
    });

    await generateMetadata({
      params: Promise.resolve({
        mdxPath: "application/deployment-guide",
        lang: "en",
      }),
    });

    expect(mockImportPage).toHaveBeenCalledWith(
      ["application", "deployment-guide"],
      "en",
    );
  });

  test("Page renders MDX content inside wrapper", async () => {
    const MockMDXContent = (props: any) => (
      <div data-testid="mdx-content">MDX Body</div>
    );
    mockImportPage.mockResolvedValue({
      default: MockMDXContent,
      toc: [{ id: "heading", value: "Heading", depth: 2 }],
      metadata: { title: "Test Page" },
      sourceCode: "const x = 1;",
    });

    render(
      await DocPage({
        params: Promise.resolve({ mdxPath: ["guide"], lang: "en" }),
      }),
    );

    expect(screen.getByTestId("mdx-wrapper")).toBeInTheDocument();
    expect(screen.getByTestId("mdx-content")).toBeInTheDocument();
    expect(screen.getByText("MDX Body")).toBeInTheDocument();
  });

  test("Page passes toc and metadata to wrapper", async () => {
    const toc = [{ id: "intro", value: "Introduction", depth: 1 }];
    const metadata = { title: "Intro Page" };
    const MockMDXContent = () => <div>Content</div>;

    mockImportPage.mockResolvedValue({
      default: MockMDXContent,
      toc,
      metadata,
      sourceCode: "",
    });

    render(
      await DocPage({
        params: Promise.resolve({ mdxPath: ["intro"], lang: "en" }),
      }),
    );

    expect(screen.getByTestId("toc").textContent).toBe(JSON.stringify(toc));
    expect(screen.getByTestId("metadata").textContent).toBe(
      JSON.stringify(metadata),
    );
  });

  test("Page passes props and params to MDXContent", async () => {
    const receivedProps: any[] = [];
    const MockMDXContent = (props: any) => {
      receivedProps.push(props);
      return <div>Content</div>;
    };
    const params = { mdxPath: ["test"], lang: "en" };

    mockImportPage.mockResolvedValue({
      default: MockMDXContent,
      toc: [],
      metadata: {},
      sourceCode: "",
    });

    render(
      await DocPage({
        params: Promise.resolve(params),
        searchParams: Promise.resolve({}),
      }),
    );

    expect(receivedProps[0]).toHaveProperty("params");
    expect(receivedProps[0].params).toEqual(params);
  });

  test("Page supplies safe defaults for optional Nextra fields", async () => {
    const MockMDXContent = () => <div>Content</div>;
    mockImportPage.mockResolvedValue({ default: MockMDXContent });

    render(
      await DocPage({
        params: Promise.resolve({ mdxPath: ["minimal"], lang: "en" }),
      }),
    );

    expect(screen.getByTestId("mdx-wrapper")).toBeInTheDocument();
  });
});
