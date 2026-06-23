import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { WhatsNewSection } from "@/components/landing/sections/whats-new-section";

afterEach(() => {
  cleanup();
});

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

describe("WhatsNewSection", () => {
  test("renders the section title", () => {
    render(<WhatsNewSection />);
    expect(screen.getByText("Whats New in iDeer 2.0")).toBeInTheDocument();
  });

  test("renders the subtitle", () => {
    render(<WhatsNewSection />);
    expect(
      screen.getByText(/evolving from a Deep Research agent/),
    ).toBeInTheDocument();
  });
});
