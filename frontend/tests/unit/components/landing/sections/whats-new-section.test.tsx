import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ui/magic-bento", () => ({
  __esModule: true,
  default: ({ data }: any) => (
    <div data-testid="magic-bento">
      {data.map((card: any, i: number) => (
        <div key={i}>{card.title}</div>
      ))}
    </div>
  ),
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

vi.mock("../section", () => ({
  Section: ({ children, title, subtitle }: any) => (
    <div data-testid="section">
      <h2>{title}</h2>
      <p>{subtitle}</p>
      {children}
    </div>
  ),
}));

import { WhatsNewSection } from "@/components/landing/sections/whats-new-section";

afterEach(() => {
  cleanup();
});

describe("WhatsNewSection", () => {
  test("renders section title", () => {
    render(<WhatsNewSection />);
    expect(screen.getByText("Whats New in iDeer 2.0")).toBeInTheDocument();
  });

  test("renders section subtitle", () => {
    render(<WhatsNewSection />);
    expect(
      screen.getByText(/evolving from a Deep Research agent/),
    ).toBeInTheDocument();
  });

  test("renders MagicBento with feature cards", () => {
    render(<WhatsNewSection />);
    expect(screen.getByTestId("magic-bento")).toBeInTheDocument();
    expect(screen.getByText("Long/Short-term Memory")).toBeInTheDocument();
    expect(screen.getByText("Open Source")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <WhatsNewSection className="custom-section" />,
    );
    expect(container.querySelector(".custom-section")).toBeInTheDocument();
  });
});
