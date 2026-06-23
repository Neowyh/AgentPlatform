import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const {
  mockNotFound,
  mockImportPage,
  mockGetAllPosts,
  mockGetBlogIndexData,
  mockFormatTagName,
  mockGetPreferredBlogLang,
  mockGetI18n,
} = vi.hoisted(() => ({
  mockNotFound: vi.fn(),
  mockImportPage: vi.fn(),
  mockGetAllPosts: vi.fn(),
  mockGetBlogIndexData: vi.fn(),
  mockFormatTagName: vi.fn(),
  mockGetPreferredBlogLang: vi.fn(),
  mockGetI18n: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  notFound: mockNotFound,
}));

vi.mock("nextra/pages", () => ({
  importPage: mockImportPage,
}));

vi.mock("@/core/blog", () => ({
  BLOG_LANGS: ["zh", "en"],
  formatTagName: (...args: any[]) => mockFormatTagName(...args),
  getAllPosts: (...args: any[]) => mockGetAllPosts(...args),
  getBlogIndexData: (...args: any[]) => mockGetBlogIndexData(...args),
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
  PostMeta: ({ currentLang, date, languages, pathname }: any) => (
    <div data-testid="post-meta">
      <span data-testid="post-lang">{currentLang}</span>
      {date && <span data-testid="post-date">{date}</span>}
      <span data-testid="post-pathname">{pathname}</span>
    </div>
  ),
}));

