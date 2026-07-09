import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Progress } from "@/components/ui/progress";

describe("Progress accessibility", () => {
  it("has progressbar role", () => {
    render(<Progress value={50} />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("has aria-valuemin defaulting to 0", () => {
    render(<Progress value={50} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuemin",
      "0",
    );
  });

  it("has aria-valuemax defaulting to 100", () => {
    render(<Progress value={50} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuemax",
      "100",
    );
  });

  it("has accessible name from aria-label", () => {
    render(<Progress aria-label="Upload progress" value={60} />);
    expect(
      screen.getByRole("progressbar", { name: /upload progress/i }),
    ).toBeInTheDocument();
  });

  it("value 0 renders correctly with progressbar role", () => {
    render(<Progress value={0} />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("value 100 renders correctly with progressbar role", () => {
    render(<Progress value={100} />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("progress conveys min and max to assistive technology", () => {
    render(<Progress value={42} />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuemin", "0");
    expect(progressbar).toHaveAttribute("aria-valuemax", "100");
  });

  it("supports custom max value", () => {
    render(<Progress value={5} max={10} />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar).toHaveAttribute("aria-valuemax", "10");
    expect(progressbar).toHaveAttribute("aria-valuemin", "0");
  });

  it("sets aria-valuenow when value is provided", () => {
    render(<Progress value={42} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "42",
    );
  });
});
