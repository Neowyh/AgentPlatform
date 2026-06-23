import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/blog", () => ({
  getAllPosts: vi.fn().mockResolvedValue([
    { title: "First Post", path: "/blog/first" },
    { title: "Second Post", path: "/blog/second" },
  ]),
  getPreferredBlogLang: vi.fn().mockReturnValue("en"),
}));

vi.mock("@/core/i18n/server", () => ({
  getI18n: vi.fn().mockResolvedValue({ locale: "en" }),
}));

vi.mock("@/components/landing/post-list", () => ({
  PostList: ({ title, posts }: any) => (
    <div data-testid="post-list">
      <h1>{title}</h1>
      {posts.map((p: any) => (
        <div key={p.path}>{p.title}</div>
      ))}
    </div>
  ),
}));

vi.mock("@/mdx-components", () => ({
  useMDXComponents: () => ({
    wrapper: ({ children }: any) => <div>{children}</div>,
  }),
}));

afterEach(() => {
  cleanup();
});

import PostsPage from "@/app/blog/posts/page";

describe("PostsPage", () => {
  test("renders post list with title", async () => {
    render(await PostsPage());
    expect(screen.getByText("All Posts")).toBeInTheDocument();
  });

  test("renders blog posts", async () => {
    render(await PostsPage());
    expect(screen.getByText("First Post")).toBeInTheDocument();
    expect(screen.getByText("Second Post")).toBeInTheDocument();
  });
});
