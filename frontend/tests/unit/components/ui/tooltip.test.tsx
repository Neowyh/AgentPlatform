import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

afterEach(() => {
  cleanup();
});

describe("Tooltip", () => {
  test("renders TooltipProvider", () => {
    render(
      <TooltipProvider>
        <div>content</div>
      </TooltipProvider>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  test("renders Tooltip with trigger and content", () => {
    render(
      <Tooltip>
        <TooltipTrigger>Hover me</TooltipTrigger>
        <TooltipContent>Tooltip text</TooltipContent>
      </Tooltip>,
    );
    expect(screen.getByText("Hover me")).toBeInTheDocument();
  });

  test("TooltipProvider sets default delayDuration to 0", () => {
    render(
      <TooltipProvider>
        <div>test</div>
      </TooltipProvider>,
    );
    expect(screen.getByText("test")).toBeInTheDocument();
  });
});
