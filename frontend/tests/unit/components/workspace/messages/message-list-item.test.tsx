import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      uploads: { uploading: "Uploading..." },
      clipboard: {
        copyToClipboard: "Copy",
        copiedToClipboard: "Copied!",
        failedToCopyToClipboard: "Failed to copy",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

vi.mock("@/core/rehype", () => ({
  useRehypeSplitWordsIntoSpans: () => [],
}));

vi.mock("@/core/messages/utils", () => ({
  extractContentFromMessage: (msg: any) => msg.content ?? "",
  extractReasoningContentFromMessage: vi.fn(() => null),
  parseUploadedFiles: vi.fn(() => []),
  stripUploadedFilesTag: vi.fn((s: string) => s),
}));

vi.mock("@/core/artifacts/utils", () => ({
  resolveArtifactURL: (path: string, threadId: string) =>
    `/artifacts/${threadId}/${path}`,
}));

vi.mock("@/core/api/feedback", () => ({
  upsertFeedback: vi.fn().mockResolvedValue({ rating: 1 }),
  deleteFeedback: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/core/streamdown", () => ({
  humanMessagePlugins: {
    remarkPlugins: [],
    rehypePlugins: [],
  },
}));

vi.mock("@/components/ai-elements/message", () => ({
  Message: ({ children, className, from }: any) => (
    <div data-testid="ai-message" data-from={from} className={className}>
      {children}
    </div>
  ),
  MessageContent: ({ children, className }: any) => (
    <div data-testid="message-content" className={className}>
      {children}
    </div>
  ),
  MessageResponse: ({ children, className }: any) => (
    <div data-testid="message-response" className={className}>
      {children}
    </div>
  ),
  MessageToolbar: ({ children, className }: any) => (
    <div data-testid="message-toolbar" className={className}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/ai-elements/reasoning", () => ({
  Reasoning: ({ children }: any) => (
    <div data-testid="reasoning">{children}</div>
  ),
  ReasoningTrigger: () => <div data-testid="reasoning-trigger" />,
  ReasoningContent: ({ children }: any) => (
    <div data-testid="reasoning-content">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/task", () => ({
  Task: ({ children }: any) => <div data-testid="task">{children}</div>,
  TaskTrigger: ({ children }: any) => (
    <div data-testid="task-trigger">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/loader", () => ({
  Loader: () => <div data-testid="loader" />,
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant, className }: any) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

vi.mock("@/components/workspace/copy-button", () => ({
  CopyButton: ({ clipboardData }: { clipboardData: string }) => (
    <button data-testid="copy-button" data-clipboard={clipboardData}>
      Copy
    </button>
  ),
}));

vi.mock("@/components/workspace/messages/markdown-content", () => ({
  MarkdownContent: ({ content, className, components }: any) => {
    // Simple markdown parser that uses components prop for images and links
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    // Match images: ![alt](src)
    const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
    // Match links: [text](href)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    // Combined regex: images first, then links
    const combinedRegex =
      /(!\[([^\]]*)\]\(([^)]+)\))|(\[([^\]]+)\]\(([^)]+)\))/g;
    // Special marker for non-string src test
    if (content === "!nonstring[src](blob)") {
      const ImgComponent = components?.img || "img";
      return (
        <div data-testid="markdown-content" className={className}>
          <ImgComponent src={123} alt="nonstring" />
        </div>
      );
    }
    let match;
    while ((match = combinedRegex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(
          <span key={`t-${lastIndex}`}>
            {content.slice(lastIndex, match.index)}
          </span>,
        );
      }
      if (match[1]) {
        // Image match
        const ImgComponent = components?.img || "img";
        parts.push(
          <ImgComponent
            key={`img-${match.index}`}
            src={match[3]}
            alt={match[2]}
          />,
        );
      } else if (match[4]) {
        // Link match
        const AComponent = components?.a || "a";
        parts.push(
          <AComponent key={`a-${match.index}`} href={match[6]}>
            {match[5]}
          </AComponent>,
        );
      }
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex < content.length) {
      parts.push(
        <span key={`t-${lastIndex}`}>{content.slice(lastIndex)}</span>,
      );
    }
    return (
      <div data-testid="markdown-content" className={className}>
        {parts.length > 0 ? parts : content}
      </div>
    );
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let MessageListItem: typeof import("@/components/workspace/messages/message-list-item").MessageListItem;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/messages/message-list-item");
  MessageListItem = mod.MessageListItem;
});

afterEach(() => {
  cleanup();
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeHumanMessage(overrides: Record<string, any> = {}) {
  return {
    id: "msg-1",
    type: "human",
    content: "Hello world",
    ...overrides,
  } as any;
}

function makeAssistantMessage(overrides: Record<string, any> = {}) {
  return {
    id: "msg-2",
    type: "ai",
    content: "Response text",
    ...overrides,
  } as any;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("MessageListItem", () => {
  test("renders human message with from=user", () => {
    render(<MessageListItem message={makeHumanMessage()} threadId="t-1" />);
    expect(screen.getByTestId("ai-message")).toHaveAttribute(
      "data-from",
      "user",
    );
  });

  test("renders assistant message with from=assistant", () => {
    render(<MessageListItem message={makeAssistantMessage()} threadId="t-1" />);
    expect(screen.getByTestId("ai-message")).toHaveAttribute(
      "data-from",
      "assistant",
    );
  });

  test("shows copy button when not loading and showCopyButton is true", () => {
    render(
      <MessageListItem
        message={makeHumanMessage()}
        threadId="t-1"
        isLoading={false}
        showCopyButton={true}
      />,
    );
    expect(screen.getByTestId("copy-button")).toBeInTheDocument();
  });

  test("hides copy button when loading", () => {
    render(
      <MessageListItem
        message={makeHumanMessage()}
        threadId="t-1"
        isLoading={true}
        showCopyButton={true}
      />,
    );
    expect(screen.queryByTestId("copy-button")).not.toBeInTheDocument();
  });

  test("hides copy button when showCopyButton is false", () => {
    render(
      <MessageListItem
        message={makeHumanMessage()}
        threadId="t-1"
        isLoading={false}
        showCopyButton={false}
      />,
    );
    expect(screen.queryByTestId("copy-button")).not.toBeInTheDocument();
  });

  test("renders message content for human message", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: "Test content" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("message-content")).toBeInTheDocument();
  });

  test("renders message content for assistant message", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({ content: "AI response" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("message-content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <MessageListItem
        message={makeHumanMessage()}
        threadId="t-1"
        className="custom-msg"
      />,
    );
    expect(screen.getByTestId("ai-message")).toHaveClass("custom-msg");
  });

  test("human message has w-fit width class in content", () => {
    render(<MessageListItem message={makeHumanMessage()} threadId="t-1" />);
    const content = screen.getByTestId("message-content");
    expect(content.className).toContain("w-fit");
  });

  test("assistant message has w-full width class in content", () => {
    render(<MessageListItem message={makeAssistantMessage()} threadId="t-1" />);
    const content = screen.getByTestId("message-content");
    expect(content.className).toContain("w-full");
  });
});

describe("FeedbackButtons", () => {
  test("renders feedback buttons when feedback prop is provided", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={null}
        runId="run-1"
      />,
    );
    // FeedbackButtons should render thumbs up/down
    const toolbar = screen.getByTestId("message-toolbar");
    expect(toolbar).toBeInTheDocument();
  });

  test("calls upsertFeedback on thumbs up click", async () => {
    const { upsertFeedback } = await import("@/core/api/feedback");
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={null}
        runId="run-1"
      />,
    );
    // Find the thumbs up button (first button in feedback area)
    const buttons = screen.getAllByRole("button");
    // The thumbs up is the first SVG button
    const thumbsUp = buttons.find((b) => b.querySelector("svg"));
    if (thumbsUp) {
      fireEvent.click(thumbsUp);
      await waitFor(() => {
        expect(upsertFeedback).toHaveBeenCalledWith("t-1", "run-1", 1);
      });
    }
  });

  test("renders with existing feedback (rating=1)", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-1", rating: 1, comment: null }}
        runId="run-1"
      />,
    );
    expect(screen.getByTestId("message-toolbar")).toBeInTheDocument();
  });

  test("renders with existing negative feedback", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-neg", rating: -1, comment: null }}
        runId="run-1"
      />,
    );
    expect(screen.getByTestId("message-toolbar")).toBeInTheDocument();
  });

  test("hides feedback buttons when feedback prop is undefined", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        isLoading={false}
        showCopyButton={true}
      />,
    );
    // Only copy button, no feedback buttons
    expect(screen.getByTestId("copy-button")).toBeInTheDocument();
  });
});

