import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInputProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="prompt-input-provider">{children}</div>
  ),
}));

vi.mock("@/components/workspace/artifacts", () => ({
  ArtifactsProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="artifacts-provider">{children}</div>
  ),
}));

vi.mock("@/core/tasks/context", () => ({
  SubtasksProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="subtasks-provider">{children}</div>
  ),
}));

import { ChatProviders } from "@/app/workspace/chats/[thread_id]/providers";

afterEach(() => {
  cleanup();
});

describe("ChatProviders", () => {
  test("renders all providers nested correctly", () => {
    const { getByTestId } = render(
      <ChatProviders>
        <div>child</div>
      </ChatProviders>,
    );
    expect(getByTestId("subtasks-provider")).toBeInTheDocument();
    expect(getByTestId("artifacts-provider")).toBeInTheDocument();
    expect(getByTestId("prompt-input-provider")).toBeInTheDocument();
  });

  test("renders children inside providers", () => {
    const { getByText } = render(
      <ChatProviders>
        <span>inner content</span>
      </ChatProviders>,
    );
    expect(getByText("inner content")).toBeInTheDocument();
  });
});
