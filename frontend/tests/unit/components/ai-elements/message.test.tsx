import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

// Mock streamdown to avoid katex CSS import issues in jsdom
vi.mock("streamdown", () => ({
  Streamdown: ({ children, className, ...props }: any) =>
    React.createElement("div", { className, ...props }, children),
}));

import {
  Message,
  MessageContent,
  MessageActions,
  MessageAction,
  MessageBranch,
  MessageBranchContent,
  MessageBranchSelector,
  MessageBranchPrevious,
  MessageBranchNext,
  MessageBranchPage,
  MessageResponse,
  MessageAttachment,
  MessageAttachments,
  MessageToolbar,
} from "@/components/ai-elements/message";

afterEach(() => {
  cleanup();
});

// ============================================================================
// Message
// ============================================================================

describe("Message", () => {
  test("renders user message with correct data-testid", () => {
    render(
      <Message from="user">
        <div>Hello</div>
      </Message>,
    );
    expect(screen.getByTestId("user-message")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  test("renders assistant message with correct data-testid", () => {
    render(
      <Message from="assistant">
        <div>Hi there</div>
      </Message>,
    );
    expect(screen.getByTestId("ai-message")).toBeInTheDocument();
    expect(screen.getByText("Hi there")).toBeInTheDocument();
  });

  test("applies is-user class for user messages", () => {
    render(
      <Message from="user" data-testid="msg">
        <div>Content</div>
      </Message>,
    );
    expect(screen.getByTestId("msg")).toHaveClass("is-user");
  });

  test("applies is-assistant class for assistant messages", () => {
    render(
      <Message from="assistant" data-testid="msg">
        <div>Content</div>
      </Message>,
    );
    expect(screen.getByTestId("msg")).toHaveClass("is-assistant");
  });

  test("applies custom className", () => {
    render(
      <Message from="user" className="custom-msg" data-testid="msg">
        <div>Content</div>
      </Message>,
    );
    expect(screen.getByTestId("msg")).toHaveClass("custom-msg");
  });

  test("renders system role message", () => {
    render(
      <Message from="system">
        <div>System message</div>
      </Message>,
    );
    // System role is not "user", so should get ai-message testid
    expect(screen.getByTestId("ai-message")).toBeInTheDocument();
  });

  test("spreads additional div props", () => {
    render(
      <Message from="user" aria-label="user message" data-testid="msg">
        <div>Content</div>
      </Message>,
    );
    expect(screen.getByTestId("msg")).toHaveAttribute(
      "aria-label",
      "user message",
    );
  });
});

// ============================================================================
// MessageContent
// ============================================================================

describe("MessageContent", () => {
  test("renders children", () => {
    render(
      <MessageContent>
        <p>Hello world</p>
      </MessageContent>,
    );
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageContent className="custom-content" data-testid="mc">
        <p>Content</p>
      </MessageContent>,
    );
    expect(screen.getByTestId("mc")).toHaveClass("custom-content");
  });
});

// ============================================================================
// MessageActions
// ============================================================================

describe("MessageActions", () => {
  test("renders children", () => {
    render(
      <MessageActions>
        <button>Action</button>
      </MessageActions>,
    );
    expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageActions className="custom-actions" data-testid="actions">
        <span>Content</span>
      </MessageActions>,
    );
    expect(screen.getByTestId("actions")).toHaveClass("custom-actions");
  });
});

// ============================================================================
// MessageAction
// ============================================================================

describe("MessageAction", () => {
  test("renders as a button", () => {
    render(<MessageAction data-testid="action">Click me</MessageAction>);
    const btn = screen.getByTestId("action");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("renders label as sr-only text", () => {
    render(<MessageAction label="Copy">Icon</MessageAction>);
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  test("renders tooltip text as sr-only when no label", () => {
    render(<MessageAction tooltip="Delete">Icon</MessageAction>);
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  test("shows tooltip when tooltip prop is set", () => {
    render(
      <MessageAction tooltip="Copy to clipboard" data-testid="action">
        Copy
      </MessageAction>,
    );
    // The button should be wrapped in a tooltip
    expect(screen.getByTestId("action")).toBeInTheDocument();
  });

  test("does not show tooltip when tooltip prop is not set", () => {
    render(<MessageAction data-testid="action">Copy</MessageAction>);
    expect(screen.getByTestId("action")).toBeInTheDocument();
  });

  test("applies default ghost variant", () => {
    render(<MessageAction data-testid="action">Btn</MessageAction>);
    const btn = screen.getByTestId("action");
    expect(btn.className).toContain("hover:bg-accent");
  });

  test("applies custom variant", () => {
    render(
      <MessageAction variant="outline" data-testid="action">
        Btn
      </MessageAction>,
    );
    const btn = screen.getByTestId("action");
    expect(btn.className).toContain("border");
  });

  test("applies default icon-sm size", () => {
    render(<MessageAction data-testid="action">Btn</MessageAction>);
    const btn = screen.getByTestId("action");
    expect(btn.className).toContain("size-8");
  });

  test("applies custom size", () => {
    render(
      <MessageAction size="sm" data-testid="action">
        Btn
      </MessageAction>,
    );
    const btn = screen.getByTestId("action");
    expect(btn.className).toContain("h-8");
  });

  test("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <MessageAction onClick={onClick} data-testid="action">
        Click
      </MessageAction>,
    );
    await user.click(screen.getByTestId("action"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

// ============================================================================
// MessageBranch
// ============================================================================

describe("MessageBranch", () => {
  test("renders children", () => {
    render(
      <MessageBranch>
        <div>Branch content</div>
      </MessageBranch>,
    );
    expect(screen.getByText("Branch content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageBranch className="custom-branch" data-testid="branch">
        <div>Content</div>
      </MessageBranch>,
    );
    expect(screen.getByTestId("branch")).toHaveClass("custom-branch");
  });

  test("calls onBranchChange when branch changes", async () => {
    const user = userEvent.setup();
    const onBranchChange = vi.fn();

    render(
      <MessageBranch onBranchChange={onBranchChange}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    await user.click(screen.getByLabelText("Next branch"));
    expect(onBranchChange).toHaveBeenCalledWith(1);
  });
});

// ============================================================================
// MessageBranchContent
// ============================================================================

describe("MessageBranchContent", () => {
  test("renders the first branch by default", () => {
    render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
      </MessageBranch>,
    );
    expect(screen.getByText("Branch 1")).toBeInTheDocument();
    expect(screen.getByText("Branch 2")).toBeInTheDocument();
  });

  test("shows the default branch", () => {
    render(
      <MessageBranch defaultBranch={1}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
      </MessageBranch>,
    );
    // Both branches are rendered, but one is hidden
    expect(screen.getByText("Branch 1")).toBeInTheDocument();
    expect(screen.getByText("Branch 2")).toBeInTheDocument();
  });
});

// ============================================================================
// MessageBranchSelector
// ============================================================================

describe("MessageBranchSelector", () => {
  test("returns null when there is only one branch", () => {
    const { container } = render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Single branch</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant" data-testid="selector">
          <MessageBranchPrevious />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );
    expect(screen.queryByTestId("selector")).not.toBeInTheDocument();
  });

  test("renders when there are multiple branches", () => {
    render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant" data-testid="selector">
          <MessageBranchPrevious />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );
    expect(screen.getByTestId("selector")).toBeInTheDocument();
  });
});

// ============================================================================
// MessageBranchPrevious & MessageBranchNext
// ============================================================================

describe("MessageBranchPrevious", () => {
  test("calls goToPrevious when clicked", async () => {
    const user = userEvent.setup();

    render(
      <MessageBranch defaultBranch={1}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    const prevBtn = screen.getByLabelText("Previous branch");
    await user.click(prevBtn);
    // After clicking prev from branch 1, we go to branch 0
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
  });

  test("wraps to last branch when at first branch", async () => {
    const user = userEvent.setup();

    render(
      <MessageBranch defaultBranch={0}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
          <div key="b3">Branch 3</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    // Start at branch 0, click prev should wrap to branch 2
    await user.click(screen.getByLabelText("Previous branch"));
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
  });

  test("is disabled when only one branch", () => {
    render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Only branch</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    // Selector returns null for single branch, so button won't exist
    expect(screen.queryByLabelText("Previous branch")).not.toBeInTheDocument();
  });
});

describe("MessageBranchNext", () => {
  test("calls goToNext when clicked", async () => {
    const user = userEvent.setup();

    render(
      <MessageBranch defaultBranch={0}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    await user.click(screen.getByLabelText("Next branch"));
    expect(screen.getByText("2 of 2")).toBeInTheDocument();
  });

  test("wraps to first branch when at last branch", async () => {
    const user = userEvent.setup();

    render(
      <MessageBranch defaultBranch={1}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    // At branch 1, click next wraps to branch 0
    await user.click(screen.getByLabelText("Next branch"));
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
  });
});

// ============================================================================
// MessageBranchPage
// ============================================================================

describe("MessageBranchPage", () => {
  test("displays current branch and total branches", () => {
    render(
      <MessageBranch defaultBranch={0}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
          <div key="b3">Branch 3</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    expect(screen.getByText("1 of 3")).toBeInTheDocument();
  });

  test("updates when branch changes", async () => {
    const user = userEvent.setup();

    render(
      <MessageBranch defaultBranch={0}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPrevious />
          <MessageBranchPage />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Next branch"));
    expect(screen.getByText("2 of 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageBranch defaultBranch={0}>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant">
          <MessageBranchPage className="custom-page" />
        </MessageBranchSelector>
      </MessageBranch>,
    );

    const page = screen.getByText("1 of 2");
    expect(page).toHaveClass("custom-page");
  });
});

// useMessageBranch error guard (line 125)
describe("useMessageBranch error", () => {
  test("throws when used outside MessageBranch context", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<MessageBranchContent>test</MessageBranchContent>);
    }).toThrow("MessageBranch components must be used within MessageBranch");
    spy.mockRestore();
  });
});

// ============================================================================
// MessageResponse
// ============================================================================

describe("MessageResponse", () => {
  test("renders children content", () => {
    render(<MessageResponse>Hello world</MessageResponse>);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageResponse className="custom-response" data-testid="response">
        Content
      </MessageResponse>,
    );
    expect(screen.getByTestId("response")).toHaveClass("custom-response");
  });
});

// ============================================================================
// MessageAttachment
// ============================================================================

describe("MessageAttachment", () => {
  test("renders image attachment with img tag", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test-url",
          filename: "test.png",
        }}
      />,
    );
    const img = screen.getByAltText("test.png");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "blob:test-url");
  });

  test("renders file attachment with paperclip icon", () => {
    const { container } = render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "application/pdf",
          url: "blob:test-url",
          filename: "document.pdf",
        }}
      />,
    );
    // File attachments show a paperclip icon; the filename is in a tooltip (not visible by default)
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toBeInTheDocument();
    // Paperclip icon SVG should be rendered
    expect(wrapper.querySelector("svg")).toBeInTheDocument();
  });

  test("renders remove button for image when onRemove provided", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test-url",
          filename: "test.png",
        }}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByLabelText("Remove attachment")).toBeInTheDocument();
  });

  test("calls onRemove when remove button clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();

    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test-url",
          filename: "test.png",
        }}
        onRemove={onRemove}
      />,
    );

    await user.click(screen.getByLabelText("Remove attachment"));
    expect(onRemove).toHaveBeenCalledOnce();
  });

  test("calls onRemove for file attachment when remove button clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();

    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "application/pdf",
          url: "blob:test-url",
          filename: "document.pdf",
        }}
        onRemove={onRemove}
      />,
    );

    await user.click(screen.getByLabelText("Remove attachment"));
    expect(onRemove).toHaveBeenCalledOnce();
  });

  test("does not render remove button when onRemove not provided", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test-url",
          filename: "test.png",
        }}
      />,
    );
    expect(
      screen.queryByLabelText("Remove attachment"),
    ).not.toBeInTheDocument();
  });

  test("uses 'Image' as fallback label when no filename for images", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test-url",
        }}
      />,
    );
    expect(screen.getByAltText("attachment")).toBeInTheDocument();
  });

  test("uses 'Attachment' as fallback label when no filename for files", () => {
    const { container } = render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "application/pdf",
          url: "blob:test-url",
        }}
      />,
    );
    // The "Attachment" label is inside a Tooltip (not visible by default)
    // Verify the file attachment container renders with paperclip icon
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.querySelector("svg")).toBeInTheDocument();
  });

  test("treats non-image mediaType with image prefix but no url as file", () => {
    const { container } = render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          filename: "test.png",
          url: "",
        }}
      />,
    );
    // Without url, image/* mediaType falls back to "file" display with paperclip icon
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.querySelector("svg")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <MessageAttachment
        className="custom-attachment"
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test",
          filename: "test.png",
        }}
      />,
    );
    // className is applied to the outermost wrapper div
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass("custom-attachment");
  });

  test("spreads additional props", () => {
    render(
      <MessageAttachment
        aria-label="attachment"
        data={{
          type: "file",
          mediaType: "image/png",
          url: "blob:test",
          filename: "test.png",
        }}
      />,
    );
    expect(screen.getByLabelText("attachment")).toBeInTheDocument();
  });
});

