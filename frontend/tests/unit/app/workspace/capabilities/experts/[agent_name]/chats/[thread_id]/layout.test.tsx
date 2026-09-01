import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInputProvider: ({ children }: any) => (
    <div data-testid="prompt-provider">{children}</div>
  ),
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactsProvider: ({ children }: any) => (
    <div data-testid="artifacts-provider">{children}</div>
  ),
}));

vi.mock("@/core/tasks/context", () => ({
  SubtasksProvider: ({ children }: any) => (
    <div data-testid="subtasks-provider">{children}</div>
  ),
}));

import AgentChatLayout from "@/app/workspace/capabilities/experts/[agent_name]/chats/[thread_id]/layout";

afterEach(() => {
  cleanup();
});

describe("AgentChatLayout", () => {
  test("renders children inside nested providers", () => {
    render(
      <AgentChatLayout>
        <div>Agent chat content</div>
      </AgentChatLayout>,
    );
    expect(screen.getByText("Agent chat content")).toBeInTheDocument();
  });

  test("renders all three providers", () => {
    render(
      <AgentChatLayout>
        <div>child</div>
      </AgentChatLayout>,
    );
    expect(screen.getByTestId("subtasks-provider")).toBeInTheDocument();
    expect(screen.getByTestId("artifacts-provider")).toBeInTheDocument();
    expect(screen.getByTestId("prompt-provider")).toBeInTheDocument();
  });
});
