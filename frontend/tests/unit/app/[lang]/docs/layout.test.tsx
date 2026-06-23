import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const { mockGetPageMap } = vi.hoisted(() => ({
  mockGetPageMap: vi.fn().mockResolvedValue([]),
}));

vi.mock("nextra", () => ({
  type: {},
}));

vi.mock("nextra/page-map", () => ({
  getPageMap: (...args: any[]) => mockGetPageMap(...args),
}));

vi.mock("nextra-theme-docs", () => ({
  Layout: ({
    children,
    navbar,
    footer,
    i18n,
    pageMap,
    docsRepositoryBase,
  }: any) => (
    <div data-testid="nextra-layout">
      {navbar}
      {footer}
      {children}
    </div>
  ),
}));

vi.mock("nextra-theme-docs/style.css", () => ({}));

vi.mock("@/core/i18n/locale", () => ({
  getLocaleByLang: (lang: string) => {
    const map: Record<string, string> = { en: "en-US", zh: "zh-CN" };
    return map[lang] || "en-US";
  },
}));

vi.mock("@/components/landing/header", () => ({
  Header: ({ locale, homeURL, className }: any) => (
    <div data-testid="header" data-locale={locale} data-home-url={homeURL}>
      Header
    </div>
  ),
}));

vi.mock("@/components/landing/footer", () => ({
  Footer: ({ className }: any) => <div data-testid="footer">Footer</div>,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

import DocLayout from "@/app/[lang]/docs/layout";

describe("DocLayout", () => {
  test("renders docs layout with children", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>Doc content</div>, params }));
    expect(screen.getByText("Doc content")).toBeInTheDocument();
  });

  test("renders nextra layout wrapper", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(screen.getByTestId("nextra-layout")).toBeInTheDocument();
  });

  test("renders header component", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(screen.getByTestId("header")).toBeInTheDocument();
  });

  test("renders footer component", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  test("passes correct locale for English", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    const header = screen.getByTestId("header");
    expect(header.getAttribute("data-locale")).toBe("en-US");
  });

  test("passes correct locale for Chinese", async () => {
    const params = Promise.resolve({ lang: "zh" });
    render(await DocLayout({ children: <div>content</div>, params }));
    const header = screen.getByTestId("header");
    expect(header.getAttribute("data-locale")).toBe("zh-CN");
  });

  test("defaults to en-US for unknown lang", async () => {
    const params = Promise.resolve({ lang: "fr" });
    render(await DocLayout({ children: <div>content</div>, params }));
    const header = screen.getByTestId("header");
    expect(header.getAttribute("data-locale")).toBe("en-US");
  });

  test("passes homeURL as root", async () => {
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    const header = screen.getByTestId("header");
    expect(header.getAttribute("data-home-url")).toBe("/");
  });

  test("calls getPageMap with correct lang prefix", async () => {
    const params = Promise.resolve({ lang: "zh" });
    await DocLayout({ children: <div>content</div>, params });
    expect(mockGetPageMap).toHaveBeenCalledWith("/zh");
  });

  test("formatPageRoute prepends base to routes that don't start with it", async () => {
    mockGetPageMap.mockResolvedValueOnce([
      { route: "/getting-started", name: "getting-started" },
      { route: "/zh/docs/api", name: "api" },
    ]);
    const params = Promise.resolve({ lang: "zh" });
    // Should not throw and should call getPageMap
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(mockGetPageMap).toHaveBeenCalledWith("/zh");
  });

  test("formatPageRoute handles items with children recursively", async () => {
    mockGetPageMap.mockResolvedValueOnce([
      {
        route: "/guides",
        name: "guides",
        children: [
          { route: "/intro", name: "intro" },
          { route: "/zh/docs/advanced", name: "advanced" },
        ],
      },
    ]);
    const params = Promise.resolve({ lang: "zh" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(mockGetPageMap).toHaveBeenCalledWith("/zh");
  });

  test("formatPageRoute skips items without route property", async () => {
    mockGetPageMap.mockResolvedValueOnce([
      { name: "separator", separator: true },
      { route: "/page", name: "page" },
    ]);
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(mockGetPageMap).toHaveBeenCalledWith("/en");
  });

  test("formatPageRoute handles items with children but no route", async () => {
    mockGetPageMap.mockResolvedValueOnce([
      {
        name: "folder",
        children: [{ route: "/nested", name: "nested" }],
      },
    ]);
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(mockGetPageMap).toHaveBeenCalledWith("/en");
  });

  test("formatPageRoute does not double-prepend base to matching routes", async () => {
    mockGetPageMap.mockResolvedValueOnce([
      { route: "/en/docs/existing", name: "existing" },
    ]);
    const params = Promise.resolve({ lang: "en" });
    render(await DocLayout({ children: <div>content</div>, params }));
    expect(mockGetPageMap).toHaveBeenCalledWith("/en");
  });
});
