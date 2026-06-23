import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

vi.mock("@uiw/react-codemirror", () => ({
  default: ({
    value,
    onChange,
    className,
  }: {
    value: string;
    onChange?: (value: string) => void;
    className?: string;
  }) => (
    <div data-testid="codemirror" className={className}>
      <textarea
        data-testid="codemirror-input"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  ),
}));

vi.mock("@codemirror/lang-markdown", () => ({
  markdown: () => ({}),
  markdownLanguage: {},
}));
vi.mock("@codemirror/language-data", () => ({ languages: [] }));
vi.mock("@uiw/codemirror-theme-basic", () => ({
  basicLightInit: () => ({}),
}));
vi.mock("@uiw/codemirror-theme-monokai", () => ({
  monokaiInit: () => ({}),
}));

vi.mock("@/components/ui/alert", () => ({
  Alert: ({ children, variant }: any) => (
    <div data-testid="alert" data-variant={variant}>
      {children}
    </div>
  ),
  AlertDescription: ({ children }: any) => (
    <div data-testid="alert-description">{children}</div>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, size, variant, ...props }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-size={size}
      data-variant={variant}
      {...props}
    >
      {children}
    </button>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let SkillEditor: typeof import("@/components/workspace/settings/skill-editor").SkillEditor;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod = await import("@/components/workspace/settings/skill-editor");
  SkillEditor = mod.SkillEditor;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SkillEditor", () => {
  const VALID_CONTENT =
    "---\nname: test\ndescription: A test skill\n---\n\n# Content here";

  test("renders the editor header with skill name", () => {
    render(
      <SkillEditor
        skillName="my-skill"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Edit Skill: my-skill")).toBeInTheDocument();
  });

  test("renders cancel and save buttons", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  test("calls onClose when cancel is clicked", () => {
    const onClose = vi.fn();
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("renders CodeMirror editor", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("codemirror")).toBeInTheDocument();
  });

  test("renders editor and preview labels", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Editor")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
  });

  test("shows validation error for missing frontmatter", async () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent="no frontmatter here"
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(screen.getByTestId("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/Missing YAML frontmatter/)).toBeInTheDocument();
  });

  test("shows validation error for missing name field", async () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent="---\ndescription: test\n---"
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(
        screen.getByText(/Missing required field: "name"/),
      ).toBeInTheDocument();
    });
  });

  test("shows validation error for missing description field", async () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent="---\nname: test\n---"
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(
        screen.getByText(/Missing required field: "description"/),
      ).toBeInTheDocument();
    });
  });

  test("calls onSave with content when validation passes", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(VALID_CONTENT);
    });
  });

  test("does not call onSave when validation fails", async () => {
    const onSave = vi.fn();
    render(
      <SkillEditor
        skillName="test"
        initialContent="invalid content"
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(screen.getByTestId("alert")).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  test("shows Saving... text while saving", async () => {
    let resolveSave: () => void;
    const savePromise = new Promise<void>((resolve) => {
      resolveSave = resolve;
    });
    const onSave = vi.fn().mockReturnValue(savePromise);

    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(screen.getByText("Saving...")).toBeInTheDocument();
    });

    resolveSave!();
    await waitFor(() => {
      expect(screen.queryByText("Saving...")).not.toBeInTheDocument();
    });
  });

  test("renders preview section with content", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    // Preview should show content after frontmatter (appears in both editor and preview)
    const contentElements = screen.getAllByText(/Content here/);
    expect(contentElements.length).toBeGreaterThanOrEqual(1);
  });

  test("updates content when editor value changes", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const input = screen.getByTestId("codemirror-input");
    fireEvent.change(input, {
      target: { value: "---\nname: new\ndescription: new\n---\n\nNew content" },
    });

    // Content appears in both editor textarea and preview
    const newContentElements = screen.getAllByText(/New content/);
    expect(newContentElements.length).toBeGreaterThanOrEqual(1);
  });

  test("shows validation errors inline when content changes", () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const input = screen.getByTestId("codemirror-input");
    fireEvent.change(input, { target: { value: "bad content" } });

    // Should show validation error immediately
    expect(screen.getByText(/Missing YAML frontmatter/)).toBeInTheDocument();
  });

  test("save button is disabled while saving", async () => {
    let resolveSave: () => void;
    const savePromise = new Promise<void>((resolve) => {
      resolveSave = resolve;
    });
    const onSave = vi.fn().mockReturnValue(savePromise);

    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(screen.getByText("Saving...")).toBeDisabled();
    });

    resolveSave!();
  });

  test("shows validation error for unterminated frontmatter", async () => {
    render(
      <SkillEditor
        skillName="test"
        initialContent="---\nname: test\ndescription: test"
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(
        screen.getByText(/Unterminated YAML frontmatter/),
      ).toBeInTheDocument();
    });
  });

  test("handles onSave throwing an error", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const onSave = vi.fn().mockRejectedValue(new Error("Save failed"));

    render(
      <SkillEditor
        skillName="test"
        initialContent={VALID_CONTENT}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    });

    // Should recover - Saving... text should disappear
    await waitFor(() => {
      expect(screen.queryByText("Saving...")).not.toBeInTheDocument();
    });

    consoleSpy.mockRestore();
  });
});
