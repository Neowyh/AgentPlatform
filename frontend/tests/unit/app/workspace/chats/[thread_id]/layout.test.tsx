import { render, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

let mockStaticOnly = false;

vi.mock("@/core/static-mode", () => ({
  isStaticWebsiteOnly: () => mockStaticOnly,
}));

vi.mock("@/env", () => ({
  env: { NEXT_PUBLIC_STATIC_WEBSITE_ONLY: undefined },
}));

vi.mock("@/core/threads/static-demo", () => ({
  DEMO_THREAD_IDS: ["id-1", "id-2"],
}));

vi.mock("@/app/workspace/chats/[thread_id]/providers", () => ({
  ChatProviders: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="chat-providers">{children}</div>
  ),
}));

import ChatLayout, {
  generateStaticParams,
} from "@/app/workspace/chats/[thread_id]/layout";

afterEach(() => {
  cleanup();
  mockStaticOnly = false;
});

describe("ChatLayout", () => {
  test("renders ChatProviders wrapping children", () => {
    const { getByTestId, getByText } = render(
      <ChatLayout>
        <div>page content</div>
      </ChatLayout>,
    );
    expect(getByTestId("chat-providers")).toBeInTheDocument();
    expect(getByText("page content")).toBeInTheDocument();
  });
});

describe("generateStaticParams", () => {
  test("returns empty array when not in static mode", () => {
    mockStaticOnly = false;
    expect(generateStaticParams()).toEqual([]);
  });

  test("returns thread IDs when in static mode", () => {
    mockStaticOnly = true;
    const result = generateStaticParams();
    expect(result).toEqual([{ thread_id: "id-1" }, { thread_id: "id-2" }]);
  });
});