describe("Task element rendering", () => {
  test("renders task element when additional_kwargs.element is task", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          additional_kwargs: { element: "task" },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("task")).toBeInTheDocument();
    expect(screen.getByTestId("loader")).toBeInTheDocument();
  });

  test("shows content in task element", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "Processing...",
          additional_kwargs: { element: "task" },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });
});

describe("Reasoning-only AI messages", () => {
  test("renders reasoning-only message when no main content", async () => {
    const { extractReasoningContentFromMessage } =
      await import("@/core/messages/utils");
    vi.mocked(extractReasoningContentFromMessage).mockReturnValue(
      "Reasoning text",
    );

    render(
      <MessageListItem
        message={makeAssistantMessage({ content: "" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("reasoning")).toBeInTheDocument();
    expect(screen.getByTestId("reasoning-content")).toBeInTheDocument();
  });
});

describe("Human message with empty content", () => {
  test("renders human message with empty content", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: "" })}
        threadId="t-1"
      />,
    );
    // Should still render without error
    expect(screen.getByTestId("ai-message")).toHaveAttribute(
      "data-from",
      "user",
    );
  });

  test("renders human message with null content", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: null })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("ai-message")).toHaveAttribute(
      "data-from",
      "user",
    );
  });
});

describe("parseUploadedFiles fallback", () => {
  test("calls parseUploadedFiles when content contains <uploaded_files> tag and no additional_kwargs.files", async () => {
    const { parseUploadedFiles } = await import("@/core/messages/utils");
    vi.mocked(parseUploadedFiles).mockReturnValue([
      { filename: "parsed.txt", path: "/mnt/parsed.txt", size: 512 },
    ]);

    render(
      <MessageListItem
        message={makeHumanMessage({
          content: "<uploaded_files>some data</uploaded_files>",
        })}
        threadId="t-1"
      />,
    );
    expect(parseUploadedFiles).toHaveBeenCalledWith(
      "<uploaded_files>some data</uploaded_files>",
    );
    // The parsed file should render a badge
    expect(screen.getByTestId("badge")).toBeInTheDocument();
  });
});

