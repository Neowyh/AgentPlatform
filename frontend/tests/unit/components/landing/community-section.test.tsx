import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CommunitySection } from "@/components/landing/sections/community-section";

afterEach(() => {
  cleanup();
});

// Mock next/navigation to provide pathname
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
}));

describe("CommunitySection", () => {
  test("renders the section title", () => {
    render(<CommunitySection />);
    expect(screen.getAllByText("Join the Community").length).toBeGreaterThan(0);
  });

  test("renders the subtitle text", () => {
    render(<CommunitySection />);
    expect(screen.getByText(/Contribute brilliant ideas/)).toBeInTheDocument();
  });

  test("renders the Contribute Now button", () => {
    render(<CommunitySection />);
    expect(screen.getByText("Contribute Now")).toBeInTheDocument();
  });
});
