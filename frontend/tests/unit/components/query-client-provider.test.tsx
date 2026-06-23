import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { QueryClientProvider } from "@/components/query-client-provider";

afterEach(() => {
  cleanup();
});

describe("QueryClientProvider", () => {
  test("renders children", () => {
    render(
      <QueryClientProvider>
        <span>child content</span>
      </QueryClientProvider>,
    );
    expect(screen.getByText("child content")).toBeInTheDocument();
  });
});
