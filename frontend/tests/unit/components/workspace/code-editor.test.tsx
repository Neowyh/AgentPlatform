import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

vi.mock("@uiw/react-codemirror", () => ({
  default: ({
    value,
    readOnly,
    placeholder,
    className,
  }: {
    value: string;
    readOnly?: boolean;
    placeholder?: string;
    className?: string;
  }) => (
    <div
      data-testid="codemirror"
      className={className}
      data-readonly={readOnly}
      data-placeholder={placeholder}
    >
      {value}
    </div>
  ),
}));

vi.mock("@codemirror/lang-css", () => ({ css: () => ({}) }));
vi.mock("@codemirror/lang-html", () => ({ html: () => ({}) }));
vi.mock("@codemirror/lang-javascript", () => ({
  javascript: () => ({}),
}));
vi.mock("@codemirror/lang-json", () => ({ json: () => ({}) }));
vi.mock("@codemirror/lang-markdown", () => ({
  markdown: () => ({}),
  markdownLanguage: {},
}));
vi.mock("@codemirror/lang-python", () => ({ python: () => ({}) }));
vi.mock("@codemirror/language-data", () => ({ languages: [] }));
vi.mock("@uiw/codemirror-theme-basic", () => ({
  basicLightInit: () => ({}),
}));
vi.mock("@uiw/codemirror-theme-monokai", () => ({
  monokaiInit: () => ({}),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: ({
    value,
    readOnly,
    className,
  }: {
    value: string;
    readOnly?: boolean;
    className?: string;
  }) => (
    <textarea
      data-testid="textarea"
      readOnly={readOnly}
      className={className}
      value={value}
    />
  ),
}));

let mockIsLoading = false;
vi.mock("@/components/workspace/messages/context", () => ({
  useThread: () => ({
    thread: { isLoading: mockIsLoading },
  }),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let CodeEditor: typeof import("@/components/workspace/code-editor").CodeEditor;

beforeEach(async () => {
  vi.clearAllMocks();
  mockIsLoading = false;
  const mod = await import("@/components/workspace/code-editor");
  CodeEditor = mod.CodeEditor;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("CodeEditor", () => {
  test("renders CodeMirror when not loading", () => {
    render(<CodeEditor value="hello world" />);
    expect(screen.getByTestId("codemirror")).toBeInTheDocument();
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  test("renders Textarea when loading", () => {
    mockIsLoading = true;
    render(<CodeEditor value="loading content" />);
    expect(screen.getByTestId("textarea")).toBeInTheDocument();
    expect(screen.queryByTestId("codemirror")).not.toBeInTheDocument();
  });

  test("passes readonly prop to CodeMirror", () => {
    render(<CodeEditor value="code" readonly />);
    expect(screen.getByTestId("codemirror")).toHaveAttribute(
      "data-readonly",
      "true",
    );
  });

  test("passes placeholder to CodeMirror", () => {
    render(<CodeEditor value="" placeholder="Type code..." />);
    expect(screen.getByTestId("codemirror")).toHaveAttribute(
      "data-placeholder",
      "Type code...",
    );
  });

  test("applies custom className", () => {
    const { container } = render(
      <CodeEditor value="" className="custom-editor" />,
    );
    // className is applied to the wrapper div, not the codemirror mock
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveClass("custom-editor");
  });

  test("textarea is readOnly when loading", () => {
    mockIsLoading = true;
    render(<CodeEditor value="content" />);
    expect(screen.getByTestId("textarea")).toHaveAttribute("readonly");
  });

  test("textarea shows the value when loading", () => {
    mockIsLoading = true;
    render(<CodeEditor value="some code" />);
    expect(screen.getByTestId("textarea")).toHaveValue("some code");
  });

  test("passes disabled prop as readonly to CodeMirror", () => {
    render(<CodeEditor value="code" disabled />);
    expect(screen.getByTestId("codemirror")).toHaveAttribute(
      "data-readonly",
      "true",
    );
  });

  test("passes settings for lineNumbers", () => {
    render(
      <CodeEditor
        value=""
        settings={{ lineNumbers: true, foldGutter: true }}
      />,
    );
    expect(screen.getByTestId("codemirror")).toBeInTheDocument();
  });

  test("handles empty value", () => {
    render(<CodeEditor value="" />);
    expect(screen.getByTestId("codemirror")).toBeInTheDocument();
  });
});
