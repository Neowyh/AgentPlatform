import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ui/galaxy", () => ({
  default: () => <div data-testid="galaxy" />,
}));

vi.mock("@/components/ui/flickering-grid", () => ({
  FlickeringGrid: () => <div data-testid="flickering-grid" />,
}));

vi.mock("@/components/ui/word-rotate", () => ({
  WordRotate: ({ words }: { words: string[] }) => (
    <div data-testid="word-rotate" data-words={words.join(",")}>
      {words[0]}
    </div>
  ),
}));

vi.mock("@/components/ui/aurora-text", () => ({
  AuroraText: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { Hero } from "@/components/landing/hero";

afterEach(() => {
  cleanup();
});

describe("Hero", () => {
  test("renders WordRotate with Chinese words", () => {
    render(<Hero />);
    const wordRotate = screen.getByTestId("word-rotate");
    const words = wordRotate.getAttribute("data-words")?.split(",") ?? [];
    expect(words).toEqual([
      "文档处理",
      "翻译润色",
      "数据分析",
      "前端设计",
      "代码开发",
      "专业设计",
    ]);
  });

  test("renders iDeer tagline", () => {
    render(<Hero />);
    expect(screen.getByText("iDeer，实现你的idea")).toBeInTheDocument();
  });

  test("renders CTA button with Chinese text", () => {
    render(<Hero />);
    expect(screen.getByRole("link", { name: /开始创造/ })).toHaveAttribute(
      "href",
      "/login?next=%2Fworkspace",
    );
  });

  test("uses the warm-paper landing theme hooks", () => {
    const { container } = render(<Hero />);
    expect(container.querySelector("[data-testid='galaxy']")).toBeNull();
    expect(
      container.querySelector("[data-testid='flickering-grid']"),
    ).toBeNull();
    expect(screen.getByRole("heading")).toHaveClass("text-[#3d2b1f]");
  });

  test("does not render English words in WordRotate", () => {
    render(<Hero />);
    const wordRotate = screen.getByTestId("word-rotate");
    const words = wordRotate.getAttribute("data-words") ?? "";
    expect(words).not.toContain("Deep Research");
    expect(words).not.toContain("Generate Slides");
    expect(words).not.toContain("Vibe Coding");
  });
});
