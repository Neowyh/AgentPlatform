import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("nextra/page-map", () => ({
  getPageMap: vi.fn(),
}));

vi.mock("react", () => ({
  // `cache` in test context simply passes the function through
  cache: <T extends (...args: unknown[]) => unknown>(fn: T) => fn,
}));

vi.mock("@/core/i18n/locale", () => ({
  getLangByLocale: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports (after mocks so the module picks up the mocked bindings)
// ---------------------------------------------------------------------------

import { getPageMap } from "nextra/page-map";

import {
  BLOG_LANGS,
  type BlogLang,
  type BlogPost,
  type BlogMetadata,
  type BlogIndexData,
  getBlogRoute,
  normalizeTagSlug,
  formatTagName,
  getPreferredBlogLang,
  getAllPosts,
  getBlogIndexData,
} from "@/core/blog/index";
import { getLangByLocale } from "@/core/i18n/locale";
import type { MdxFile, PageMapItem, Folder } from "nextra";

// ---------------------------------------------------------------------------
// Helpers to build mock page-map items
// ---------------------------------------------------------------------------

function makeMdxFile(
  name: string,
  route: string,
  frontMatter?: Record<string, unknown>,
): MdxFile {
  return {
    name,
    route,
    ...(frontMatter ? { frontMatter } : {}),
  } as MdxFile;
}

function makeFolder(
  name: string,
  route: string,
  children: PageMapItem[],
): Folder {
  return {
    name,
    route,
    children,
  } as Folder;
}

/** Convenience: build a minimal BlogPost for assertion helpers. */
function makeBlogPost(
  slug: string[],
  overrides: Partial<BlogPost> = {},
): BlogPost {
  const title = overrides.title ?? slug.join("/");
  return {
    lang: overrides.lang ?? "en",
    languages: overrides.languages ?? ["en"],
    metadata: overrides.metadata ?? {
      title,
      tags: [],
      item: makeMdxFile(title, `/blog/${slug.join("/")}`),
    },
    slug,
    title,
  };
}

// ---------------------------------------------------------------------------
// Reset mocks between tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.restoreAllMocks();
});

// ===================================================================
// getBlogRoute
// ===================================================================

describe("getBlogRoute", () => {
  it('returns "/blog" when slug is empty', () => {
    expect(getBlogRoute([])).toBe("/blog");
  });

  it("joins a single-segment slug", () => {
    expect(getBlogRoute(["hello-world"])).toBe("/blog/hello-world");
  });

  it("joins a multi-segment slug", () => {
    expect(getBlogRoute(["2024", "01", "post"])).toBe("/blog/2024/01/post");
  });
});

// ===================================================================
// normalizeTagSlug
// ===================================================================

describe("normalizeTagSlug", () => {
  it("lowercases the tag", () => {
    expect(normalizeTagSlug("React")).toBe("react");
  });

  it("replaces spaces with hyphens", () => {
    expect(normalizeTagSlug("machine learning")).toBe("machine-learning");
  });

  it("collapses multiple spaces into a single hyphen", () => {
    expect(normalizeTagSlug("deep   learning")).toBe("deep-learning");
  });

  it("handles already-normalized slugs", () => {
    expect(normalizeTagSlug("ai")).toBe("ai");
  });

  it("handles mixed case and spaces together", () => {
    expect(normalizeTagSlug("Type Script")).toBe("type-script");
  });
});

// ===================================================================
// formatTagName
// ===================================================================

describe("formatTagName", () => {
  it("capitalizes a single word", () => {
    expect(formatTagName("react")).toBe("React");
  });

  it("capitalizes each hyphen-separated segment", () => {
    expect(formatTagName("machine-learning")).toBe("Machine Learning");
  });

  it("filters out empty segments from leading/trailing hyphens", () => {
    expect(formatTagName("-ai-")).toBe("Ai");
  });

  it("handles multiple hyphens", () => {
    expect(formatTagName("type-script-is-fun")).toBe("Type Script Is Fun");
  });
});

// ===================================================================
// getPreferredBlogLang
// ===================================================================

describe("getPreferredBlogLang", () => {
  it('returns "en" for en-US locale', () => {
    vi.mocked(getLangByLocale).mockReturnValue("en");
    expect(getPreferredBlogLang("en-US")).toBe("en");
  });

  it('returns "zh" for zh-CN locale', () => {
    vi.mocked(getLangByLocale).mockReturnValue("zh");
    expect(getPreferredBlogLang("zh-CN")).toBe("zh");
  });

  it("returns undefined when the locale language is not in BLOG_LANGS", () => {
    vi.mocked(getLangByLocale).mockReturnValue("fr");
    expect(getPreferredBlogLang("en-US")).toBeUndefined();
  });
});

// ===================================================================
// getAllPosts
// ===================================================================

describe("getAllPosts", () => {
  it("returns empty array when all page-maps are empty", async () => {
    vi.mocked(getPageMap).mockResolvedValue([]);
    const posts = await getAllPosts();
    expect(posts).toEqual([]);
  });

  it("collects posts from multiple language trees", async () => {
    const enItems = [
      makeMdxFile("post-a", "/en/posts/post-a", {
        title: "Post A",
        date: "2024-01-01",
        tags: ["ai"],
      }),
    ];
    const zhItems = [
      makeMdxFile("post-a", "/zh/posts/post-a", {
        title: "Post A (zh)",
        date: "2024-01-02",
        tags: ["ai"],
      }),
    ];

    vi.mocked(getPageMap).mockImplementation(
      async (path?: string): Promise<PageMapItem[]> => {
        if (path === "/en/posts") return enItems as unknown as PageMapItem[];
        if (path === "/zh/posts") return zhItems as unknown as PageMapItem[];
        return [];
      },
    );

    const posts = await getAllPosts();
    // Both locales share the same slug "post-a" so they merge into one post
    expect(posts).toHaveLength(1);
    expect(posts[0]!.languages).toEqual(expect.arrayContaining(["en", "zh"]));
  });

  it("sorts posts by date descending", async () => {
    const items = [
      makeMdxFile("old", "/en/posts/old", {
        title: "Old",
        date: "2020-01-01",
      }),
      makeMdxFile("new", "/en/posts/new", {
        title: "New",
        date: "2024-06-01",
      }),
      makeMdxFile("mid", "/en/posts/mid", {
        title: "Mid",
        date: "2022-03-15",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts.map((p) => p.title)).toEqual(["New", "Mid", "Old"]);
  });

  it("prefers the requested language when available", async () => {
    const enItems = [
      makeMdxFile("shared", "/en/posts/shared", {
        title: "Shared EN",
        date: "2024-01-01",
      }),
    ];
    const zhItems = [
      makeMdxFile("shared", "/zh/posts/shared", {
        title: "Shared ZH",
        date: "2024-01-01",
      }),
    ];

    vi.mocked(getPageMap).mockImplementation(
      async (path?: string): Promise<PageMapItem[]> => {
        if (path === "/en/posts") return enItems as unknown as PageMapItem[];
        if (path === "/zh/posts") return zhItems as unknown as PageMapItem[];
        return [];
      },
    );

    const posts = await getAllPosts("zh");
    expect(posts).toHaveLength(1);
    expect(posts[0]!.lang).toBe("zh");
    expect(posts[0]!.title).toBe("Shared ZH");
  });

  it("prefers frontMatter title over file title", async () => {
    const items = [
      {
        name: "file-name",
        route: "/en/posts/my-post",
        title: "File Title",
        frontMatter: { title: "Front Matter Title" },
      } as MdxFile,
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.title).toBe("Front Matter Title");
  });

  it("falls back to item.title when frontMatter.title is missing", async () => {
    const items = [
      {
        name: "file-name",
        route: "/en/posts/my-post",
        title: "File Title",
      } as MdxFile,
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.title).toBe("File Title");
  });

  it("falls back to item.name when both titles are missing", async () => {
    const items = [
      {
        name: "file-name",
        route: "/en/posts/my-post",
      } as MdxFile,
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.title).toBe("file-name");
  });

  it("parses tags from frontMatter", async () => {
    const items = [
      makeMdxFile("tagged", "/en/posts/tagged", {
        title: "Tagged",
        tags: ["ai", "ml", 42, "", false],
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.tags).toEqual(["ai", "ml"]);
  });

  it("handles missing tags gracefully", async () => {
    const items = [
      makeMdxFile("no-tags", "/en/posts/no-tags", {
        title: "No Tags",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.tags).toEqual([]);
  });

  it("merges tags from all language variants", async () => {
    const enItems = [
      makeMdxFile("post", "/en/posts/post", {
        title: "Post",
        tags: ["ai"],
      }),
    ];
    const zhItems = [
      makeMdxFile("post", "/zh/posts/post", {
        title: "Post",
        tags: ["ml"],
      }),
    ];

    vi.mocked(getPageMap).mockImplementation(
      async (path?: string): Promise<PageMapItem[]> => {
        if (path === "/en/posts") return enItems as unknown as PageMapItem[];
        if (path === "/zh/posts") return zhItems as unknown as PageMapItem[];
        return [];
      },
    );

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.tags).toEqual(
      expect.arrayContaining(["ai", "ml"]),
    );
  });

  it("skips items without a route-derived slug (top-level index)", async () => {
    // An item whose route normalises to "/blog" produces an empty slug
    // and should be excluded.
    const items = [makeMdxFile("index", "/en/posts", { title: "Index" })];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts).toHaveLength(0);
  });

  it("recursively collects posts from nested folders", async () => {
    const items = [
      makeFolder("2024", "/en/posts/2024", [
        makeMdxFile("post-1", "/en/posts/2024/post-1", { title: "P1" }),
        makeFolder("06", "/en/posts/2024/06", [
          makeMdxFile("post-2", "/en/posts/2024/06/post-2", { title: "P2" }),
        ]),
      ]),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts).toHaveLength(2);
    expect(posts.map((p) => p.slug)).toEqual(
      expect.arrayContaining([
        ["2024", "post-1"],
        ["2024", "06", "post-2"],
      ]),
    );
  });

  it("normalises locale-prefixed routes to /blog", async () => {
    const items = [makeMdxFile("post", "/zh/posts/post", { title: "ZH Post" })];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts("zh");
    expect(posts[0]!.metadata.item.route).toBe("/blog/post");
  });

  it("handles items that are neither Folder nor MdxFile", async () => {
    // A separator or other non-MdxFile item should be skipped silently.
    const items = [
      { separator: true } as unknown as PageMapItem,
      makeMdxFile("valid", "/en/posts/valid", { title: "Valid" }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts).toHaveLength(1);
  });

  it("preserves date metadata from frontMatter", async () => {
    const items = [
      makeMdxFile("dated", "/en/posts/dated", {
        title: "Dated",
        date: "2024-05-15",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.date).toBe("2024-05-15");
  });

  it("preserves description metadata from frontMatter", async () => {
    const items = [
      makeMdxFile("desc", "/en/posts/desc", {
        title: "Desc",
        description: "A great post",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.description).toBe("A great post");
  });

  it("ignores non-string description values", async () => {
    const items = [
      makeMdxFile("desc", "/en/posts/desc", {
        title: "Desc",
        description: 123,
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    expect(posts[0]!.metadata.description).toBeUndefined();
  });

  it("treats unparseable dates as epoch 0", async () => {
    const items = [
      makeMdxFile("bad-date", "/en/posts/bad-date", {
        title: "Bad",
        date: "not-a-date",
      }),
      makeMdxFile("good-date", "/en/posts/good-date", {
        title: "Good",
        date: "2024-01-01",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    // Good date should come first
    expect(posts[0]!.title).toBe("Good");
  });

  it("handles posts with no date (sorts as epoch 0)", async () => {
    const items = [
      makeMdxFile("undated", "/en/posts/undated", { title: "Undated" }),
      makeMdxFile("dated", "/en/posts/dated", {
        title: "Dated",
        date: "2024-01-01",
      }),
    ];

    vi.mocked(getPageMap).mockResolvedValue(items);

    const posts = await getAllPosts();
    // Dated post should be first
    expect(posts[0]!.title).toBe("Dated");
  });
});

// ===================================================================
// getBlogIndexData
// ===================================================================

describe("getBlogIndexData", () => {
  /** Helper: set up getPageMap to return a simple single-language tree. */
  function stubSingleLangPosts(posts: MdxFile[]) {
    vi.mocked(getPageMap).mockImplementation(
      async (path?: string): Promise<PageMapItem[]> => {
        if (path === "/en/posts") return posts as unknown as PageMapItem[];
        return [];
      },
    );
  }

  it("returns correct shape with empty posts", async () => {
    vi.mocked(getPageMap).mockResolvedValue([]);

    const data = await getBlogIndexData();

    expect(data).toHaveProperty("pageMap");
    expect(data).toHaveProperty("posts");
    expect(data).toHaveProperty("recentPosts");
    expect(data).toHaveProperty("tags");
    expect(data.posts).toEqual([]);
    expect(data.recentPosts).toEqual([]);
    expect(data.tags).toEqual([]);
  });

  it("populates posts from getAllPosts", async () => {
    stubSingleLangPosts([
      makeMdxFile("a", "/en/posts/a", { title: "A", tags: ["ai"] }),
      makeMdxFile("b", "/en/posts/b", { title: "B", tags: ["ml"] }),
    ]);

    const data = await getBlogIndexData();
    expect(data.posts).toHaveLength(2);
  });

  it("limits recentPosts to 5 items", async () => {
    const items = Array.from({ length: 10 }, (_, i) =>
      makeMdxFile(`p${i}`, `/en/posts/p${i}`, {
        title: `P${i}`,
        date: `2024-0${(i % 9) + 1}-01`,
      }),
    );
    stubSingleLangPosts(items);

    const data = await getBlogIndexData();
    expect(data.recentPosts).toHaveLength(5);
  });

  it("recentPosts are the 5 most recent by date", async () => {
    const items = Array.from({ length: 10 }, (_, i) =>
      makeMdxFile(`p${i}`, `/en/posts/p${i}`, {
        title: `P${i}`,
        date: `2024-${String(i + 1).padStart(2, "0")}-01`,
      }),
    );
    stubSingleLangPosts(items);

    const data = await getBlogIndexData();
    expect(data.recentPosts.map((p) => p.title)).toEqual([
      "P9",
      "P8",
      "P7",
      "P6",
      "P5",
    ]);
  });

  describe("tag filtering", () => {
    const posts = [
      makeMdxFile("ai-post", "/en/posts/ai-post", {
        title: "AI Post",
        tags: ["ai", "ml"],
      }),
      makeMdxFile("web-post", "/en/posts/web-post", {
        title: "Web Post",
        tags: ["web"],
      }),
      makeMdxFile("both-post", "/en/posts/both-post", {
        title: "Both Post",
        tags: ["ai", "web"],
      }),
    ];

    it("returns all posts when no tag filter is specified", async () => {
      stubSingleLangPosts(posts);
      const data = await getBlogIndexData();
      expect(data.posts).toHaveLength(3);
    });

    it("filters posts by tag when filter is provided", async () => {
      stubSingleLangPosts(posts);
      const data = await getBlogIndexData(undefined, { tag: "ai" });
      expect(data.posts).toHaveLength(2);
      expect(data.posts.every((p) => p.metadata.tags.includes("ai"))).toBe(
        true,
      );
    });

    it("normalises the tag filter slug for matching", async () => {
      stubSingleLangPosts([
        makeMdxFile("ml-post", "/en/posts/ml-post", {
          title: "ML Post",
          tags: ["Machine Learning"],
        }),
      ]);
      const data = await getBlogIndexData(undefined, {
        tag: "machine-learning",
      });
      expect(data.posts).toHaveLength(1);
    });

    it("returns empty posts array when tag matches nothing", async () => {
      stubSingleLangPosts(posts);
      const data = await getBlogIndexData(undefined, { tag: "nonexistent" });
      expect(data.posts).toHaveLength(0);
    });
  });

  describe("tags aggregation", () => {
    it("aggregates tags across all posts with counts", async () => {
      stubSingleLangPosts([
        makeMdxFile("a", "/en/posts/a", { title: "A", tags: ["ai", "ml"] }),
        makeMdxFile("b", "/en/posts/b", { title: "B", tags: ["ai"] }),
        makeMdxFile("c", "/en/posts/c", { title: "C", tags: ["web"] }),
      ]);

      const data = await getBlogIndexData();
      const tagNames = data.tags.map((t) => t.name);
      expect(tagNames).toEqual(expect.arrayContaining(["ai", "ml", "web"]));

      const aiTag = data.tags.find((t) => t.name === "ai");
      expect(aiTag).toBeDefined();
      expect(aiTag!.count).toBe(2);
    });

    it("sorts tags alphabetically", async () => {
      stubSingleLangPosts([
        makeMdxFile("z", "/en/posts/z", { title: "Z", tags: ["zebra"] }),
        makeMdxFile("a", "/en/posts/a", { title: "A", tags: ["apple"] }),
        makeMdxFile("m", "/en/posts/m", { title: "M", tags: ["mango"] }),
      ]);

      const data = await getBlogIndexData();
      expect(data.tags.map((t) => t.name)).toEqual(["apple", "mango", "zebra"]);
    });

    it("sorts posts within each tag by date descending", async () => {
      stubSingleLangPosts([
        makeMdxFile("old", "/en/posts/old", {
          title: "Old",
          date: "2020-01-01",
          tags: ["ai"],
        }),
        makeMdxFile("new", "/en/posts/new", {
          title: "New",
          date: "2024-06-01",
          tags: ["ai"],
        }),
      ]);

      const data = await getBlogIndexData();
      const aiTag = data.tags.find((t) => t.name === "ai");
      expect(aiTag!.posts.map((p) => p.title)).toEqual(["New", "Old"]);
    });

    it("omits the tags folder from pageMap when there are no tags", async () => {
      stubSingleLangPosts([
        makeMdxFile("no-tags", "/en/posts/no-tags", {
          title: "No Tags",
        }),
      ]);

      const data = await getBlogIndexData();
      const tagFolder = data.pageMap.find(
        (item) => "name" in item && (item as Folder).name === "tags",
      );
      expect(tagFolder).toBeUndefined();
    });

    it("includes the tags folder in pageMap when tags exist", async () => {
      stubSingleLangPosts([
        makeMdxFile("tagged", "/en/posts/tagged", {
          title: "Tagged",
          tags: ["ai"],
        }),
      ]);

      const data = await getBlogIndexData();
      const tagFolder = data.pageMap.find(
        (item) => "name" in item && (item as Folder).name === "tags",
      ) as Folder | undefined;
      expect(tagFolder).toBeDefined();
      expect(tagFolder!.route).toBe("/blog/tags");
    });
  });

  describe("pageMap structure", () => {
    it("always includes a data map as the first item", async () => {
      stubSingleLangPosts([]);

      const data = await getBlogIndexData();
      expect(data.pageMap.length).toBeGreaterThanOrEqual(1);
      const first = data.pageMap[0]!;
      expect(first).toHaveProperty("data");
    });

    it("includes an All Posts entry", async () => {
      stubSingleLangPosts([]);

      const data = await getBlogIndexData();
      const allPosts = data.pageMap.find(
        (item) => "name" in item && (item as MdxFile).name === "All Posts",
      ) as MdxFile | undefined;
      expect(allPosts).toBeDefined();
      expect(allPosts!.route).toBe("/blog/posts");
    });

    it("includes a recent_posts folder", async () => {
      stubSingleLangPosts([makeMdxFile("a", "/en/posts/a", { title: "A" })]);

      const data = await getBlogIndexData();
      const recentFolder = data.pageMap.find(
        (item) => "name" in item && (item as Folder).name === "recent_posts",
      ) as Folder | undefined;
      expect(recentFolder).toBeDefined();
      expect(recentFolder!.route).toBe("/blog/recent-posts");
      expect(recentFolder!.children).toHaveLength(1);
    });

    it("creates correct tag entries in the tags folder", async () => {
      stubSingleLangPosts([
        makeMdxFile("p", "/en/posts/p", {
          title: "P",
          tags: ["Machine Learning"],
        }),
      ]);

      const data = await getBlogIndexData();
      const tagFolder = data.pageMap.find(
        (item) => "name" in item && (item as Folder).name === "tags",
      ) as Folder | undefined;
      expect(tagFolder).toBeDefined();

      const tagChild = tagFolder!.children[0] as MdxFile;
      expect(tagChild.name).toBe("Machine Learning");
      expect((tagChild as unknown as Record<string, unknown>).title).toBe(
        "Machine Learning (1)",
      );
      expect(tagChild.route).toBe("/blog/tags/machine-learning");
    });
  });

  describe("preferred language propagation", () => {
    it("passes preferredLang to getAllPosts", async () => {
      const enItems = [makeMdxFile("post", "/en/posts/post", { title: "EN" })];
      const zhItems = [makeMdxFile("post", "/zh/posts/post", { title: "ZH" })];

      vi.mocked(getPageMap).mockImplementation(
        async (path?: string): Promise<PageMapItem[]> => {
          if (path === "/en/posts") return enItems as unknown as PageMapItem[];
          if (path === "/zh/posts") return zhItems as unknown as PageMapItem[];
          return [];
        },
      );

      const data = await getBlogIndexData("zh");
      expect(data.posts[0]!.lang).toBe("zh");
      expect(data.posts[0]!.title).toBe("ZH");
    });
  });
});

// ===================================================================
// BLOG_LANGS constant
// ===================================================================

describe("BLOG_LANGS", () => {
  it('contains "zh" and "en"', () => {
    expect(BLOG_LANGS).toEqual(["zh", "en"]);
  });

  it("is a readonly tuple", () => {
    // Verify it satisfies the BlogLang union
    const langs: readonly BlogLang[] = BLOG_LANGS;
    expect(langs).toHaveLength(2);
  });
});