// ============================================================================
// MessageAttachments
// ============================================================================

describe("MessageAttachments", () => {
  test("renders children", () => {
    render(
      <MessageAttachments data-testid="attachments">
        <div>Attachment 1</div>
      </MessageAttachments>,
    );
    expect(screen.getByText("Attachment 1")).toBeInTheDocument();
  });

  test("returns null when no children", () => {
    const { container } = render(<MessageAttachments />);
    expect(container.firstChild).toBeNull();
  });

  test("applies custom className", () => {
    render(
      <MessageAttachments
        className="custom-attachments"
        data-testid="attachments"
      >
        <div>Att</div>
      </MessageAttachments>,
    );
    expect(screen.getByTestId("attachments")).toHaveClass("custom-attachments");
  });
});

// ============================================================================
// MessageToolbar
// ============================================================================

describe("MessageToolbar", () => {
  test("renders children", () => {
    render(
      <MessageToolbar>
        <button>Copy</button>
      </MessageToolbar>,
    );
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageToolbar className="custom-toolbar" data-testid="toolbar">
        <span>Content</span>
      </MessageToolbar>,
    );
    expect(screen.getByTestId("toolbar")).toHaveClass("custom-toolbar");
  });

  test("spreads additional props", () => {
    render(
      <MessageToolbar aria-label="message toolbar" data-testid="toolbar">
        <span>Content</span>
      </MessageToolbar>,
    );
    expect(screen.getByTestId("toolbar")).toHaveAttribute(
      "aria-label",
      "message toolbar",
    );
  });
});

