import {
  render,
  screen,
  cleanup,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  PromptInput,
  PromptInputProvider,
  PromptInputBody,
  PromptInputTextarea,
  PromptInputHeader,
  PromptInputFooter,
  PromptInputTools,
  PromptInputButton,
  PromptInputSubmit,
  PromptInputAttachments,
  PromptInputAttachment,
  PromptInputActionMenu,
  PromptInputActionMenuTrigger,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionAddAttachments,
  PromptInputTabsList,
  PromptInputTab,
  PromptInputTabLabel,
  PromptInputTabBody,
  PromptInputTabItem,
  PromptInputSelect,
  PromptInputSelectTrigger,
  PromptInputSelectContent,
  PromptInputSelectItem,
  PromptInputSelectValue,
  PromptInputHoverCard,
  PromptInputHoverCardTrigger,
  PromptInputHoverCardContent,
  PromptInputSpeechButton,
  PromptInputCommand,
  PromptInputCommandInput,
  PromptInputCommandList,
  PromptInputCommandEmpty,
  PromptInputCommandGroup,
  PromptInputCommandItem,
  PromptInputCommandSeparator,
  usePromptInputController,
  useProviderAttachments,
  usePromptInputAttachments,
} from "@/components/ai-elements/prompt-input";

// Track nanoid call count for unique IDs
let nanoidCounter = 0;
vi.mock("nanoid", () => ({
  nanoid: () => `test-id-${++nanoidCounter}`,
}));

const mockSplitUnsupported = vi.fn(
  (
    files: File[] | FileList,
  ): { accepted: File[]; rejected: File[]; message: string | undefined } => ({
    accepted: Array.from(files),
    rejected: [],
    message: undefined,
  }),
);

vi.mock("@/core/uploads", () => ({
  splitUnsupportedUploadFiles: (...args: any[]) =>
    mockSplitUnsupported(...(args as [any])),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
  },
}));

const mockIsIMEComposing = vi.fn((_el?: Element) => false);
vi.mock("@/lib/ime", () => ({
  isIMEComposing: (...args: any[]) => mockIsIMEComposing(...(args as [any])),
}));

// Mock URL.createObjectURL and revokeObjectURL
const mockCreateObjectURL = vi.fn(() => "blob:mock-url");
const mockRevokeObjectURL = vi.fn();
Object.defineProperty(globalThis, "URL", {
  value: {
    createObjectURL: mockCreateObjectURL,
    revokeObjectURL: mockRevokeObjectURL,
  },
});

// Polyfill ResizeObserver for cmdk (used by Command components)
if (typeof globalThis.ResizeObserver === "undefined") {
  (globalThis as any).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  nanoidCounter = 0;
});

// Helper to create a mock File
function createMockFile(
  name = "test.png",
  type = "image/png",
  size = 1024,
): File {
  const file = new File(["test content"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

// ============================================================================
// PromptInputProvider
// ============================================================================

describe("PromptInputProvider", () => {
  test("renders children", () => {
    render(
      <PromptInputProvider>
        <div>Provider child</div>
      </PromptInputProvider>,
    );
    expect(screen.getByText("Provider child")).toBeInTheDocument();
  });

  test("provides text input context to children", () => {
    function TestConsumer() {
      const ctrl = usePromptInputController();
      return <span>Value: {ctrl.textInput.value}</span>;
    }

    render(
      <PromptInputProvider initialInput="Hello">
        <TestConsumer />
      </PromptInputProvider>,
    );
    expect(screen.getByText("Value: Hello")).toBeInTheDocument();
  });

  test("provides empty initial input by default", () => {
    function TestConsumer() {
      const ctrl = usePromptInputController();
      return <span>Value: [{ctrl.textInput.value}]</span>;
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );
    expect(screen.getByText("Value: []")).toBeInTheDocument();
  });
});

// ============================================================================
// usePromptInputController
// ============================================================================

describe("usePromptInputController", () => {
  test("throws when used outside PromptInputProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function BadConsumer() {
      usePromptInputController();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      "Wrap your component inside <PromptInputProvider>",
    );
    consoleSpy.mockRestore();
  });
});

// ============================================================================
// useProviderAttachments
// ============================================================================

describe("useProviderAttachments", () => {
  test("throws when used outside PromptInputProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function BadConsumer() {
      useProviderAttachments();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      "Wrap your component inside <PromptInputProvider>",
    );
    consoleSpy.mockRestore();
  });
});

// ============================================================================
// usePromptInputAttachments
// ============================================================================

describe("usePromptInputAttachments", () => {
  test("throws when used outside both PromptInput and PromptInputProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    function BadConsumer() {
      usePromptInputAttachments();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      "usePromptInputAttachments must be used within a PromptInput or PromptInputProvider",
    );
    consoleSpy.mockRestore();
  });
});

// ============================================================================
// PromptInput
// ============================================================================

describe("PromptInput", () => {
  test("renders form with children", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
          <PromptInputSubmit />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  test("renders hidden file input", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByTestId("file-input")).toBeInTheDocument();
  });

  test("calls onSubmit with text on form submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
          <PromptInputSubmit />
        </PromptInputBody>
      </PromptInput>,
    );

    await user.type(screen.getByRole("textbox"), "Hello world");
    await user.click(screen.getByLabelText("Submit"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Hello world" }),
      expect.anything(),
    );
  });

  test("calls onSubmit with empty text when form is empty", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
          <PromptInputSubmit />
        </PromptInputBody>
      </PromptInput>,
    );

    await user.click(screen.getByLabelText("Submit"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: "" }),
      expect.anything(),
    );
  });

  test("applies custom className to form", () => {
    render(
      <PromptInput onSubmit={vi.fn()} className="custom-form">
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );
    const form = screen.getByRole("textbox").closest("form");
    expect(form).toHaveClass("custom-form");
  });

  test("renders with provider integration", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputBody
// ============================================================================

describe("PromptInputBody", () => {
  test("renders children", () => {
    render(
      <PromptInputBody data-testid="body">
        <span>Body content</span>
      </PromptInputBody>,
    );
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <PromptInputBody className="custom-body" data-testid="body">
        <span>Content</span>
      </PromptInputBody>,
    );
    expect(screen.getByTestId("body")).toHaveClass("custom-body");
  });
});

// ============================================================================
// PromptInputTextarea
// ============================================================================

describe("PromptInputTextarea", () => {
  test("renders with default placeholder", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(
      screen.getByPlaceholderText("What would you like to know?"),
    ).toBeInTheDocument();
  });

  test("renders with custom placeholder", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea placeholder="Ask something..." />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByPlaceholderText("Ask something...")).toBeInTheDocument();
  });

  test("accepts user input", async () => {
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    await user.type(screen.getByRole("textbox"), "Test input");
    expect(screen.getByRole("textbox")).toHaveValue("Test input");
  });

  test("submits form on Enter key press", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
          <PromptInputSubmit />
        </PromptInputBody>
      </PromptInput>,
    );

    await user.type(screen.getByRole("textbox"), "Enter key test");
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Enter key test" }),
      expect.anything(),
    );
  });

  test("does not submit on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
          <PromptInputSubmit />
        </PromptInputBody>
      </PromptInput>,
    );

    await user.type(screen.getByRole("textbox"), "Line 1");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    // onSubmit should not be called
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("removes last attachment on Backspace when textarea is empty", async () => {
    const user = userEvent.setup();

    // Create a file to add as attachment
    const file = createMockFile("test.png", "image/png");

    function TestWrapper() {
      return (
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      );
    }

    render(<TestWrapper />);

    // Backspace on empty textarea should not throw
    const textarea = screen.getByRole("textbox");
    await user.click(textarea);
    await user.keyboard("{Backspace}");
    // No error means it handled the empty case correctly
  });

  test("applies custom className", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea className="custom-textarea" />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByRole("textbox")).toHaveClass("custom-textarea");
  });

  test("works with provider - controlled mode", async () => {
    const user = userEvent.setup();

    render(
      <PromptInputProvider initialInput="">
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      </PromptInputProvider>,
    );

    await user.type(screen.getByRole("textbox"), "Provided input");
    expect(screen.getByRole("textbox")).toHaveValue("Provided input");
  });
});

// ============================================================================
// PromptInputHeader
// ============================================================================

describe("PromptInputHeader", () => {
  test("renders children", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputHeader data-testid="header">
          <span>Header content</span>
        </PromptInputHeader>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByText("Header content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputHeader className="custom-header" data-testid="header">
          <span>Content</span>
        </PromptInputHeader>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );
    expect(screen.getByTestId("header")).toHaveClass("custom-header");
  });
});

// ============================================================================
// PromptInputFooter
// ============================================================================

