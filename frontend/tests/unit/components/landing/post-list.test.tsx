import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { PostMeta, PostTags, PostList } from "@/components/landing/post-list";

afterEach(() => {
  cleanup();
});

describe("PostMeta", () => {
  test("renders formatted date", () => {
    render(<PostMeta date="2024-06-15" />);
    expect(screen.getByText(/Jun 15, 2024/)).toBeInTheDocument();
  });

  test("returns null when no date and single language", () => {
    const { container } = render(<PostMeta />);
    expect(container.firstChild).toBeNull();
  });

  test("renders language links when multiple languages", () => {
    render(
      <PostMeta
        date="2024-06-15"
        languages={["en", "zh"]}
        pathname="/blog/test"
        currentLang="en"
      />,
    );
    expect(screen.getByText("EN")).toBeInTheDocument();
    expect(screen.getByText("ZH")).toBeInTheDocument();
  });

  test("highlights active language", () => {
    render(
      <PostMeta
        date="2024-06-15"
        languages={["en", "zh"]}
        pathname="/blog/test"
        currentLang="en"
      />,
    );
    const enLink = screen.getByText("EN");
    expect(enLink.className).toContain("font-medium");
  });
});

describe("PostTags", () => {
  test("renders tags", () => {
    render(<PostTags tags={["react", "typescript"]} />);
    expect(screen.getByText("react")).toBeInTheDocument();
    expect(screen.getByText("typescript")).toBeInTheDocument();
  });

  test("returns null for empty tags array", () => {
    const { container } = render(<PostTags tags={[]} />);
    expect(container.firstChild).toBeNull();
  });

  test("returns null for non-array tags", () => {
    const { container } = render(<PostTags tags="not-an-array" />);
    expect(container.firstChild).toBeNull();
  });

  test("filters out non-string tags", () => {
    render(<PostTags tags={[123, "valid", null]} />);
    expect(screen.getByText("valid")).toBeInTheDocument();
  });
});

describe("PostList", () => {
  const mockPosts = [
    {
      slug: ["post-1"],
      title: "First Post",
      lang: "en",
      languages: ["en"],
      metadata: {
        description: "Description 1",
        date: "2024-01-01",
        tags: ["tag1"],
      },
    },
    {
      slug: ["post-2"],
      title: "Second Post",
      lang: "en",
      languages: ["en"],
      metadata: {},
    },
  ] as any;

  test("renders the title", () => {
    render(<PostList title="Blog Posts" posts={[]} />);
    expect(screen.getByText("Blog Posts")).toBeInTheDocument();
  });

  test("renders description when provided", () => {
    render(
      <PostList title="Blog" posts={[]} description="My blog description" />,
    );
    expect(screen.getByText("My blog description")).toBeInTheDocument();
  });

  test("renders post titles", () => {
    render(<PostList title="Blog" posts={mockPosts} />);
    expect(screen.getByText("First Post")).toBeInTheDocument();
    expect(screen.getByText("Second Post")).toBeInTheDocument();
  });

  test("renders post descriptions when available", () => {
    render(<PostList title="Blog" posts={mockPosts} />);
    expect(screen.getByText("Description 1")).toBeInTheDocument();
  });

  test("renders posts with and without descriptions", () => {
    render(<PostList title="Blog" posts={mockPosts} />);
    // First post has a description, second does not
    expect(screen.getByText("Description 1")).toBeInTheDocument();
    // Both post titles should be present
    expect(screen.getByText("First Post")).toBeInTheDocument();
    expect(screen.getByText("Second Post")).toBeInTheDocument();
  });
});