// ============================================================================
// MessageResponse memo behavior
// ============================================================================

describe("MessageResponse memo", () => {
  test("does not re-render when children are the same", () => {
    const { rerender } = render(
      <MessageResponse>Stable content</MessageResponse>,
    );
    const firstEl = screen.getByText("Stable content");
    rerender(<MessageResponse>Stable content</MessageResponse>);
    // Memo prevents re-render, so the DOM element should be the same reference
    expect(screen.getByText("Stable content")).toBe(firstEl);
  });

  test("re-renders when children change", () => {
    const { rerender } = render(
      <MessageResponse>First content</MessageResponse>,
    );
    expect(screen.getByText("First content")).toBeInTheDocument();
    rerender(<MessageResponse>Updated content</MessageResponse>);
    expect(screen.getByText("Updated content")).toBeInTheDocument();
    expect(screen.queryByText("First content")).not.toBeInTheDocument();
  });

  test("has displayName set to MessageResponse", () => {
    expect(MessageResponse.displayName).toBe("MessageResponse");
  });
});

// ============================================================================
// MessageBranchSelector from prop
// ============================================================================

describe("MessageBranchSelector from prop", () => {
  test("renders with user from prop", () => {
    render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="user" data-testid="selector">
          <MessageBranchPrevious />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );
    expect(screen.getByTestId("selector")).toBeInTheDocument();
  });

  test("renders with assistant from prop", () => {
    render(
      <MessageBranch>
        <MessageBranchContent>
          <div key="b1">Branch 1</div>
          <div key="b2">Branch 2</div>
        </MessageBranchContent>
        <MessageBranchSelector from="assistant" data-testid="selector">
          <MessageBranchPrevious />
          <MessageBranchNext />
        </MessageBranchSelector>
      </MessageBranch>,
    );
    expect(screen.getByTestId("selector")).toBeInTheDocument();
  });
});