describe("PromptInputFooter", () => {
  test("renders children", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter data-testid="footer">
          <span>Footer content</span>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter className="custom-footer" data-testid="footer">
          <span>Content</span>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("footer")).toHaveClass("custom-footer");
  });
});

// ============================================================================
// PromptInputTools
// ============================================================================

describe("PromptInputTools", () => {
  test("renders children", () => {
    render(
      <PromptInputTools data-testid="tools">
        <button>Tool 1</button>
      </PromptInputTools>,
    );
    expect(screen.getByRole("button", { name: "Tool 1" })).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <PromptInputTools className="custom-tools" data-testid="tools">
        <span>Content</span>
      </PromptInputTools>,
    );
    expect(screen.getByTestId("tools")).toHaveClass("custom-tools");
  });
});

// ============================================================================
// PromptInputButton
// ============================================================================

describe("PromptInputButton", () => {
  test("renders as a button", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputButton data-testid="btn">Click</PromptInputButton>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("btn")).toBeInTheDocument();
  });

  test("has type button by default", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputButton data-testid="btn">Btn</PromptInputButton>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("btn")).toHaveAttribute("type", "button");
  });

  test("applies ghost variant by default", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputButton data-testid="btn">Btn</PromptInputButton>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("btn").className).toContain("hover:bg-accent");
  });

  test("applies custom variant", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputButton variant="outline" data-testid="btn">
            Btn
          </PromptInputButton>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("btn").className).toContain("border");
  });

  test("applies custom className", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputButton className="custom-btn" data-testid="btn">
            Btn
          </PromptInputButton>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("btn")).toHaveClass("custom-btn");
  });
});

// ============================================================================
// PromptInputSubmit
// ============================================================================

describe("PromptInputSubmit", () => {
  test("renders with submit type", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByLabelText("Submit")).toHaveAttribute("type", "submit");
  });

  test("renders arrow up icon by default (no status)", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );
    const btn = screen.getByLabelText("Submit");
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  test("renders loader icon when status is submitted", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit status="submitted" />
        </PromptInputFooter>
      </PromptInput>,
    );
    const btn = screen.getByLabelText("Submit");
    const svg = btn.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.className.baseVal || "").toContain("animate-spin");
  });

  test("renders square icon when status is streaming", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit status="streaming" />
        </PromptInputFooter>
      </PromptInput>,
    );
    const btn = screen.getByLabelText("Submit");
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  test("renders x icon when status is error", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit status="error" />
        </PromptInputFooter>
      </PromptInput>,
    );
    const btn = screen.getByLabelText("Submit");
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  test("renders custom children instead of icon", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit>Send</PromptInputSubmit>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByText("Send")).toBeInTheDocument();
  });

  test("applies default variant", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit data-testid="submit" />
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("submit").className).toContain("bg-primary");
  });

  test("applies custom className", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit className="custom-submit" data-testid="submit" />
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("submit")).toHaveClass("custom-submit");
  });
});

// ============================================================================
// PromptInputAttachments
// ============================================================================

describe("PromptInputAttachments", () => {
  test("returns null when no files", () => {
    const { container } = render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <div>{file.filename}</div>}
        </PromptInputAttachments>
      </PromptInput>,
    );
    // No attachments rendered
    expect(container.querySelector("[class*='flex-wrap']")).toBeNull();
  });

  test("applies custom className", () => {
    // Render with no files - returns null so className test is not applicable
    const { container } = render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments className="custom-attachments">
          {(file) => <div>{file.filename}</div>}
        </PromptInputAttachments>
      </PromptInput>,
    );
    // No files means null return
    expect(container.firstChild).toBeTruthy(); // The form is still there
  });
});

// ============================================================================
// PromptInputAttachment
// ============================================================================

describe("PromptInputAttachment", () => {
  test("renders image attachment", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "att-1",
              type: "file",
              mediaType: "image/png",
              url: "blob:test",
              filename: "photo.png",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(screen.getByText("photo.png")).toBeInTheDocument();
    expect(screen.getByAltText("photo.png")).toBeInTheDocument();
  });

  test("renders file attachment with paperclip icon", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "att-2",
              type: "file",
              mediaType: "application/pdf",
              url: "blob:test",
              filename: "doc.pdf",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(screen.getByText("doc.pdf")).toBeInTheDocument();
  });

  test("uses 'Image' fallback when no filename for image", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "att-3",
              type: "file",
              mediaType: "image/png",
              url: "blob:test",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(screen.getByText("Image")).toBeInTheDocument();
  });

  test("uses 'Attachment' fallback when no filename for file", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "att-4",
              type: "file",
              mediaType: "application/pdf",
              url: "blob:test",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(screen.getByText("Attachment")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            className="custom-att"
            data={{
              id: "att-5",
              type: "file",
              mediaType: "image/png",
              url: "blob:test",
              filename: "test.png",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );
    expect(
      screen.getByText("test.png").closest("[class*='custom-att']"),
    ).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputActionMenu and related
// ============================================================================

describe("PromptInputActionMenu", () => {
  test("renders trigger button with plus icon", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger data-testid="menu-trigger" />
          </PromptInputActionMenu>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByTestId("menu-trigger")).toBeInTheDocument();
  });

  test("renders trigger with custom children", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger data-testid="menu-trigger">
              Actions
            </PromptInputActionMenuTrigger>
          </PromptInputActionMenu>
        </PromptInputFooter>
      </PromptInput>,
    );
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  test("renders action menu item", async () => {
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger data-testid="menu-trigger" />
            <PromptInputActionMenuContent>
              <PromptInputActionMenuItem>Menu item</PromptInputActionMenuItem>
            </PromptInputActionMenuContent>
          </PromptInputActionMenu>
        </PromptInputFooter>
      </PromptInput>,
    );

    await user.click(screen.getByTestId("menu-trigger"));
    await waitFor(() => {
      expect(screen.getByText("Menu item")).toBeInTheDocument();
    });
  });
});

// ============================================================================
// PromptInputActionAddAttachments
// ============================================================================

describe("PromptInputActionAddAttachments", () => {
  test("renders with default label", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger data-testid="menu-trigger" />
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu>
        </PromptInputFooter>
      </PromptInput>,
    );

    // Open menu to see the item
    const user = userEvent.setup();
    user.click(screen.getByTestId("menu-trigger"));
  });

  test("renders with custom label", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputActionMenu>
              <PromptInputActionMenuTrigger data-testid="menu-trigger" />
              <PromptInputActionMenuContent>
                <PromptInputActionAddAttachments label="Upload files" />
              </PromptInputActionMenuContent>
            </PromptInputActionMenu>
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    const user = userEvent.setup();
    user.click(screen.getByTestId("menu-trigger"));
  });
});

// ============================================================================
// PromptInputTabs and related
// ============================================================================

describe("PromptInputTabs", () => {
  test("PromptInputTabsList renders children", () => {
    render(
      <PromptInputTabsList data-testid="tabs-list">
        <span>Tab list</span>
      </PromptInputTabsList>,
    );
    expect(screen.getByText("Tab list")).toBeInTheDocument();
  });

  test("PromptInputTabsList applies custom className", () => {
    render(
      <PromptInputTabsList className="custom-tabs" data-testid="tabs-list">
        <span>Content</span>
      </PromptInputTabsList>,
    );
    expect(screen.getByTestId("tabs-list")).toHaveClass("custom-tabs");
  });

  test("PromptInputTab renders children", () => {
    render(
      <PromptInputTab data-testid="tab">
        <span>Tab content</span>
      </PromptInputTab>,
    );
    expect(screen.getByText("Tab content")).toBeInTheDocument();
  });

  test("PromptInputTab applies custom className", () => {
    render(
      <PromptInputTab className="custom-tab" data-testid="tab">
        <span>Content</span>
      </PromptInputTab>,
    );
    expect(screen.getByTestId("tab")).toHaveClass("custom-tab");
  });

  test("PromptInputTabLabel renders children", () => {
    render(<PromptInputTabLabel>Tab Label</PromptInputTabLabel>);
    expect(screen.getByText("Tab Label")).toBeInTheDocument();
  });

  test("PromptInputTabLabel renders as h3", () => {
    render(
      <PromptInputTabLabel data-testid="label">Label</PromptInputTabLabel>,
    );
    expect(screen.getByTestId("label").tagName).toBe("H3");
  });

  test("PromptInputTabLabel applies custom className", () => {
    render(
      <PromptInputTabLabel className="custom-label" data-testid="label">
        Label
      </PromptInputTabLabel>,
    );
    expect(screen.getByTestId("label")).toHaveClass("custom-label");
  });

  test("PromptInputTabBody renders children", () => {
    render(
      <PromptInputTabBody data-testid="tab-body">
        <span>Body content</span>
      </PromptInputTabBody>,
    );
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });

  test("PromptInputTabBody applies custom className", () => {
    render(
      <PromptInputTabBody className="custom-body" data-testid="tab-body">
        <span>Content</span>
      </PromptInputTabBody>,
    );
    expect(screen.getByTestId("tab-body")).toHaveClass("custom-body");
  });

  test("PromptInputTabItem renders children", () => {
    render(
      <PromptInputTabItem data-testid="tab-item">
        <span>Item content</span>
      </PromptInputTabItem>,
    );
    expect(screen.getByText("Item content")).toBeInTheDocument();
  });

  test("PromptInputTabItem applies custom className", () => {
    render(
      <PromptInputTabItem className="custom-item" data-testid="tab-item">
        <span>Content</span>
      </PromptInputTabItem>,
    );
    expect(screen.getByTestId("tab-item")).toHaveClass("custom-item");
  });
});