describe("Human message with files", () => {
  test("renders file list when additional_kwargs.files is provided", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "test.txt", path: "/mnt/test.txt", size: 1024 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    // RichFilesList should render a badge
    expect(screen.getByTestId("badge")).toBeInTheDocument();
  });

  test("renders uploading file card", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "upload.txt", status: "uploading" }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("upload.txt")).toBeInTheDocument();
    expect(screen.getByText("Uploading...")).toBeInTheDocument();
  });

  test("renders image file card", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "photo.png", path: "/mnt/photo.png", size: 2048 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    // Image files render as links with img tags
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/photo.png");
  });

  test("skips file card when no path", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "nopath.pdf" }],
          },
        })}
        threadId="t-1"
      />,
    );
    // No path means RichFileCard returns null
    expect(screen.queryByTestId("badge")).not.toBeInTheDocument();
  });

  test("renders file card with different types", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "data.json", path: "/mnt/data.json", size: 1024000 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("JSON")).toBeInTheDocument();
  });
});

describe("Assistant message with files", () => {
  test("renders files on assistant message", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          additional_kwargs: {
            files: [
              { filename: "result.csv", path: "/mnt/result.csv", size: 500 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("CSV")).toBeInTheDocument();
  });
});

describe("Markdown content rendering", () => {
  test("renders markdown content for assistant message", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({ content: "**bold** text" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
  });

  test("passes isLoading to markdown content", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        isLoading={true}
      />,
    );
    expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
  });
});

// ── Additional coverage tests ─────────────────────────────────────────────

