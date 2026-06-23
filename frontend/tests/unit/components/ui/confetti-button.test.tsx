import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock canvas-confetti
vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

import confetti from "canvas-confetti";

import { ConfettiButton } from "@/components/ui/confetti-button";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ConfettiButton", () => {
  test("renders as a button with text", () => {
    render(<ConfettiButton>Celebrate!</ConfettiButton>);
    expect(screen.getByText("Celebrate!")).toBeInTheDocument();
  });

  test("renders as a button element", () => {
    render(<ConfettiButton data-testid="cb">Click</ConfettiButton>);
    expect(screen.getByTestId("cb").tagName).toBe("BUTTON");
  });

  test("fires confetti on click", () => {
    render(<ConfettiButton data-testid="cb">Click</ConfettiButton>);
    fireEvent.click(screen.getByTestId("cb"));
    expect(confetti).toHaveBeenCalledTimes(1);
  });

  test("calls custom onClick handler", () => {
    const handleClick = vi.fn();
    render(
      <ConfettiButton onClick={handleClick} data-testid="cb">
        Click
      </ConfettiButton>,
    );
    fireEvent.click(screen.getByTestId("cb"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  test("passes confetti options correctly", () => {
    render(
      <ConfettiButton
        angle={180}
        particleCount={100}
        startVelocity={50}
        spread={90}
        data-testid="cb"
      >
        Click
      </ConfettiButton>,
    );
    fireEvent.click(screen.getByTestId("cb"));
    expect(confetti).toHaveBeenCalledWith(
      expect.objectContaining({
        angle: 180,
        particleCount: 100,
        startVelocity: 50,
        spread: 90,
      }),
    );
  });

  test("applies custom className", () => {
    render(
      <ConfettiButton className="custom-cb" data-testid="cb-custom">
        Click
      </ConfettiButton>,
    );
    expect(screen.getByTestId("cb-custom")).toHaveClass("custom-cb");
  });
});