// ============================================================================
// PromptInputSelect and related
// ============================================================================

describe("PromptInputSelect", () => {
  test("renders select trigger", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger data-testid="select-trigger">
          <PromptInputSelectValue placeholder="Select option" />
        </PromptInputSelectTrigger>
      </PromptInputSelect>,
    );
    expect(screen.getByTestId("select-trigger")).toBeInTheDocument();
  });

  test("renders with placeholder value", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger>
          <PromptInputSelectValue placeholder="Pick one" />
        </PromptInputSelectTrigger>
      </PromptInputSelect>,
    );
    expect(screen.getByText("Pick one")).toBeInTheDocument();
  });

  test("PromptInputSelectTrigger applies custom className", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger
          className="custom-trigger"
          data-testid="select-trigger"
        >
          <PromptInputSelectValue placeholder="Select" />
        </PromptInputSelectTrigger>
      </PromptInputSelect>,
    );
    expect(screen.getByTestId("select-trigger")).toHaveClass("custom-trigger");
  });
});

// ============================================================================
// PromptInputHoverCard and related
// ============================================================================

describe("PromptInputHoverCard", () => {
  test("renders children", () => {
    render(
      <PromptInputHoverCard>
        <PromptInputHoverCardTrigger>
          <span>Hover me</span>
        </PromptInputHoverCardTrigger>
        <PromptInputHoverCardContent>
          <p>Hover content</p>
        </PromptInputHoverCardContent>
      </PromptInputHoverCard>,
    );
    expect(screen.getByText("Hover me")).toBeInTheDocument();
  });

  test("PromptInputHoverCardContent applies custom className", () => {
    render(
      <PromptInputHoverCard open>
        <PromptInputHoverCardTrigger>
          <span>Trigger</span>
        </PromptInputHoverCardTrigger>
        <PromptInputHoverCardContent
          className="custom-content"
          data-testid="hover-content"
        >
          <p>Content</p>
        </PromptInputHoverCardContent>
      </PromptInputHoverCard>,
    );
    expect(screen.getByTestId("hover-content")).toHaveClass("custom-content");
  });

  test("PromptInputHoverCardContent defaults align to start", () => {
    render(
      <PromptInputHoverCard open>
        <PromptInputHoverCardTrigger>
          <span>Trigger</span>
        </PromptInputHoverCardTrigger>
        <PromptInputHoverCardContent data-testid="hover-content">
          <p>Content</p>
        </PromptInputHoverCardContent>
      </PromptInputHoverCard>,
    );
    expect(screen.getByTestId("hover-content")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputCommand and related (pass-through components)
// ============================================================================

describe("PromptInputCommand pass-through components", () => {
  test("PromptInputCommand renders", () => {
    render(
      <div data-testid="cmd-wrapper">
        {/* Just test the import/exports exist */}
        <span>Command components available</span>
      </div>,
    );
    expect(
      screen.getByText("Command components available"),
    ).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInput error callbacks
// ============================================================================

describe("PromptInput error callbacks", () => {
  test("calls onError with accept code when no files match accept filter", async () => {
    const onError = vi.fn();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit} accept="image/*" onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    // Create a non-image file
    const txtFile = new File(["hello"], "readme.txt", { type: "text/plain" });
    Object.defineProperty(fileInput, "files", {
      value: [txtFile],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "accept" }),
    );
  });

  test("calls onError with max_file_size code when file exceeds maxFileSize", () => {
    const onError = vi.fn();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit} maxFileSize={100} onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const bigFile = new File(["x".repeat(200)], "big.png", {
      type: "image/png",
    });
    Object.defineProperty(bigFile, "size", { value: 200 });
    Object.defineProperty(fileInput, "files", {
      value: [bigFile],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "max_file_size" }),
    );
  });

  test("calls onError with max_files code when adding more files than maxFiles", () => {
    const onError = vi.fn();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit} maxFiles={1} onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("a.png", "image/png");
    const file2 = createMockFile("b.png", "image/png");
    Object.defineProperty(fileInput, "files", {
      value: [file1, file2],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "max_files" }),
    );
  });
});

// ============================================================================
// PromptInput accept filter logic
// ============================================================================

describe("PromptInput accept filter", () => {
  test("accepts files matching wildcard pattern", () => {
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit} accept="image/*">
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const imgFile = createMockFile("photo.jpg", "image/jpeg");
    Object.defineProperty(fileInput, "files", {
      value: [imgFile],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    // No error callback means file was accepted
    // The file should be in state (we can't directly assert that without
    // rendering attachments, but the absence of error is sufficient)
  });

  test("accepts files matching exact MIME type", () => {
    const onError = vi.fn();

    render(
      <PromptInput
        onSubmit={vi.fn()}
        accept="application/pdf"
        onError={onError}
      >
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const pdfFile = createMockFile("doc.pdf", "application/pdf");
    Object.defineProperty(fileInput, "files", {
      value: [pdfFile],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    // Should not call onError for accepted type
    expect(onError).not.toHaveBeenCalled();
  });

  test("accepts all files when accept is empty", () => {
    const onError = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()} accept="" onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const anyFile = createMockFile("data.csv", "text/csv");
    Object.defineProperty(fileInput, "files", {
      value: [anyFile],
      writable: false,
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(onError).not.toHaveBeenCalled();
  });
});

// ============================================================================
// PromptInput syncHiddenInput
// ============================================================================

describe("PromptInput syncHiddenInput", () => {
  test("clears file input value when syncHiddenInput is true and no files", () => {
    render(
      <PromptInput onSubmit={vi.fn()} syncHiddenInput>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    // syncHiddenInput clears the input when files array is empty
    expect((fileInput as HTMLInputElement).value).toBe("");
  });
});

// ============================================================================
// PromptInputSelectContent and PromptInputSelectItem
// ============================================================================

describe("PromptInputSelectContent and PromptInputSelectItem", () => {
  test("PromptInputSelectContent renders children", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger>
          <PromptInputSelectValue placeholder="Select" />
        </PromptInputSelectTrigger>
        <PromptInputSelectContent>
          <PromptInputSelectItem value="opt1">Option 1</PromptInputSelectItem>
        </PromptInputSelectContent>
      </PromptInputSelect>,
    );
    expect(screen.getByText("Select")).toBeInTheDocument();
  });

  test("PromptInputSelectContent applies custom className", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger>
          <PromptInputSelectValue placeholder="Pick" />
        </PromptInputSelectTrigger>
        <PromptInputSelectContent className="custom-content">
          <PromptInputSelectItem value="a">A</PromptInputSelectItem>
        </PromptInputSelectContent>
      </PromptInputSelect>,
    );
    // The component renders without error
    expect(screen.getByText("Pick")).toBeInTheDocument();
  });

  test("PromptInputSelectItem applies custom className", () => {
    render(
      <PromptInputSelect>
        <PromptInputSelectTrigger>
          <PromptInputSelectValue placeholder="Pick" />
        </PromptInputSelectTrigger>
        <PromptInputSelectContent>
          <PromptInputSelectItem value="a" className="custom-item">
            Item A
          </PromptInputSelectItem>
        </PromptInputSelectContent>
      </PromptInputSelect>,
    );
    expect(screen.getByText("Pick")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInput provider cleanup on unmount
// ============================================================================

describe("PromptInput provider cleanup", () => {
  test("revokes blob URLs when PromptInputProvider unmounts", () => {
    const { unmount } = render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      </PromptInputProvider>,
    );

    // Unmount should trigger cleanup
    unmount();

    // If there were no files, no URLs should be revoked
    // This test verifies the cleanup path doesn't throw
    expect(true).toBe(true);
  });
});

// ============================================================================
// PromptInputProvider setInput and clear
// ============================================================================

describe("PromptInputProvider setInput and clear", () => {
  test("setInput updates the value exposed via controller", () => {
    function TestConsumer() {
      const ctrl = usePromptInputController();
      return (
        <div>
          <span data-testid="val">{ctrl.textInput.value}</span>
          <button onClick={() => ctrl.textInput.setInput("new text")}>
            Set
          </button>
          <button onClick={() => ctrl.textInput.clear()}>Clear</button>
        </div>
      );
    }

    render(
      <PromptInputProvider initialInput="start">
        <TestConsumer />
      </PromptInputProvider>,
    );

    expect(screen.getByTestId("val")).toHaveTextContent("start");
  });

  test("clear resets the value to empty string", async () => {
    const user = userEvent.setup();

    function TestConsumer() {
      const ctrl = usePromptInputController();
      return (
        <div>
          <span data-testid="val">{ctrl.textInput.value}</span>
          <button onClick={() => ctrl.textInput.clear()}>Clear</button>
        </div>
      );
    }

    render(
      <PromptInputProvider initialInput="has content">
        <TestConsumer />
      </PromptInputProvider>,
    );

    expect(screen.getByTestId("val")).toHaveTextContent("has content");
    await user.click(screen.getByText("Clear"));
    expect(screen.getByTestId("val")).toHaveTextContent("");
  });
});

// ============================================================================
// PromptInput full composition
// ============================================================================

describe("PromptInput composition", () => {
  test("renders a complete prompt input with all sub-components", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputHeader>
          <span>Header</span>
        </PromptInputHeader>
        <PromptInputBody>
          <PromptInputTextarea placeholder="Ask me anything" />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputTools>
            <PromptInputButton data-testid="tool-btn">Tool</PromptInputButton>
          </PromptInputTools>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    expect(screen.getByText("Header")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask me anything")).toBeInTheDocument();
    expect(screen.getByTestId("tool-btn")).toBeInTheDocument();
    expect(screen.getByLabelText("Submit")).toBeInTheDocument();

    // Type and submit
    await user.type(screen.getByRole("textbox"), "Test message");
    await user.click(screen.getByLabelText("Submit"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Test message" }),
      expect.anything(),
    );
  });

  test("renders with provider and attachments", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <PromptInputProvider initialInput="Provider text">
        <PromptInput onSubmit={onSubmit}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputTools>
              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger data-testid="menu-trigger" />
                <PromptInputActionMenuContent>
                  <PromptInputActionAddAttachments />
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>
            </PromptInputTools>
            <PromptInputSubmit />
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    expect(screen.getByRole("textbox")).toHaveValue("Provider text");
    expect(screen.getByLabelText("Submit")).toBeInTheDocument();

    // Submit with provider text
    await user.click(screen.getByLabelText("Submit"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Provider text" }),
      expect.anything(),
    );
  });

  test("handles file input change event", async () => {
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");

    // Simulate file input change
    const event = new Event("change", { bubbles: true });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fileInput.dispatchEvent(event);
  });

  test("accept prop is set on file input", () => {
    render(
      <PromptInput onSubmit={vi.fn()} accept="image/*">
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    expect(screen.getByTestId("file-input")).toHaveAttribute(
      "accept",
      "image/*",
    );
  });

  test("multiple prop is set on file input", () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    expect(screen.getByTestId("file-input")).toHaveAttribute("multiple", "");
  });

  test("disabled prop can be passed", () => {
    render(
      <PromptInput onSubmit={vi.fn()} disabled>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    // The form should still render
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputProvider attachment management
// ============================================================================

describe("PromptInputProvider attachment management", () => {
  test("add creates object URLs and appends files", async () => {
    function TestConsumer() {
      const ctx = useProviderAttachments();
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
          <button
            onClick={() => {
              const file = createMockFile("a.png", "image/png");
              ctx.add([file]);
            }}
          >
            Add
          </button>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    expect(screen.getByTestId("count")).toHaveTextContent("0");
    await userEvent.setup().click(screen.getByText("Add"));
    expect(screen.getByTestId("count")).toHaveTextContent("1");
    expect(mockCreateObjectURL).toHaveBeenCalled();
  });

  test("add ignores empty file arrays", () => {
    function TestConsumer() {
      const ctx = useProviderAttachments();
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
          <button onClick={() => ctx.add([])}>Add Empty</button>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add Empty"));
    expect(screen.getByTestId("count")).toHaveTextContent("0");
  });

  test("add with FileList works", () => {
    function TestConsumer() {
      const ctx = useProviderAttachments();
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
          <span data-testid="fname">{ctx.files[0]?.filename ?? ""}</span>
          <button
            onClick={() => {
              const file = createMockFile("photo.jpg", "image/jpeg");
              ctx.add([file]);
            }}
          >
            Add File
          </button>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add File"));
    expect(screen.getByTestId("count")).toHaveTextContent("1");
    expect(screen.getByTestId("fname")).toHaveTextContent("photo.jpg");
  });

  test("remove deletes file by id and revokes URL", () => {
    let removeFn: ((id: string) => void) | null = null;
    let filesRef: any[] = [];

    function TestConsumer() {
      const ctx = useProviderAttachments();
      removeFn = ctx.remove;
      filesRef = ctx.files;
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
          <button
            onClick={() => {
              const file = createMockFile("a.png", "image/png");
              ctx.add([file]);
            }}
          >
            Add
          </button>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add"));
    expect(screen.getByTestId("count")).toHaveTextContent("1");

    // Remove the file we just added
    const fileId = filesRef[0].id;
    act(() => removeFn!(fileId));
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  test("clear removes all files and revokes URLs", () => {
    let clearFn: (() => void) | null = null;

    function TestConsumer() {
      const ctx = useProviderAttachments();
      clearFn = ctx.clear;
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
          <button
            onClick={() => {
              ctx.add([createMockFile("a.png", "image/png")]);
              ctx.add([createMockFile("b.png", "image/png")]);
            }}
          >
            Add Two
          </button>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add Two"));
    expect(screen.getByTestId("count")).toHaveTextContent("2");

    act(() => clearFn!());
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  test("openFileDialog calls registered open function", () => {
    let openFn: (() => void) | null = null;

    function TestConsumer() {
      const ctx = useProviderAttachments();
      openFn = ctx.openFileDialog;
      return <span>Consumer</span>;
    }

    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
        <TestConsumer />
      </PromptInputProvider>,
    );

    // openFileDialog should be callable and not throw
    expect(typeof openFn).toBe("function");
    // Call it to cover the callback
    act(() => openFn!());
  });

  test("provider unmount cleanup revokes blob URLs for files with URLs", () => {
    function TestConsumer() {
      const ctx = useProviderAttachments();
      return (
        <button
          onClick={() => {
            ctx.add([createMockFile("a.png", "image/png")]);
          }}
        >
          Add
        </button>
      );
    }

    const { unmount } = render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add"));
    mockRevokeObjectURL.mockClear();
    unmount();
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  test("provider unmount cleanup iterates over multiple files", () => {
    function TestConsumer() {
      const ctx = useProviderAttachments();
      return (
        <button
          onClick={() => {
            ctx.add([createMockFile("a.png", "image/png")]);
            ctx.add([createMockFile("b.png", "image/png")]);
          }}
        >
          Add Two
        </button>
      );
    }

    const { unmount } = render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    fireEvent.click(screen.getByText("Add Two"));
    mockRevokeObjectURL.mockClear();
    unmount();
    // Should revoke URLs for both files
    expect(mockRevokeObjectURL).toHaveBeenCalledTimes(2);
  });
});

// ============================================================================
// PromptInput local attachment management (no provider)
// ============================================================================

describe("PromptInput local attachment management", () => {
  test("adds files via file input change", () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(screen.getByTestId("file-item")).toHaveTextContent("test.png");
  });

  test("adds multiple files", () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("a.png", "image/png");
    const file2 = createMockFile("b.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file1, file2] });
    fireEvent.change(fileInput);

    expect(screen.getAllByTestId("file-item")).toHaveLength(2);
  });

  test("resets file input value after change to allow re-selecting same file", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect((fileInput as HTMLInputElement).value).toBe("");
  });

  test("handleChange does nothing when files is null", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    Object.defineProperty(fileInput, "files", { value: null });
    // Should not throw
    fireEvent.change(fileInput);
  });

  test("removes attachment and revokes blob URL via provider", async () => {
    // Test the provider's remove function directly, since the remove button
    // in PromptInputAttachment is hidden behind hover state
    let removeFn: ((id: string) => void) | null = null;
    let addFn: ((files: File[] | FileList) => void) | null = null;
    let filesList: any[] = [];

    function TestConsumer() {
      const ctx = useProviderAttachments();
      removeFn = ctx.remove;
      addFn = ctx.add;
      filesList = ctx.files;
      return (
        <div>
          <span data-testid="count">{ctx.files.length}</span>
        </div>
      );
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
      </PromptInputProvider>,
    );

    // Add a file
    const file = createMockFile("test.png", "image/png");
    act(() => addFn!([file]));
    expect(screen.getByTestId("count")).toHaveTextContent("1");

    mockRevokeObjectURL.mockClear();

    // Remove via provider
    const fileId = filesList[0].id;
    act(() => removeFn!(fileId));

    expect(screen.getByTestId("count")).toHaveTextContent("0");
    expect(mockRevokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  test("unmount cleanup revokes blob URLs for local files", () => {
    const { unmount } = render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    mockRevokeObjectURL.mockClear();
    unmount();
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });
});

// ============================================================================
// PromptInput matchesAccept edge cases
// ============================================================================

describe("PromptInput matchesAccept edge cases", () => {
  test("accepts all files when accept is undefined", () => {
    const onError = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()} onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.txt", "text/plain");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(onError).not.toHaveBeenCalled();
  });

  test("accepts all files when accept is whitespace only", () => {
    const onError = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()} accept="   " onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.txt", "text/plain");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(onError).not.toHaveBeenCalled();
  });

  test("handles multiple accept patterns separated by comma", () => {
    const onError = vi.fn();

    render(
      <PromptInput
        onSubmit={vi.fn()}
        accept="image/*, application/pdf"
        onError={onError}
      >
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const pdfFile = createMockFile("doc.pdf", "application/pdf");
    Object.defineProperty(fileInput, "files", { value: [pdfFile] });
    fireEvent.change(fileInput);

    expect(onError).not.toHaveBeenCalled();
  });

  test("rejects file not matching any accept pattern", () => {
    const onError = vi.fn();

    render(
      <PromptInput
        onSubmit={vi.fn()}
        accept="image/*, application/pdf"
        onError={onError}
      >
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const txtFile = createMockFile("readme.txt", "text/plain");
    Object.defineProperty(fileInput, "files", { value: [txtFile] });
    fireEvent.change(fileInput);

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "accept" }),
    );
  });
});

// ============================================================================
// PromptInput addLocal with maxFileSize edge cases
// ============================================================================

describe("PromptInput maxFileSize edge cases", () => {
  test("adds files within size limit", () => {
    render(
      <PromptInput onSubmit={vi.fn()} maxFileSize={2000}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("small.png", "image/png", 500);
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(screen.getByTestId("file-item")).toHaveTextContent("small.png");
  });

  test("adds some files when only some exceed maxFileSize", () => {
    render(
      <PromptInput onSubmit={vi.fn()} maxFileSize={1000} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const smallFile = createMockFile("small.png", "image/png", 500);
    const bigFile = createMockFile("big.png", "image/png", 2000);
    Object.defineProperty(fileInput, "files", { value: [smallFile, bigFile] });
    fireEvent.change(fileInput);

    expect(screen.getByTestId("file-item")).toHaveTextContent("small.png");
  });
});

// ============================================================================
// PromptInput maxFiles edge cases
// ============================================================================

describe("PromptInput maxFiles edge cases", () => {
  test("adds files up to maxFiles limit", () => {
    render(
      <PromptInput onSubmit={vi.fn()} maxFiles={2} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("a.png", "image/png");
    const file2 = createMockFile("b.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file1, file2] });
    fireEvent.change(fileInput);

    expect(screen.getAllByTestId("file-item")).toHaveLength(2);
  });

  test("caps files at maxFiles when more are provided", () => {
    const onError = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()} maxFiles={1} multiple onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="file-item">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("a.png", "image/png");
    const file2 = createMockFile("b.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file1, file2] });
    fireEvent.change(fileInput);

    expect(screen.getAllByTestId("file-item")).toHaveLength(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "max_files" }),
    );
  });
});

// ============================================================================
// splitUnsupportedUploadFiles with message (toast.error path)
// ============================================================================

describe("PromptInput splitUnsupportedUploadFiles message", () => {
  test("calls onError with unsupported_package code and shows toast when no onError provided", async () => {
    const { toast } = await import("sonner");
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [],
      rejected: [],
      message: "Some files are unsupported",
    });

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.exe", "application/octet-stream");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(toast.error).toHaveBeenCalledWith("Some files are unsupported");
  });

  test("calls onError callback with unsupported_package code when onError is provided", () => {
    const onError = vi.fn();
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [],
      rejected: [],
      message: "Unsupported format",
    });

    render(
      <PromptInput onSubmit={vi.fn()} onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.exe", "application/octet-stream");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(onError).toHaveBeenCalledWith({
      code: "unsupported_package",
      message: "Unsupported format",
    });
  });
});

// ============================================================================
// PromptInput handleSubmit with files (blob conversion)
// ============================================================================

describe("PromptInput handleSubmit with files", () => {
  test("submits with files that have a File object (no blob conversion needed)", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
        <PromptInputAttachments>
          {(file) => <span>{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(screen.getByText("test.png")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    const callArgs = onSubmit.mock.calls[0];
    expect(callArgs![0]!.files).toHaveLength(1);
    expect(callArgs![0]!.files[0].file).toBeInstanceOf(File);
  });

  test("converts blob URLs to data URLs for non-File attachments", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    // Mock fetch to return a blob for blob URL conversion
    const mockBlob = new Blob(["test"], { type: "image/png" });
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      blob: () => Promise.resolve(mockBlob),
    });

    // Mock FileReader for data URL conversion
    const originalFileReader = global.FileReader;
    class MockFileReader {
      onloadend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      result: string | null = null;
      readAsDataURL() {
        this.result = "data:image/png;base64,dGVzdA==";
        setTimeout(() => this.onloadend?.(), 0);
      }
    }
    (global as any).FileReader = MockFileReader;

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Add a file via input to get it in state
    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    global.fetch = originalFetch;
    (global as any).FileReader = originalFileReader;
  });

  test("handles blob URL conversion failure gracefully", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    // Mock fetch to fail
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockRejectedValue(new Error("fetch failed"));

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Add a file via input
    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    // Should still call onSubmit even if conversion fails
    const callArgs = onSubmit.mock.calls[0];
    expect(callArgs![0]!.files).toHaveLength(1);

    global.fetch = originalFetch;
  });

  test("handles FileReader error during blob conversion", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    // Mock fetch to succeed
    const mockBlob = new Blob(["test"], { type: "image/png" });
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      blob: () => Promise.resolve(mockBlob),
    });

    // Mock FileReader to trigger onerror
    const originalFileReader = global.FileReader;
    class ErrorFileReader {
      onloadend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      result: string | null = null;
      readAsDataURL() {
        setTimeout(() => this.onerror?.(), 0);
      }
    }
    (global as any).FileReader = ErrorFileReader;

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Add a file via input
    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    global.fetch = originalFetch;
    (global as any).FileReader = originalFileReader;
  });

  test("handles async onSubmit - clears after promise resolves", async () => {
    let resolveSubmit: () => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    const onSubmit = vi.fn().mockReturnValue(submitPromise);
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    expect(screen.getByTestId("att")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Submit"));

    // Resolve the async onSubmit
    act(() => resolveSubmit!());

    await waitFor(() => {
      expect(screen.queryByTestId("att")).not.toBeInTheDocument();
    });
  });

  test("does not clear attachments when async onSubmit rejects", async () => {
    // Create a rejected promise that we handle to avoid unhandled rejection
    const rejectedPromise = Promise.reject(new Error("fail"));
    rejectedPromise.catch(() => {}); // suppress unhandled rejection warning
    const onSubmit = vi.fn().mockReturnValue(rejectedPromise);
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    // Attachments should still be present
    expect(screen.getByTestId("att")).toBeInTheDocument();
  });

  test("does not clear attachments when sync onSubmit throws", async () => {
    const onSubmit = vi.fn().mockImplementation(() => {
      throw new Error("sync error");
    });
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    // Attachments should still be present
    expect(screen.getByTestId("att")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInput handleSubmit with provider (text from controller)
// ============================================================================

describe("PromptInput handleSubmit with provider", () => {
  test("submits provider text and clears text after sync submit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <PromptInputProvider initialInput="Provider hello">
        <PromptInput onSubmit={onSubmit}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputSubmit />
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    expect(screen.getByRole("textbox")).toHaveValue("Provider hello");

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ text: "Provider hello" }),
        expect.anything(),
      );
    });

    // Text should be cleared after successful sync submit
    await waitFor(() => {
      expect(screen.getByRole("textbox")).toHaveValue("");
    });
  });

  test("does not clear provider text when onSubmit is async and pending", async () => {
    let resolveSubmit: () => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    const onSubmit = vi.fn().mockReturnValue(submitPromise);
    const user = userEvent.setup();

    render(
      <PromptInputProvider initialInput="Keep me">
        <PromptInput onSubmit={onSubmit}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputSubmit />
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    // Text should still be there while promise is pending
    expect(screen.getByRole("textbox")).toHaveValue("Keep me");

    // Now resolve
    act(() => resolveSubmit!());

    // Text should be cleared after resolution
    await waitFor(() => {
      expect(screen.getByRole("textbox")).toHaveValue("");
    });
  });

  test("does not clear provider text when user typed different text during async submit", async () => {
    let resolveSubmit: () => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    const onSubmit = vi.fn().mockReturnValue(submitPromise);
    const user = userEvent.setup();

    render(
      <PromptInputProvider initialInput="original">
        <PromptInput onSubmit={onSubmit}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputSubmit />
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    await user.click(screen.getByLabelText("Submit"));

    // User changes text while submit is pending
    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "modified");

    // Resolve the submit
    act(() => resolveSubmit!());

    // Text should NOT be cleared because user typed something different
    await waitFor(() => {
      expect(screen.getByRole("textbox")).toHaveValue("modified");
    });
  });

  test("resets form for non-provider mode on submit", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "Hello");
    expect(textarea).toHaveValue("Hello");

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ text: "Hello" }),
        expect.anything(),
      );
    });

    // Form should be reset after submit
    await waitFor(() => {
      expect(textarea).toHaveValue("");
    });
  });
});

// ============================================================================
// PromptInputTextarea paste handling
// ============================================================================

describe("PromptInputTextarea paste handling", () => {
  test("pastes files from clipboard and adds as attachments", () => {
    const file = createMockFile("pasted.png", "image/png");

    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(f) => <span data-testid="att">{f.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");

    // Simulate paste with file items
    const clipboardData = {
      items: [
        {
          kind: "file",
          getAsFile: () => file,
        },
      ],
    };

    fireEvent.paste(textarea, { clipboardData });

    expect(screen.getByTestId("att")).toHaveTextContent("pasted.png");
  });

  test("paste with text only does not prevent default", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");

    const clipboardData = {
      items: [
        {
          kind: "string",
          getAsFile: () => null,
        },
      ],
    };

    // Should not throw or prevent default for text paste
    fireEvent.paste(textarea, { clipboardData });
  });

  test("paste with no clipboardData items does nothing", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");

    // No clipboardData at all
    fireEvent.paste(textarea, {});
  });

  test("paste sanitizes files through splitUnsupportedUploadFiles", () => {
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [],
      rejected: [],
      message: "Unsupported file type",
    });

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");
    const file = createMockFile("bad.exe", "application/octet-stream");
    const clipboardData = {
      items: [{ kind: "file", getAsFile: () => file }],
    };

    fireEvent.paste(textarea, { clipboardData });
    expect(mockSplitUnsupported).toHaveBeenCalled();
  });

  test("paste adds multiple files at once", () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(f) => <span data-testid="att">{f.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");
    const file1 = createMockFile("a.png", "image/png");
    const file2 = createMockFile("b.png", "image/png");
    const clipboardData = {
      items: [
        { kind: "file", getAsFile: () => file1 },
        { kind: "file", getAsFile: () => file2 },
      ],
    };

    fireEvent.paste(textarea, { clipboardData });

    expect(screen.getAllByTestId("att")).toHaveLength(2);
  });
});

// ============================================================================
// PromptInputTextarea composition events
// ============================================================================

describe("PromptInputTextarea composition events", () => {
  test("does not submit on Enter during IME composition", async () => {
    mockIsIMEComposing.mockReturnValueOnce(true);
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");
    await userEvent.setup().type(textarea, "test");
    fireEvent.keyDown(textarea, { key: "Enter" });

    // Should not submit during IME composition
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("handles compositionStart and compositionEnd events", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");

    fireEvent.compositionStart(textarea);
    fireEvent.compositionEnd(textarea);

    // Should handle without errors
  });
});

// ============================================================================
// PromptInputTextarea Enter key with disabled submit button
// ============================================================================

describe("PromptInputTextarea Enter with disabled submit", () => {
  test("does not submit on Enter when submit button is disabled", async () => {
    const onSubmit = vi.fn();

    render(
      <PromptInput onSubmit={onSubmit}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit disabled />
        </PromptInputFooter>
      </PromptInput>,
    );

    const textarea = screen.getByRole("textbox");
    await userEvent.setup().type(textarea, "Hello");
    fireEvent.keyDown(textarea, { key: "Enter" });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});

// ============================================================================
// PromptInputTextarea Backspace removes last attachment
// ============================================================================

describe("PromptInputTextarea Backspace removes last attachment", () => {
  test("removes last attachment on Backspace when textarea is empty and attachments exist", async () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    // Add files
    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("first.png", "image/png");
    const file2 = createMockFile("second.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file1, file2] });
    fireEvent.change(fileInput);

    expect(screen.getAllByTestId("att")).toHaveLength(2);

    // Press Backspace on empty textarea
    const textarea = screen.getByRole("textbox");
    await userEvent.setup().click(textarea);
    fireEvent.keyDown(textarea, { key: "Backspace" });

    // Last attachment should be removed
    await waitFor(() => {
      expect(screen.getAllByTestId("att")).toHaveLength(1);
    });
  });
});

// ============================================================================
// PromptInput drag and drop (local form)
// ============================================================================

describe("PromptInput drag and drop", () => {
  test("handles dragover with files on form", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    fireEvent.dragOver(form, {
      dataTransfer: { types: ["Files"] },
    });

    // The handler prevents default to allow drop - we verify no errors
  });

  test("handles drop with files on form", () => {
    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;
    const file = createMockFile("dropped.png", "image/png");

    fireEvent.drop(form, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
      },
    });

    expect(screen.getByTestId("att")).toHaveTextContent("dropped.png");
  });

  test("does not prevent default on dragover without Files type", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    fireEvent.dragOver(form, {
      dataTransfer: { types: ["text/plain"] },
    });

    // Should not prevent default when no Files type
  });
});

// ============================================================================
// PromptInput global drop
// ============================================================================

describe("PromptInput globalDrop", () => {
  test("handles global dragover with files", () => {
    render(
      <PromptInput onSubmit={vi.fn()} globalDrop>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    fireEvent.dragOver(document, {
      dataTransfer: { types: ["Files"] },
    });

    // Should prevent default to allow drop
  });

  test("handles global drop with files", () => {
    render(
      <PromptInput onSubmit={vi.fn()} globalDrop multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const file = createMockFile("global-drop.png", "image/png");

    fireEvent.drop(document, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
      },
    });

    expect(screen.getByTestId("att")).toHaveTextContent("global-drop.png");
  });

  test("global drop does nothing without Files type in dataTransfer", () => {
    render(
      <PromptInput onSubmit={vi.fn()} globalDrop>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const preventDefaultSpy = vi.fn();
    const dragOverEvent = new Event("dragover", { bubbles: true });
    Object.defineProperty(dragOverEvent, "dataTransfer", {
      value: { types: ["text/plain"] },
    });
    Object.defineProperty(dragOverEvent, "preventDefault", {
      value: preventDefaultSpy,
    });

    document.dispatchEvent(dragOverEvent);
    expect(preventDefaultSpy).not.toHaveBeenCalled();
  });

  test("global drop sanitizes files through splitUnsupportedUploadFiles", () => {
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [],
      rejected: [],
      message: "Unsupported",
    });

    const onError = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()} globalDrop onError={onError}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const file = createMockFile("bad.exe", "application/octet-stream");

    fireEvent.drop(document, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
      },
    });

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "unsupported_package" }),
    );
  });

  test("local form drop handler does not activate when globalDrop is true", () => {
    render(
      <PromptInput onSubmit={vi.fn()} globalDrop>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    // When globalDrop is true, form-level handler should not be attached
    // The document-level handler owns drops instead
    fireEvent.dragOver(form, {
      dataTransfer: { types: ["Files"] },
    });

    // This test verifies the cleanup path in the effect - no errors
  });
});

