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
    expect(screen.getByText("iDeer 2.0 新功能")).toBeInTheDocument();
  });

  test("renders the subtitle", () => {
    render(<WhatsNewSection />);
    expect(screen.getByText(/从 Deep Research 智能体进化/)).toBeInTheDocument();
  });
});