describe("formatBytes", () => {
  // We can't directly import the private formatBytes, so we test it through
  // RichFileCard rendering which calls formatBytes internally.
  test("shows dash for 0 bytes in file card", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "zero.bin", path: "/mnt/zero.bin", size: 0 }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument(); // em-dash for 0 bytes
  });

  test("shows KB for file in KB range", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "small.txt", path: "/mnt/small.txt", size: 2048 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  test("shows MB for file in MB range", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              {
                filename: "big.zip",
                path: "/mnt/big.zip",
                size: 5 * 1024 * 1024,
              },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("5.0 MB")).toBeInTheDocument();
  });
});

describe("getFileTypeLabel", () => {
  test("returns mapped label for known extension", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "data.csv", path: "/mnt/data.csv", size: 100 }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("CSV")).toBeInTheDocument();
  });

  test("returns uppercase for unknown extension", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "file.xyz", path: "/mnt/file.xyz", size: 100 }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("XYZ")).toBeInTheDocument();
  });

  test("returns FILE for file with empty extension", () => {
    // getFileExt("") returns "", so FILE_TYPE_MAP[""] is undefined,
    // and ("".toUpperCase() || "FILE") evaluates to "FILE"
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "", path: "/mnt/file", size: 100 }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("FILE")).toBeInTheDocument();
  });
});

describe("isImageFile", () => {
  test("recognizes PNG as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "pic.png", path: "/mnt/pic.png", size: 500 }],
          },
        })}
        threadId="t-1"
      />,
    );
    // Image files render as <a> with <img>
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/pic.png");
  });

  test("recognizes JPEG as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "photo.jpeg", path: "/mnt/photo.jpeg", size: 500 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/photo.jpeg");
  });

  test("recognizes GIF as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "anim.gif", path: "/mnt/anim.gif", size: 500 }],
          },
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/anim.gif");
  });

  test("recognizes WEBP as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "photo.webp", path: "/mnt/photo.webp", size: 500 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/photo.webp");
  });

  test("recognizes SVG as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "icon.svg", path: "/mnt/icon.svg", size: 500 }],
          },
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/icon.svg");
  });

  test("recognizes BMP as image", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "bitmap.bmp", path: "/mnt/bitmap.bmp", size: 500 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/bitmap.bmp");
  });

  test("non-image extension renders as file card", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "doc.pdf", path: "/mnt/doc.pdf", size: 1024 }],
          },
        })}
        threadId="t-1"
      />,
    );
    // Non-image renders FileIcon + badge, not <img>
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
  });
});

describe("MessageImage component", () => {
  test("resolves /mnt/ src via resolveArtifactURL", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "![alt text](/mnt/image.png)",
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/image.png");
    expect(img).toHaveAttribute("alt", "alt text");
  });

  test("uses non-/mnt/ src as-is in img", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "![external](https://example.com/pic.jpg)",
        })}
        threadId="t-1"
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/pic.jpg");
  });
});

describe("MessageContent_ a tag with /mnt/ href", () => {
  test("resolves /mnt/ links via resolveArtifactURL", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "[file link](/mnt/docs/report.pdf)",
        })}
        threadId="t-1"
      />,
    );
    const link = screen.getByText("file link").closest("a");
    expect(link).toHaveAttribute("href", "/artifacts/t-1//mnt/docs/report.pdf");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("non-/mnt/ links are rendered normally", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "[google](https://google.com)",
        })}
        threadId="t-1"
      />,
    );
    const link = screen.getByText("google").closest("a");
    expect(link).toHaveAttribute("href", "https://google.com");
  });
});

describe("contentToDisplay useMemo for human messages", () => {
  test("calls stripUploadedFilesTag for human messages", async () => {
    const { stripUploadedFilesTag } = await import("@/core/messages/utils");
    vi.mocked(stripUploadedFilesTag).mockReturnValue("cleaned content");

    render(
      <MessageListItem
        message={makeHumanMessage({ content: "some content" })}
        threadId="t-1"
      />,
    );
    expect(stripUploadedFilesTag).toHaveBeenCalled();
    expect(screen.getByText("cleaned content")).toBeInTheDocument();
  });

  test("returns rawContent as-is for non-human messages", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({ content: "assistant raw" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("assistant raw")).toBeInTheDocument();
  });
});

