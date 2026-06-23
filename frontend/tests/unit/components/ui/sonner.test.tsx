import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock next-themes
vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "light" }),
}));

import { Toaster } from "@/components/ui/sonner";

afterEach(() => {
  cleanup();
});

describe("Toaster (Sonner)", () => {
  test("renders the toaster component", () => {
    const { container } = render(<Toaster />);
    expect(container).toBeInTheDocument();
  });
});
