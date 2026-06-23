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

import { ChatProviders } from "@/app/workspace/chats/[thread_id]/providers";

afterEach(() => {
  cleanup();
});

describe("ChatProviders", () => {
  test("renders children inside nested providers", () => {
    render(
      <ChatProviders>
        <div>Chat content</div>
      </ChatProviders>,
    );
    expect(screen.getByText("Chat content")).toBeInTheDocument();
  });

  test("renders SubtasksProvider", () => {
    render(
      <ChatProviders>
        <div>child</div>
      </ChatProviders>,
    );
    expect(screen.getByTestId("subtasks-provider")).toBeInTheDocument();
  });

  test("renders ArtifactsProvider", () => {
    render(
      <ChatProviders>
        <div>child</div>
      </ChatProviders>,
    );
    expect(screen.getByTestId("artifacts-provider")).toBeInTheDocument();
  });

  test("renders PromptInputProvider", () => {
    render(
      <ChatProviders>
        <div>child</div>
      </ChatProviders>,
    );
    expect(screen.getByTestId("prompt-provider")).toBeInTheDocument();
  });
});