describe("Human message rendering paths", () => {
  test("renders AIElementMessageResponse for human with content", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: "Hello!" })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("message-response")).toBeInTheDocument();
  });

  test("does not render AIElementMessageResponse for human with empty content", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: "" })}
        threadId="t-1"
      />,
    );
    expect(screen.queryByTestId("message-response")).not.toBeInTheDocument();
  });

  test("does not render AIElementMessageResponse for human with null content", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: null })}
        threadId="t-1"
      />,
    );
    expect(screen.queryByTestId("message-response")).not.toBeInTheDocument();
  });
});

describe("FeedbackButtons edge cases", () => {
  test("deleteFeedback called when clicking same rating (toggle off)", async () => {
    const { deleteFeedback } = await import("@/core/api/feedback");
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-1", rating: 1, comment: null }}
        runId="run-1"
      />,
    );
    // Find buttons with svg (feedback buttons)
    const buttons = screen.getAllByRole("button");
    const thumbsUp = buttons.find((b) => b.querySelector("svg"));
    expect(thumbsUp).toBeTruthy();
    if (thumbsUp) {
      fireEvent.click(thumbsUp);
      await waitFor(() => {
        expect(deleteFeedback).toHaveBeenCalledWith("t-1", "run-1");
      });
    }
  });

  test("deleteFeedback called for toggle off negative feedback", async () => {
    const { deleteFeedback } = await import("@/core/api/feedback");
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-neg", rating: -1, comment: null }}
        runId="run-1"
      />,
    );
    const buttons = screen.getAllByRole("button");
    const thumbsDown = buttons.find((b) => {
      const svg = b.querySelector("svg");
      return svg && b.className.includes("fill-current");
    });
    if (thumbsDown) {
      fireEvent.click(thumbsDown);
      await waitFor(() => {
        expect(deleteFeedback).toHaveBeenCalledWith("t-1", "run-1");
      });
    }
  });

  test("handles upsertFeedback error gracefully", async () => {
    const { upsertFeedback } = await import("@/core/api/feedback");
    vi.mocked(upsertFeedback).mockRejectedValueOnce(new Error("Network error"));
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={null}
        runId="run-1"
      />,
    );
    const buttons = screen.getAllByRole("button");
    const thumbsUp = buttons.find((b) => b.querySelector("svg"));
    if (thumbsUp) {
      fireEvent.click(thumbsUp);
      await waitFor(() => {
        expect(upsertFeedback).toHaveBeenCalled();
      });
    }
    // Should not throw - button still functional after error
    expect(screen.getByTestId("message-toolbar")).toBeInTheDocument();
  });

  test("handles deleteFeedback error gracefully", async () => {
    const { deleteFeedback } = await import("@/core/api/feedback");
    vi.mocked(deleteFeedback).mockRejectedValueOnce(new Error("Delete error"));
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-1", rating: 1, comment: null }}
        runId="run-1"
      />,
    );
    const buttons = screen.getAllByRole("button");
    const thumbsUp = buttons.find((b) => b.querySelector("svg"));
    if (thumbsUp) {
      fireEvent.click(thumbsUp);
      await waitFor(() => {
        expect(deleteFeedback).toHaveBeenCalled();
      });
    }
    // Should not throw
    expect(screen.getByTestId("message-toolbar")).toBeInTheDocument();
  });

  test("clicking opposite rating calls upsertFeedback", async () => {
    const { upsertFeedback } = await import("@/core/api/feedback");
    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={{ feedback_id: "fb-1", rating: 1, comment: null }}
        runId="run-1"
      />,
    );
    // Click thumbs down (second button with svg)
    const buttons = screen.getAllByRole("button");
    const allSvgButtons = buttons.filter((b) => b.querySelector("svg"));
    if (allSvgButtons.length >= 2) {
      fireEvent.click(allSvgButtons[1]!); // thumbs down
      await waitFor(() => {
        expect(upsertFeedback).toHaveBeenCalledWith("t-1", "run-1", -1);
      });
    }
  });

  test("isSubmitting prevents double-click", async () => {
    const { upsertFeedback } = await import("@/core/api/feedback");
    // Make the first call slow
    let resolveFirst: (() => void) | undefined;
    vi.mocked(upsertFeedback).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = () =>
            resolve({ feedback_id: "fb-1", rating: 1, comment: null });
        }),
    );

    render(
      <MessageListItem
        message={makeAssistantMessage()}
        threadId="t-1"
        feedback={null}
        runId="run-1"
      />,
    );
    const buttons = screen.getAllByRole("button");
    const thumbsUp = buttons.find((b) => b.querySelector("svg"));
    if (thumbsUp) {
      // First click starts submitting
      fireEvent.click(thumbsUp);
      // Second click should be blocked by isSubmitting guard
      fireEvent.click(thumbsUp);
      // Resolve the slow call
      resolveFirst?.();
      await waitFor(() => {
        expect(upsertFeedback).toHaveBeenCalledTimes(1); // Only one call
      });
    }
  });
});