import BlogPage, { generateMetadata } from "@/app/blog/[[...mdxPath]]/page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Blog catch-all page", () => {
  beforeEach(() => {
    mockGetI18n.mockResolvedValue({ locale: "en-US" });
    mockGetPreferredBlogLang.mockReturnValue("en");
  });

  // --- generateMetadata tests ---
  describe("generateMetadata", () => {
    test("returns 'Blog' title for empty mdxPath", async () => {
      const metadata = await generateMetadata({
        params: Promise.resolve({ mdxPath: undefined }),
      });
      expect(metadata).toEqual({ title: "Blog" });
    });

    test("returns 'Blog' title for empty array mdxPath", async () => {
      const metadata = await generateMetadata({
        params: Promise.resolve({ mdxPath: [] }),
      });
      expect(metadata).toEqual({ title: "Blog" });
    });

    test("returns tag title when mdxPath is tags/[tag]", async () => {
      mockFormatTagName.mockReturnValue("AI");

      const metadata = await generateMetadata({
        params: Promise.resolve({ mdxPath: ["tags", "ai"] }),
      });

      expect(metadata).toEqual({ title: "AI" });
      expect(mockFormatTagName).toHaveBeenCalledWith("ai");
    });

    test("returns page metadata for a blog post", async () => {
      // loadBlogPage tries importPage for each BLOG_LANG ["zh", "en"]
      // First call (zh) succeeds, second (en) fails
      mockImportPage
        .mockResolvedValueOnce({
          metadata: { title: "My Post", date: "2024-01-01" },
        })
        .mockRejectedValueOnce(new Error("not found"));

      const metadata = await generateMetadata({
        params: Promise.resolve({ mdxPath: ["my-post"] }),
      });

      expect(metadata).toHaveProperty("title", "My Post");
      expect(metadata).toHaveProperty("date", "2024-01-01");
    });

    test("returns empty object when page not found", async () => {
      mockImportPage.mockRejectedValue(new Error("not found"));

      const metadata = await generateMetadata({
        params: Promise.resolve({ mdxPath: ["nonexistent"] }),
      });

      expect(metadata).toEqual({});
    });
  });

  // --- Page render tests ---
  describe("Page rendering", () => {
    test("renders all posts list when mdxPath is empty", async () => {
      mockGetAllPosts.mockResolvedValue([
        { title: "Post 1", slug: ["post-1"] },
        { title: "Post 2", slug: ["post-2"] },
      ]);

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: undefined }),
          searchParams: Promise.resolve({}),
        }),
      );

      expect(screen.getByTestId("post-list")).toBeInTheDocument();
      expect(screen.getByTestId("wrapper-title").textContent).toBe("All Posts");
      expect(screen.getByTestId("post-count").textContent).toBe("2");
    });

    test("renders tag page when mdxPath starts with 'tags'", async () => {
      mockFormatTagName.mockReturnValue("React");
      mockGetBlogIndexData.mockResolvedValue({
        posts: [{ title: "React Post", slug: ["react-post"] }],
      });

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: ["tags", "react"] }),
          searchParams: Promise.resolve({}),
        }),
      );

      expect(screen.getByTestId("wrapper-title").textContent).toBe("React");
      expect(screen.getByTestId("post-count").textContent).toBe("1");
    });

    test("calls notFound for empty tag results", async () => {
      mockFormatTagName.mockReturnValue("Empty");
      mockGetBlogIndexData.mockResolvedValue({ posts: [] });
      mockNotFound.mockImplementation(() => {
        throw new Error("NOT_FOUND");
      });

      await expect(
        BlogPage({
          params: Promise.resolve({ mdxPath: ["tags", "empty"] }),
          searchParams: Promise.resolve({}),
        }),
      ).rejects.toThrow("NOT_FOUND");
    });

    test("calls notFound for invalid tag URI encoding", async () => {
      mockNotFound.mockImplementation(() => {
        throw new Error("NOT_FOUND");
      });

      await expect(
        BlogPage({
          params: Promise.resolve({ mdxPath: ["tags", "%E0%A4%A"] }),
          searchParams: Promise.resolve({}),
        }),
      ).rejects.toThrow("NOT_FOUND");
    });

    test("calls notFound when blog page not found", async () => {
      mockImportPage.mockRejectedValue(new Error("not found"));
      mockNotFound.mockImplementation(() => {
        throw new Error("NOT_FOUND");
      });

      await expect(
        BlogPage({
          params: Promise.resolve({ mdxPath: ["nonexistent-post"] }),
          searchParams: Promise.resolve({}),
        }),
      ).rejects.toThrow("NOT_FOUND");
    });

    test("renders individual blog post with MDX content", async () => {
      const MockMDXContent = (props: any) => (
        <div data-testid="mdx-content">Post Body</div>
      );
      // loadBlogPage tries importPage for each BLOG_LANG ["zh", "en"]
      mockImportPage
        .mockResolvedValueOnce({
          default: MockMDXContent,
          toc: [{ id: "h1", value: "Heading", depth: 1 }],
          metadata: { title: "My Post", date: "2024-06-01" },
          sourceCode: "code",
        })
        .mockRejectedValueOnce(new Error("not found"));

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: ["my-post"] }),
          searchParams: Promise.resolve({}),
        }),
      );

      expect(screen.getByTestId("wrapper")).toBeInTheDocument();
      expect(screen.getByTestId("mdx-content")).toBeInTheDocument();
      expect(screen.getByTestId("post-meta")).toBeInTheDocument();
      expect(screen.getByText("Post Body")).toBeInTheDocument();
    });

    test("renders post meta with correct lang and date", async () => {
      const MockMDXContent = () => <div>Content</div>;
      // loadBlogPage tries importPage for each BLOG_LANG ["zh", "en"]
      // First call (zh) fails, second (en) succeeds - so preferredLang "en" is picked
      mockImportPage
        .mockRejectedValueOnce(new Error("not found"))
        .mockResolvedValueOnce({
          default: MockMDXContent,
          toc: [],
          metadata: { title: "Test", date: "2024-03-15" },
          sourceCode: "",
        });

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: ["test-post"] }),
          searchParams: Promise.resolve({}),
        }),
      );

      expect(screen.getByTestId("post-lang").textContent).toBe("en");
      expect(screen.getByTestId("post-date").textContent).toBe("2024-03-15");
      expect(screen.getByTestId("post-pathname").textContent).toBe(
        "/blog/test-post",
      );
    });

    test("uses query lang param when valid", async () => {
      mockGetAllPosts.mockResolvedValue([]);

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: undefined }),
          searchParams: Promise.resolve({ lang: "zh" }),
        }),
      );

      expect(mockGetAllPosts).toHaveBeenCalledWith("zh");
    });

    test("falls back to locale lang when query lang is invalid", async () => {
      mockGetAllPosts.mockResolvedValue([]);

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: undefined }),
          searchParams: Promise.resolve({ lang: "invalid" }),
        }),
      );

      expect(mockGetAllPosts).toHaveBeenCalledWith("en");
    });

    test("renders tags page with description", async () => {
      mockFormatTagName.mockReturnValue("TypeScript");
      mockGetBlogIndexData.mockResolvedValue({
        posts: [
          { title: "TS Post 1", slug: ["ts-1"] },
          { title: "TS Post 2", slug: ["ts-2"] },
          { title: "TS Post 3", slug: ["ts-3"] },
        ],
      });

      render(
        await BlogPage({
          params: Promise.resolve({ mdxPath: ["tags", "typescript"] }),
          searchParams: Promise.resolve({}),
        }),
      );

      expect(screen.getByText(/3 posts with the tag/)).toBeInTheDocument();
    });
  });
});