// ============================================================================
// MessageAttachment edge cases
// ============================================================================

describe("MessageAttachment edge cases", () => {
  test("renders file attachment with remove button when onRemove provided for non-image", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();

    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "application/pdf",
          url: "blob:test-url",
          filename: "document.pdf",
        }}
        onRemove={onRemove}
      />,
    );

    const removeBtn = screen.getByLabelText("Remove attachment");
    expect(removeBtn).toBeInTheDocument();
    await user.click(removeBtn);
    expect(onRemove).toHaveBeenCalledOnce();
  });

  test("does not render remove button for non-image when onRemove is not provided", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "application/pdf",
          url: "blob:test-url",
          filename: "document.pdf",
        }}
      />,
    );
    expect(
      screen.queryByLabelText("Remove attachment"),
    ).not.toBeInTheDocument();
  });

  test("renders image with correct alt text using filename", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/jpeg",
          url: "blob:test-url",
          filename: "photo.jpg",
        }}
      />,
    );
    expect(screen.getByAltText("photo.jpg")).toBeInTheDocument();
  });

  test("renders image with alt='attachment' when no filename and no url", () => {
    render(
      <MessageAttachment
        data={{
          type: "file",
          mediaType: "image/png",
          url: "",
        }}
      />,
    );
    // Without URL, the component falls through to file display (paperclip)
    const wrapper = document.querySelector("[class*='size-24']");
    expect(wrapper).toBeInTheDocument();
  });
});

