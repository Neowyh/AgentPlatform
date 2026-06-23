import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/workspace/agents/agent-gallery", () => ({
  AgentGallery: () => <div data-testid="agent-gallery">Agent Gallery</div>,
}));

import AgentsPage from "@/app/workspace/agents/page";

afterEach(() => {
  cleanup();
});

describe("AgentsPage", () => {
  test("renders AgentGallery component", () => {
    render(<AgentsPage />);
    expect(screen.getByTestId("agent-gallery")).toBeInTheDocument();
  });

  test("renders AgentGallery with expected text", () => {
    render(<AgentsPage />);
    expect(screen.getByText("Agent Gallery")).toBeInTheDocument();
  });
});
