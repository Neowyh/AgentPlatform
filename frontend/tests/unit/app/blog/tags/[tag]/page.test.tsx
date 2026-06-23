import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const {
  mockNotFound,
  mockGetBlogIndexData,
  mockFormatTagName,
  mockGetPreferredBlogLang,
  mockGetI18n,
} = vi.hoisted(() => ({
  mockNotFound: vi.fn(),
  mockGetBlogIndexData: vi.fn(),
  mockFormatTagName: vi.fn(),
  mockGetPreferredBlogLang: vi.fn(),
  mockGetI18n: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  notFound: mockNotFound,
}));

vi.mock("@/core/blog", () => ({
  getBlogIndexData: (...args: any[]) => mockGetBlogIndexData(...args),
  formatTagName: (...args: any[]) => mockFormatTagName(...args),
  getPreferredBlogLang: (...args: any[]) => mockGetPreferredBlogLang(...args),
}));

vi.mock("@/core/i18n/server", () => ({
  getI18n: (...args: any[]) => mockGetI18n(...args),
}));

vi.mock("@/mdx-components", () => ({
  useMDXComponents: () => ({
    wrapper: ({ children, toc, metadata }: any) => (
      <div data-testid="wrapper">
        <span data-testid="wrapper-title">{metadata?.title}</span>
        {children}
      </div>
    ),
  }),
}));

vi.mock("nextra-theme-docs", () => ({
  Layout: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("nextra-theme-docs/style.css", () => ({}));

vi.mock("@/components/landing/post-list", () => ({
  PostList: ({ title, description, posts }: any) => (
    <div data-testid="post-list">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
      <span data-testid="post-count">{posts?.length ?? 0}</span>
    </div>
  ),
}));

import TagPage, { generateMetadata } from "@/app/blog/tags/[tag]/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Blog TagPage", () => {
  test("generateMetadata returns title from formatTagName", async () => {
    mockFormatTagName.mockReturnValue("Artificial Intelligence");

    const metadata = await generateMetadata({
      params: Promise.resolve({ tag: "ai" }),
    });

    expect(metadata).toEqual({
      title: "Artificial Intelligence",
      filePath: "blog/index.mdx",
    });
    expect(mockFormatTagName).toHaveBeenCalledWith("ai");
  });

  test("generateMetadata handles hyphenated tags", async () => {
    mockFormatTagName.mockReturnValue("Machine Learning");

    const metadata = await generateMetadata({
      params: Promise.resolve({ tag: "machine-learning" }),
    });

    expect(metadata.title).toBe("Machine Learning");
  });

  test("renders post list when posts exist", async () => {
    mockGetI18n.mockResolvedValue({ locale: "en-US" });
    mockGetPreferredBlogLang.mockReturnValue("en");
    mockGetBlogIndexData.mockResolvedValue({
      posts: [
        { title: "AI Post 1", slug: ["ai-post-1"] },
        { title: "AI Post 2", slug: ["ai-post-2"] },
      ],
    });
    mockFormatTagName.mockReturnValue("AI");

    render(
      await TagPage({
        params: Promise.resolve({ tag: "ai" }),
      }),
    );

    expect(screen.getByTestId("post-list")).toBeInTheDocument();
    expect(screen.getByTestId("wrapper-title").textContent).toBe("AI");
    expect(screen.getByTestId("post-count").textContent).toBe("2");
  });

  test("renders description with post count", async () => {
    mockGetI18n.mockResolvedValue({ locale: "en-US" });
    mockGetPreferredBlogLang.mockReturnValue("en");
    mockGetBlogIndexData.mockResolvedValue({
      posts: [{ title: "Post", slug: ["post"] }],
    });
    mockFormatTagName.mockReturnValue("React");

    render(
      await TagPage({
        params: Promise.resolve({ tag: "react" }),
      }),
    );

    expect(screen.getByText(/1 posts with the tag/)).toBeInTheDocument();
  });

  test("calls notFound when no posts match tag", async () => {
    mockGetI18n.mockResolvedValue({ locale: "en-US" });
    mockGetPreferredBlogLang.mockReturnValue("en");
    mockGetBlogIndexData.mockResolvedValue({ posts: [] });
    mockFormatTagName.mockReturnValue("Nonexistent");
    mockNotFound.mockImplementation(() => {
      throw new Error("NOT_FOUND");
    });

    await expect(
      TagPage({
        params: Promise.resolve({ tag: "nonexistent" }),
      }),
    ).rejects.toThrow("NOT_FOUND");

    expect(mockNotFound).toHaveBeenCalled();
  });

  test("passes preferred blog lang from locale", async () => {
    mockGetI18n.mockResolvedValue({ locale: "zh-CN" });
    mockGetPreferredBlogLang.mockReturnValue("zh");
    mockGetBlogIndexData.mockResolvedValue({
      posts: [{ title: "Chinese Post", slug: ["zh-post"] }],
    });
    mockFormatTagName.mockReturnValue("AI");

    render(
      await TagPage({
        params: Promise.resolve({ tag: "ai" }),
      }),
    );

    expect(mockGetPreferredBlogLang).toHaveBeenCalledWith("zh-CN");
    expect(mockGetBlogIndexData).toHaveBeenCalledWith("zh", { tag: "ai" });
  });

  test("wrapper receives correct metadata", async () => {
    mockGetI18n.mockResolvedValue({ locale: "en-US" });
    mockGetPreferredBlogLang.mockReturnValue("en");
    mockGetBlogIndexData.mockResolvedValue({
      posts: [{ title: "Post", slug: ["post"] }],
    });
    mockFormatTagName.mockReturnValue("Testing");

    render(
      await TagPage({
        params: Promise.resolve({ tag: "testing" }),
      }),
    );

    expect(screen.getByTestId("wrapper-title").textContent).toBe("Testing");
  });
});