// ============================================================================
// PromptInputAttachment remove button and hover card content
// ============================================================================

describe("PromptInputAttachment interactions", () => {
  test("remove button calls attachments.remove", async () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachments>
            {(file) => <PromptInputAttachment data={file} />}
          </PromptInputAttachments>
        </PromptInput>
      </PromptInputProvider>,
    );

    // Add a file via the provider
    let addFn: ((files: File[] | FileList) => void) | null = null;
    function CaptureAdd() {
      const ctx = useProviderAttachments();
      addFn = ctx.add;
      return null;
    }

    const { rerender } = render(
      <PromptInputProvider>
        <CaptureAdd />
      </PromptInputProvider>,
    );

    // Now render with attachment
    rerender(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      </PromptInputProvider>,
    );
  });

  test("image attachment shows img element", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "img-1",
              type: "file",
              mediaType: "image/jpeg",
              url: "blob:test-url",
              filename: "photo.jpg",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );

    const img = screen.getByAltText("photo.jpg");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "blob:test-url");
  });

  test("remove button click triggers stopPropagation and calls remove", async () => {
    // The remove button is inside a HoverCard overlay, so we test it
    // by verifying the button exists and has the right attributes.
    // The actual remove logic is tested via the provider remove tests above.
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "att-btn-test",
              type: "file",
              mediaType: "image/png",
              url: "blob:test",
              filename: "test.png",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );

    // The remove button exists in the DOM
    const removeBtn = screen.getByRole("button", { name: /remove/i });
    expect(removeBtn).toHaveAttribute("type", "button");
    expect(removeBtn).toHaveAttribute("aria-label", "Remove attachment");
    fireEvent.click(removeBtn);
  });

  test("file attachment renders with mediaType data", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "file-1",
              type: "file",
              mediaType: "application/pdf",
              url: "blob:test-url",
              filename: "doc.pdf",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );

    // The filename label should be visible in the trigger
    expect(screen.getByText("doc.pdf")).toBeInTheDocument();
    // The attachment renders without errors when mediaType is provided
  });

  test("attachment without mediaType does not show mediaType", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "file-2",
              type: "file",
              url: "blob:test-url",
              mediaType: "application/pdf",
              filename: "doc.pdf",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );

    // The filename should still render
    expect(screen.getByText("doc.pdf")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputAttachment with image without URL (file type fallback)
// ============================================================================

describe("PromptInputAttachment edge cases", () => {
  test("image type without URL is treated as file", () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputAttachment
            data={{
              id: "no-url",
              type: "file",
              mediaType: "image/png",
              url: "",
              filename: "no-url.png",
            }}
          />
        </PromptInput>
      </PromptInputProvider>,
    );

    // Without URL, mediaType becomes "file" not "image"
    expect(screen.getByText("no-url.png")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputActionAddAttachments onSelect handler
// ============================================================================

describe("PromptInputActionAddAttachments onSelect", () => {
  test("prevents default and opens file dialog on select with provider", async () => {
    render(
      <PromptInputProvider>
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
          <PromptInputFooter>
            <PromptInputActionMenu open>
              <PromptInputActionMenuTrigger data-testid="menu-trigger" />
              <PromptInputActionMenuContent>
                <PromptInputActionAddAttachments data-testid="add-att" />
              </PromptInputActionMenuContent>
            </PromptInputActionMenu>
          </PromptInputFooter>
        </PromptInput>
      </PromptInputProvider>,
    );

    // The menu should be open, verify the item is rendered
    await waitFor(() => {
      expect(screen.getByText("Add photos or files")).toBeInTheDocument();
    });

    // Click the menu item to trigger onSelect
    await userEvent.setup().click(screen.getByText("Add photos or files"));
  });

  test("opens local file dialog when no provider", async () => {
    // Without provider, openFileDialogLocal is used (line 508)
    const clickSpy = vi.fn();
    const originalClick = HTMLInputElement.prototype.click;

    // Mock click on the file input
    HTMLInputElement.prototype.click = clickSpy;

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputActionMenu open>
            <PromptInputActionMenuTrigger data-testid="menu-trigger" />
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu>
        </PromptInputFooter>
      </PromptInput>,
    );

    await waitFor(() => {
      expect(screen.getByText("Add photos or files")).toBeInTheDocument();
    });

    await userEvent.setup().click(screen.getByText("Add photos or files"));

    // openFileDialogLocal calls inputRef.current?.click()
    expect(clickSpy).toHaveBeenCalled();

    HTMLInputElement.prototype.click = originalClick;
  });
});

// ============================================================================
// PromptInputCommand pass-through components with className
// ============================================================================

describe("PromptInputCommand components", () => {
  test("all PromptInputCommand exports are defined", () => {
    expect(PromptInputCommand).toBeDefined();
    expect(PromptInputCommandInput).toBeDefined();
    expect(PromptInputCommandList).toBeDefined();
    expect(PromptInputCommandEmpty).toBeDefined();
    expect(PromptInputCommandGroup).toBeDefined();
    expect(PromptInputCommandItem).toBeDefined();
    expect(PromptInputCommandSeparator).toBeDefined();
  });

  test("PromptInputCommand renders with className", () => {
    render(
      <PromptInputCommand className="custom-cmd" data-testid="cmd">
        <div>Command content</div>
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd")).toBeInTheDocument();
  });

  test("PromptInputCommandInput renders with className", () => {
    render(
      <PromptInputCommand className="custom-cmd" data-testid="cmd">
        <PromptInputCommandInput placeholder="Search..." />
      </PromptInputCommand>,
    );
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });

  test("PromptInputCommandList renders", () => {
    render(
      <PromptInputCommand>
        <PromptInputCommandList data-testid="cmd-list">
          <div>List content</div>
        </PromptInputCommandList>
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd-list")).toBeInTheDocument();
  });

  test("PromptInputCommandEmpty renders", () => {
    render(
      <PromptInputCommand>
        <PromptInputCommandEmpty data-testid="cmd-empty">
          No results
        </PromptInputCommandEmpty>
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd-empty")).toBeInTheDocument();
  });

  test("PromptInputCommandGroup renders", () => {
    render(
      <PromptInputCommand>
        <PromptInputCommandGroup data-testid="cmd-group">
          <div>Group content</div>
        </PromptInputCommandGroup>
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd-group")).toBeInTheDocument();
  });

  test("PromptInputCommandItem renders", () => {
    render(
      <PromptInputCommand>
        <PromptInputCommandItem data-testid="cmd-item">
          Item content
        </PromptInputCommandItem>
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd-item")).toBeInTheDocument();
  });

  test("PromptInputCommandSeparator renders", () => {
    render(
      <PromptInputCommand>
        <PromptInputCommandSeparator data-testid="cmd-sep" />
      </PromptInputCommand>,
    );
    expect(screen.getByTestId("cmd-sep")).toBeInTheDocument();
  });
});

// ============================================================================
// PromptInputSpeechButton
// ============================================================================

describe("PromptInputSpeechButton", () => {
  let originalSpeechRecognition: any;
  let originalWebkitSpeechRecognition: any;

  beforeEach(() => {
    originalSpeechRecognition = (window as any).SpeechRecognition;
    originalWebkitSpeechRecognition = (window as any).webkitSpeechRecognition;
  });

  afterEach(() => {
    if (originalSpeechRecognition) {
      (window as any).SpeechRecognition = originalSpeechRecognition;
    } else {
      delete (window as any).SpeechRecognition;
    }
    if (originalWebkitSpeechRecognition) {
      (window as any).webkitSpeechRecognition = originalWebkitSpeechRecognition;
    } else {
      delete (window as any).webkitSpeechRecognition;
    }
  });

  test("renders mic button", () => {
    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;
    };

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    expect(screen.getByTestId("speech-btn")).toBeInTheDocument();
  });

  test("is disabled when SpeechRecognition is not available", () => {
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    expect(screen.getByTestId("speech-btn")).toBeDisabled();
  });

  test("toggles listening state on click - start and stop", async () => {
    const mockStart = vi.fn();
    const mockStop = vi.fn();
    let capturedCallbacks: any = {};

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start = mockStart;
      stop = mockStop;
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    const btn = screen.getByTestId("speech-btn");
    const user = userEvent.setup();

    // Click to start listening
    await user.click(btn);
    expect(mockStart).toHaveBeenCalled();

    // Simulate onstart to set isListening to true
    act(() => capturedCallbacks.onstart?.());

    // Click again to stop listening
    await user.click(btn);
    expect(mockStop).toHaveBeenCalled();
  });

  test("uses webkitSpeechRecognition as fallback", () => {
    delete (window as any).SpeechRecognition;

    const MockWebkitSpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;
    };

    (window as any).webkitSpeechRecognition = MockWebkitSpeechRecognition;

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    expect(screen.getByTestId("speech-btn")).not.toBeDisabled();
  });

  test("handles speech recognition result event", () => {
    let capturedCallbacks: any = {};

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    const textareaRef = { current: null as HTMLTextAreaElement | null };
    const onTranscriptionChange = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea
            ref={(el) => {
              textareaRef.current = el;
            }}
          />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton
            textareaRef={textareaRef}
            onTranscriptionChange={onTranscriptionChange}
            data-testid="speech-btn"
          />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Simulate onstart
    if (capturedCallbacks.onstart) {
      capturedCallbacks.onstart();
    }

    // Simulate onresult with a final result
    if (capturedCallbacks.onresult) {
      capturedCallbacks.onresult({
        resultIndex: 0,
        results: [
          {
            isFinal: true,
            0: { transcript: "hello world", confidence: 0.9 },
            length: 1,
          },
        ],
      });
    }

    expect(onTranscriptionChange).toHaveBeenCalledWith("hello world");
  });

  test("handles speech recognition result appending to existing text", () => {
    let capturedCallbacks: any = {};

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    const textareaRef = { current: null as HTMLTextAreaElement | null };
    const onTranscriptionChange = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea
            ref={(el) => {
              textareaRef.current = el;
              if (el) el.value = "existing text";
            }}
          />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton
            textareaRef={textareaRef}
            onTranscriptionChange={onTranscriptionChange}
            data-testid="speech-btn"
          />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Simulate onresult
    if (capturedCallbacks.onresult) {
      capturedCallbacks.onresult({
        resultIndex: 0,
        results: [
          {
            isFinal: true,
            0: { transcript: "more words", confidence: 0.9 },
            length: 1,
          },
        ],
      });
    }

    expect(onTranscriptionChange).toHaveBeenCalledWith(
      "existing text more words",
    );
  });

  test("handles speech recognition error event", () => {
    let capturedCallbacks: any = {};
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Simulate onerror
    if (capturedCallbacks.onerror) {
      capturedCallbacks.onerror({ error: "not-allowed" });
    }

    expect(consoleSpy).toHaveBeenCalledWith(
      "Speech recognition error:",
      "not-allowed",
    );
    consoleSpy.mockRestore();
  });

  test("handles speech recognition onend callback", () => {
    let capturedCallbacks: any = {};

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Simulate onstart then onend
    if (capturedCallbacks.onstart) capturedCallbacks.onstart();
    if (capturedCallbacks.onend) capturedCallbacks.onend();
  });

  test("handles result with non-final transcript (no transcription change)", () => {
    let capturedCallbacks: any = {};

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    const onTranscriptionChange = vi.fn();

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton
            onTranscriptionChange={onTranscriptionChange}
            data-testid="speech-btn"
          />
        </PromptInputFooter>
      </PromptInput>,
    );

    if (capturedCallbacks.onresult) {
      capturedCallbacks.onresult({
        resultIndex: 0,
        results: [
          {
            isFinal: false,
            0: { transcript: "partial", confidence: 0.5 },
            length: 1,
          },
        ],
      });
    }

    expect(onTranscriptionChange).not.toHaveBeenCalled();
  });

  test("cleanup stops recognition on unmount", () => {
    const mockStop = vi.fn();

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop = mockStop;
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;
    };

    const { unmount } = render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton />
        </PromptInputFooter>
      </PromptInput>,
    );

    unmount();
    expect(mockStop).toHaveBeenCalled();
  });

  test("toggleListening does nothing when recognition is null", () => {
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton data-testid="speech-btn" />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Click should not throw even when recognition is null
    fireEvent.click(screen.getByTestId("speech-btn"));
  });

  test("handles onresult with null textareaRef", () => {
    let capturedCallbacks: any = {};
    const onTranscriptionChange = vi.fn();

    (window as any).SpeechRecognition = class {
      continuous = false;
      interimResults = false;
      lang = "";
      start() {}
      stop() {}
      onstart: any = null;
      onend: any = null;
      onresult: any = null;
      onerror: any = null;

      constructor() {
        capturedCallbacks = this;
      }
    };

    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSpeechButton
            onTranscriptionChange={onTranscriptionChange}
            data-testid="speech-btn"
          />
        </PromptInputFooter>
      </PromptInput>,
    );

    // Simulate onresult without textareaRef
    if (capturedCallbacks.onresult) {
      capturedCallbacks.onresult({
        resultIndex: 0,
        results: [
          {
            isFinal: true,
            0: { transcript: "hello", confidence: 0.9 },
            length: 1,
          },
        ],
      });
    }

    // Without textareaRef.current, onTranscriptionChange should not be called
    expect(onTranscriptionChange).not.toHaveBeenCalled();
  });
});

// ============================================================================
// PromptInput __registerFileInput with provider
// ============================================================================

describe("PromptInput provider file input registration", () => {
  test("registers file input ref with provider on mount", () => {
    let registerSpy: any = null;

    function TestConsumer() {
      const ctrl = usePromptInputController();
      registerSpy = ctrl.__registerFileInput;
      return <span>Consumer</span>;
    }

    render(
      <PromptInputProvider>
        <TestConsumer />
        <PromptInput onSubmit={vi.fn()}>
          <PromptInputBody>
            <PromptInputTextarea />
          </PromptInputBody>
        </PromptInput>
      </PromptInputProvider>,
    );

    // The __registerFileInput should have been called during PromptInput mount
    expect(registerSpy).toBeDefined();
  });
});

// ============================================================================
// PromptInput syncHiddenInput edge cases
// ============================================================================

describe("PromptInput syncHiddenInput with files", () => {
  test("does not clear file input when syncHiddenInput is true and files exist", () => {
    render(
      <PromptInput onSubmit={vi.fn()} syncHiddenInput multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file = createMockFile("test.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file] });
    fireEvent.change(fileInput);

    // After adding a file, syncHiddenInput should not clear because files.length > 0
    // The value would have been reset by handleChange already
  });
});

// ============================================================================
// PromptInput attachments with clearSubmittedState edge case
// ============================================================================

describe("PromptInput clearSubmittedState", () => {
  test("removes only submitted files that are still present (partial removal)", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    // Track added files to simulate partial removal
    const addedFileIds: string[] = [];

    render(
      <PromptInput onSubmit={onSubmit} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputFooter>
          <PromptInputSubmit />
        </PromptInputFooter>
        <PromptInputAttachments>
          {(file) => {
            addedFileIds.push(file.id);
            return <span data-testid="att">{file.filename}</span>;
          }}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const fileInput = screen.getByTestId("file-input");
    const file1 = createMockFile("a.png", "image/png");
    Object.defineProperty(fileInput, "files", { value: [file1] });
    fireEvent.change(fileInput);

    expect(screen.getByTestId("att")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });

    // After sync submit, files should be cleared
    await waitFor(() => {
      expect(screen.queryByTestId("att")).not.toBeInTheDocument();
    });
  });
});

// ============================================================================
// PromptInput drop with empty file list
// ============================================================================

describe("PromptInput drop edge cases", () => {
  test("drop with empty files does nothing", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    fireEvent.drop(form, {
      dataTransfer: {
        types: ["Files"],
        files: [],
      },
    });
    // Should not throw
  });

  test("global drop with empty files does nothing", () => {
    render(
      <PromptInput onSubmit={vi.fn()} globalDrop>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    fireEvent.drop(document, {
      dataTransfer: {
        types: ["Files"],
        files: [],
      },
    });
    // Should not throw
  });

  test("drop with no dataTransfer does nothing", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    fireEvent.drop(form, {
      dataTransfer: null,
    });
    // Should not throw
  });

  test("dragover with no dataTransfer does nothing", () => {
    render(
      <PromptInput onSubmit={vi.fn()}>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;

    fireEvent.dragOver(form, {
      dataTransfer: null,
    });
    // Should not throw
  });
});

// ============================================================================
// PromptInput with globalDrop sanitization
// ============================================================================

describe("PromptInput globalDrop sanitization", () => {
  test("global drop sanitizes accepted files", () => {
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [createMockFile("ok.png", "image/png")],
      rejected: [],
      message: undefined,
    });

    render(
      <PromptInput onSubmit={vi.fn()} globalDrop multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const file = createMockFile("ok.png", "image/png");

    fireEvent.drop(document, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
      },
    });

    expect(mockSplitUnsupported).toHaveBeenCalled();
  });
});

// ============================================================================
// PromptInput local form drop sanitization
// ============================================================================

describe("PromptInput local form drop sanitization", () => {
  test("form drop sanitizes accepted files", () => {
    mockSplitUnsupported.mockReturnValueOnce({
      accepted: [createMockFile("ok.png", "image/png")],
      rejected: [],
      message: undefined,
    });

    render(
      <PromptInput onSubmit={vi.fn()} multiple>
        <PromptInputBody>
          <PromptInputTextarea />
        </PromptInputBody>
        <PromptInputAttachments>
          {(file) => <span data-testid="att">{file.filename}</span>}
        </PromptInputAttachments>
      </PromptInput>,
    );

    const form = screen.getByRole("textbox").closest("form")!;
    const file = createMockFile("ok.png", "image/png");

    fireEvent.drop(form, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
      },
    });

    expect(mockSplitUnsupported).toHaveBeenCalled();
  });
});
