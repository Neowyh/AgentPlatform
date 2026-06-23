import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      pages: {
        untitled: "Untitled",
        newChat: "New Chat",
        appName: "iDeer",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

let mockIsNewThread = false;
vi.mock("@/components/workspace/chats", () => ({
  useThreadChat: () => ({
    isNewThread: mockIsNewThread,
  }),
}));

vi.mock("@/components/workspace/flip-display", () => ({
  FlipDisplay: ({
    children,
    uniqueKey,
  }: {
    children: React.ReactNode;
    uniqueKey: string;
  }) => (
    <div data-testid="flip-display" data-key={uniqueKey}>
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ThreadTitle: typeof import("@/components/workspace/thread-title").ThreadTitle;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/thread-title");
  ThreadTitle = mod.ThreadTitle;
});

afterEach(() => {
  cleanup();
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeThread(overrides: Record<string, unknown> = {}) {
  return {
    messages: [],
    isLoading: false,
    isThreadLoading: false,
    values: { title: "Test Title", artifacts: [] },
    getMessagesMetadata: vi.fn(),
    ...overrides,
  } as any;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ThreadTitle", () => {
  test("renders title in FlipDisplay when title exists", () => {
    const thread = makeThread({ values: { title: "My Thread" } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    expect(screen.getByTestId("flip-display")).toBeInTheDocument();
    expect(screen.getByText("My Thread")).toBeInTheDocument();
  });

  test("returns null when no title", () => {
    const thread = makeThread({ values: { title: undefined } });
    const { container } = render(
      <ThreadTitle threadId="t-1" thread={thread} />,
    );
    expect(container.innerHTML).toBe("");
  });

  test("sets document.title with the thread title", () => {
    const thread = makeThread({ values: { title: "Hello" } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    expect(document.title).toBe("Hello - iDeer");
  });

  test("sets document.title to loading when isThreadLoading", () => {
    const thread = makeThread({
      values: { title: "Hello" },
      isThreadLoading: true,
    });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    expect(document.title).toBe("Loading... - iDeer");
  });

  test("sets document.title to Untitled when no title and not new", () => {
    const thread = makeThread({ values: { title: undefined } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    expect(document.title).toBe("Untitled - iDeer");
  });

  test("passes threadId as uniqueKey to FlipDisplay", () => {
    const thread = makeThread({ values: { title: "Hi" } });
    render(<ThreadTitle threadId="thread-abc" thread={thread} />);
    expect(screen.getByTestId("flip-display")).toHaveAttribute(
      "data-key",
      "thread-abc",
    );
  });

  test("renders fallback text when title is null", () => {
    const thread = makeThread({ values: { title: null } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    // When title is null, it returns null (no render)
    expect(screen.queryByTestId("flip-display")).not.toBeInTheDocument();
  });

  test("renders when title is empty string", () => {
    const thread = makeThread({ values: { title: "" } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    // Empty string is falsy, so returns null
    expect(screen.queryByTestId("flip-display")).not.toBeInTheDocument();
  });

  test("sets document.title to New Chat when isNewThread and no title", () => {
    mockIsNewThread = true;
    const thread = makeThread({ values: { title: undefined } });
    render(<ThreadTitle threadId="t-1" thread={thread} />);
    expect(document.title).toBe("New Chat - iDeer");
    mockIsNewThread = false;
  });
});
