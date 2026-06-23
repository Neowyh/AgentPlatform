import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
} from "@/components/ai-elements/conversation";

afterEach(() => {
  cleanup();
});

// Mock use-stick-to-bottom - StickToBottom.Content is a nested property
vi.mock("use-stick-to-bottom", () => {
  const StickToBottomComponent = ({
    children,
    className,
    role,
    ...props
  }: Record<string, unknown>) => (
    <div
      className={className as string}
      role={role as string}
      data-testid="stick-to-bottom"
      {...props}
    >
      {children as React.ReactNode}
    </div>
  );
  const StickToBottomContentComponent = ({
    children,
    className,
    ...props
  }: Record<string, unknown>) => (
    <div
      className={className as string}
      data-testid="stick-to-bottom-content"
      {...props}
    >
      {children as React.ReactNode}
    </div>
  );
  // Attach Content as a static property
  StickToBottomComponent.Content = StickToBottomContentComponent;

  return {
    StickToBottom: StickToBottomComponent,
    StickToBottomContent: StickToBottomContentComponent,
    useStickToBottomContext: () => ({
      isAtBottom: true,
      scrollToBottom: vi.fn(),
    }),
  };
});

describe("Conversation", () => {
  test("renders with children", () => {
    render(
      <Conversation data-testid="conversation">
        <p>Conversation content</p>
      </Conversation>,
    );
    expect(screen.getByTestId("conversation")).toBeInTheDocument();
    expect(screen.getByText("Conversation content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Conversation className="custom-conversation" data-testid="conversation">
        <p>Content</p>
      </Conversation>,
    );
    expect(screen.getByTestId("conversation")).toHaveClass(
      "custom-conversation",
    );
  });

  test("has role=log attribute", () => {
    render(
      <Conversation data-testid="conversation">
        <p>Content</p>
      </Conversation>,
    );
    expect(screen.getByTestId("conversation")).toHaveAttribute("role", "log");
  });

  test("has overflow-y-hidden class", () => {
    render(
      <Conversation data-testid="conversation">
        <p>Content</p>
      </Conversation>,
    );
    expect(screen.getByTestId("conversation").className).toContain(
      "overflow-y-hidden",
    );
  });

  test("passes additional props", () => {
    render(
      <Conversation aria-label="Chat conversation" data-testid="conversation">
        <p>Content</p>
      </Conversation>,
    );
    expect(screen.getByTestId("conversation")).toHaveAttribute(
      "aria-label",
      "Chat conversation",
    );
  });
});

describe("ConversationContent", () => {
  test("renders children", () => {
    render(
      <Conversation>
        <ConversationContent data-testid="content">
          <p>Message 1</p>
          <p>Message 2</p>
        </ConversationContent>
      </Conversation>,
    );
    expect(screen.getByText("Message 1")).toBeInTheDocument();
    expect(screen.getByText("Message 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Conversation>
        <ConversationContent className="custom-content" data-testid="content">
          <p>Content</p>
        </ConversationContent>
      </Conversation>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });

  test("has flex and gap classes", () => {
    render(
      <Conversation>
        <ConversationContent data-testid="content">
          <p>Content</p>
        </ConversationContent>
      </Conversation>,
    );
    const el = screen.getByTestId("content");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("flex-col");
    expect(el.className).toContain("gap-8");
  });

  test("has padding class", () => {
    render(
      <Conversation>
        <ConversationContent data-testid="content">
          <p>Content</p>
        </ConversationContent>
      </Conversation>,
    );
    expect(screen.getByTestId("content").className).toContain("p-4");
  });
});

describe("ConversationEmptyState", () => {
  test("renders with default title and description", () => {
    render(<ConversationEmptyState data-testid="empty" />);
    expect(screen.getByText("No messages yet")).toBeInTheDocument();
    expect(
      screen.getByText("Start a conversation to see messages here"),
    ).toBeInTheDocument();
  });

  test("renders custom title", () => {
    render(<ConversationEmptyState title="Custom Title" data-testid="empty" />);
    expect(screen.getByText("Custom Title")).toBeInTheDocument();
  });

  test("renders custom description", () => {
    render(
      <ConversationEmptyState
        description="Custom description"
        data-testid="empty"
      />,
    );
    expect(screen.getByText("Custom description")).toBeInTheDocument();
  });

  test("renders icon when provided", () => {
    render(
      <ConversationEmptyState
        icon={<span data-testid="empty-icon">Icon</span>}
        data-testid="empty"
      />,
    );
    expect(screen.getByTestId("empty-icon")).toBeInTheDocument();
  });

  test("does not render icon when not provided", () => {
    render(<ConversationEmptyState data-testid="empty" />);
    expect(screen.queryByTestId("empty-icon")).not.toBeInTheDocument();
  });

  test("renders children instead of default content", () => {
    render(
      <ConversationEmptyState data-testid="empty">
        <p>Custom empty state</p>
      </ConversationEmptyState>,
    );
    expect(screen.getByText("Custom empty state")).toBeInTheDocument();
    expect(screen.queryByText("No messages yet")).not.toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ConversationEmptyState className="custom-empty" data-testid="empty" />,
    );
    expect(screen.getByTestId("empty")).toHaveClass("custom-empty");
  });

  test("hides description when set to empty string", () => {
    render(<ConversationEmptyState description="" data-testid="empty" />);
    expect(screen.getByText("No messages yet")).toBeInTheDocument();
    expect(
      screen.queryByText("Start a conversation to see messages here"),
    ).not.toBeInTheDocument();
  });

  test("has centering layout classes", () => {
    render(<ConversationEmptyState data-testid="empty" />);
    const el = screen.getByTestId("empty");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("items-center");
    expect(el.className).toContain("justify-center");
    expect(el.className).toContain("text-center");
  });
});