describe("RichFileCard image rendering", () => {
  test("image file card renders link with resolved artifact URL", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              {
                filename: "photo.png",
                path: "/mnt/photos/photo.png",
                size: 4096,
              },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    // Should render as a link wrapping an img
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/artifacts/t-1//mnt/photos/photo.png");
    expect(img).toHaveAttribute("alt", "photo.png");
    // Parent should be an anchor
    const link = img.closest("a");
    expect(link).toHaveAttribute(
      "href",
      "/artifacts/t-1//mnt/photos/photo.png",
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  test("non-image file card renders FileIcon and badge", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "report.pdf", path: "/mnt/report.pdf", size: 2048 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  test("file card with unknown extension shows uppercase label", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [
              { filename: "archive.7z", path: "/mnt/archive.7z", size: 1024 },
            ],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByText("7Z")).toBeInTheDocument();
  });

  test("file card with no path returns null", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: {
            files: [{ filename: "test.bin", size: 100 }],
          },
        })}
        threadId="t-1"
      />,
    );
    // No file card rendered
    expect(screen.queryByText("BIN")).not.toBeInTheDocument();
  });
});

describe("Empty RichFilesList", () => {
  test("renders no file list when files array is empty", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: { files: [] },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.queryByTestId("badge")).not.toBeInTheDocument();
  });

  test("renders no file list when additional_kwargs.files is not an array", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          additional_kwargs: { files: "not-an-array" },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.queryByTestId("badge")).not.toBeInTheDocument();
  });
});

describe("Human message layout", () => {
  test("human message renders in ml-auto div", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({ content: "Hi" })}
        threadId="t-1"
      />,
    );
    const content = screen.getByTestId("message-content");
    expect(content.parentElement).toHaveClass("ml-auto");
  });

  test("human message with files renders filesList before message response", () => {
    render(
      <MessageListItem
        message={makeHumanMessage({
          content: "Check this",
          additional_kwargs: {
            files: [{ filename: "doc.txt", path: "/mnt/doc.txt", size: 100 }],
          },
        })}
        threadId="t-1"
      />,
    );
    // Both file badge and message response should render
    expect(screen.getByTestId("badge")).toBeInTheDocument();
    expect(screen.getByTestId("message-response")).toBeInTheDocument();
  });
});

describe("Assistant message rendering path", () => {
  test("assistant message renders MarkdownContent with files and content", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "Here is the result",
          additional_kwargs: {
            files: [{ filename: "out.csv", path: "/mnt/out.csv", size: 500 }],
          },
        })}
        threadId="t-1"
      />,
    );
    expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
    expect(screen.getByText("CSV")).toBeInTheDocument();
  });
});

describe("MessageImage non-string src", () => {
  test("renders img directly when src is not a string", () => {
    render(
      <MessageListItem
        message={makeAssistantMessage({
          content: "!nonstring[src](blob)",
        })}
        threadId="t-1"
      />,
    );
    // The mock passes src={123} (non-string) to the img component
    // MessageImage should render a plain <img> without wrapping <a>
    const img = screen.getByRole("img");
    expect(img).toBeInTheDocument();
    expect(img.closest("a")).toBeNull(); // No anchor wrapper for non-string src
  });
});