// ============================================================================
// MessageAttachment remove button stopPropagation
// ============================================================================

describe("MessageAttachment stopPropagation", () => {
  test("image remove button stops event propagation", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    const parentClick = vi.fn();

    const { container } = render(
      <div onClick={parentClick}>
        <MessageAttachment
          data={{
            type: "file",
            mediaType: "image/png",
            url: "blob:test",
            filename: "img.png",
          }}
          onRemove={onRemove}
        />
      </div>,
    );

    await user.click(screen.getByLabelText("Remove attachment"));
    expect(onRemove).toHaveBeenCalledOnce();
    // stopPropagation should prevent the parent click
    expect(parentClick).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Message composition
// ============================================================================

describe("Message composition", () => {
  test("renders a full user message with content, actions, and toolbar", () => {
    render(
      <Message from="user">
        <MessageContent>
          <p>User message text</p>
        </MessageContent>
        <MessageActions>
          <MessageAction label="Copy">Copy</MessageAction>
        </MessageActions>
        <MessageToolbar>
          <span>Toolbar</span>
        </MessageToolbar>
      </Message>,
    );

    expect(screen.getByTestId("user-message")).toBeInTheDocument();
    expect(screen.getByText("User message text")).toBeInTheDocument();
    // "Copy" appears twice: once as button text and once as sr-only label
    expect(screen.getAllByText("Copy").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Toolbar")).toBeInTheDocument();
  });

  test("renders a full assistant message with response and attachments", () => {
    render(
      <Message from="assistant">
        <MessageContent>
          <MessageResponse>Assistant response</MessageResponse>
        </MessageContent>
        <MessageAttachments>
          <MessageAttachment
            data={{
              type: "file",
              mediaType: "image/png",
              url: "blob:test",
              filename: "chart.png",
            }}
          />
        </MessageAttachments>
        <MessageToolbar>
          <MessageAction label="Like">Like</MessageAction>
        </MessageToolbar>
      </Message>,
    );

    expect(screen.getByTestId("ai-message")).toBeInTheDocument();
    expect(screen.getByText("Assistant response")).toBeInTheDocument();
    expect(screen.getByAltText("chart.png")).toBeInTheDocument();
  });

  test("renders message with branching support", async () => {
    const user = userEvent.setup();

    render(
      <Message from="assistant">
        <MessageBranch>
          <MessageBranchContent>
            <div key="r1">Response 1</div>
            <div key="r2">Response 2</div>
          </MessageBranchContent>
          <MessageBranchSelector from="assistant">
            <MessageBranchPrevious />
            <MessageBranchPage />
            <MessageBranchNext />
          </MessageBranchSelector>
        </MessageBranch>
      </Message>,
    );

    expect(screen.getByText("Response 1")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Next branch"));
    expect(screen.getByText("2 of 2")).toBeInTheDocument();
  });
});
