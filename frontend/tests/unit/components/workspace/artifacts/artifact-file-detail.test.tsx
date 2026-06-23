import {
  render,
  screen,
  cleanup,
  fireEvent,
  act,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ---------------------------------------------------------------------------
// Hoisted mocks (must use vi.hoisted for vars referenced inside vi.mock)
// ---------------------------------------------------------------------------

const {
  mockToastSuccess,
  mockToastError,
  mockUseArtifactContent,
  mockGetArtifactViewState,
  mockCheckCodeFile,
  mockGetFileName,
  mockUrlOfArtifact,
  mockWriteTextToClipboard,
  mockFindToolCallResult,
  mockInstallSkill,
  mockUseThread,
  mockToggleOnValueChange,
} = vi.hoisted(() => ({
  mockToastSuccess: vi.fn(),
  mockToastError: vi.fn(),
  mockUseArtifactContent: vi.fn(),
  mockGetArtifactViewState: vi.fn(),
  mockCheckCodeFile: vi.fn(),
  mockGetFileName: vi.fn(),
  mockUrlOfArtifact: vi.fn(),
  mockWriteTextToClipboard: vi.fn(),
  mockFindToolCallResult: vi.fn(),
  mockInstallSkill: vi.fn(),
  mockUseThread: vi.fn(),
  mockToggleOnValueChange: {
    current: null as ((value: string) => void) | null,
  },
}));

// ---------------------------------------------------------------------------
// vi.mock declarations
// ---------------------------------------------------------------------------

vi.mock("sonner", () => ({
  toast: { success: mockToastSuccess, error: mockToastError },
}));

vi.mock("streamdown", () => ({
  Streamdown: ({ children }: any) => (
    <div data-testid="streamdown">{children}</div>
  ),
}));

vi.mock("@/components/ai-elements/artifact", () => ({
  Artifact: ({ children, className, ...props }: any) => (
    <div data-testid="artifact" className={className} {...props}>
      {children}
    </div>
  ),
  ArtifactAction: ({ label, tooltip, disabled, onClick }: any) => (
    <button
      data-testid="artifact-action"
      data-label={label}
      data-tooltip={tooltip}
      disabled={disabled}
      onClick={onClick}
    >
      {label || tooltip}
    </button>
  ),
  ArtifactActions: ({ children }: any) => (
    <div data-testid="artifact-actions">{children}</div>
  ),
  ArtifactContent: ({ children, className }: any) => (
    <div data-testid="artifact-content" className={className}>
      {children}
    </div>
  ),
  ArtifactHeader: ({ children, className }: any) => (
    <div data-testid="artifact-header" className={className}>
      {children}
    </div>
  ),
  ArtifactTitle: ({ children }: any) => (
    <div data-testid="artifact-title">{children}</div>
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, value, onValueChange }: any) => (
    <div data-testid="select" data-value={value}>
      {children}
    </div>
  ),
  SelectContent: ({ children }: any) => (
    <div data-testid="select-content">{children}</div>
  ),
  SelectGroup: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children, value }: any) => (
    <div data-testid="select-item" data-value={value}>
      {children}
    </div>
  ),
  SelectTrigger: ({ children }: any) => (
    <div data-testid="select-trigger">{children}</div>
  ),
  SelectValue: () => null,
}));

vi.mock("@/components/ui/toggle-group", () => ({
  ToggleGroup: ({ children, value, onValueChange, ...props }: any) => {
    mockToggleOnValueChange.current = onValueChange;
    return (
      <div data-testid="toggle-group" data-value={value} {...props}>
        {children}
      </div>
    );
  },
  ToggleGroupItem: ({ children, value, ...props }: any) => (
    <button
      data-testid={`toggle-item-${value}`}
      data-value={value}
      onClick={() => mockToggleOnValueChange.current?.(value)}
      {...props}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/workspace/code-editor", () => ({
  CodeEditor: ({ value, readonly }: any) => (
    <div data-testid="code-editor" data-readonly={String(readonly)}>
      {value}
    </div>
  ),
}));

vi.mock("@/core/artifacts/hooks", () => ({
  useArtifactContent: (...args: any[]) => mockUseArtifactContent(...args),
}));

vi.mock("@/core/artifacts/preview", () => ({
  appendHtmlPreviewBaseHref: (c: string) => c,
  appendHtmlPreviewScrollRestoration: (c: string) => c,
  createHtmlPreviewScrollKey: (k: string) => `scroll-key:${k}`,
  getArtifactViewState: (...args: any[]) => mockGetArtifactViewState(...args),
  HTML_PREVIEW_SCROLL_MESSAGE_SOURCE: "ideer-artifact-preview-scroll",
}));

vi.mock("@/core/artifacts/utils", () => ({
  urlOfArtifact: (...args: any[]) => mockUrlOfArtifact(...args),
}));

vi.mock("@/core/clipboard", () => ({
  writeTextToClipboard: (...args: any[]) => mockWriteTextToClipboard(...args),
}));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      toolCalls: { skillInstallTooltip: "Install this skill" },
      common: {
        install: "Install",
        openInNewWindow: "Open in new window",
        download: "Download",
        close: "Close",
      },
      clipboard: {
        copyToClipboard: "Copy to clipboard",
        copiedToClipboard: "Copied to clipboard",
        failedToCopyToClipboard: "Failed to copy",
      },
    },
  }),
}));

vi.mock("@/core/messages/utils", () => ({
  findToolCallResult: (...args: any[]) => mockFindToolCallResult(...args),
}));

vi.mock("@/core/skills/api", () => ({
  installSkill: (...args: any[]) => mockInstallSkill(...args),
}));

vi.mock("@/core/streamdown", () => ({
  streamdownPlugins: { plugins: true },
}));

vi.mock("@/core/utils/files", () => ({
  checkCodeFile: (...args: any[]) => mockCheckCodeFile(...args),
  getFileName: (...args: any[]) => mockGetFileName(...args),
}));

vi.mock("@/env", () => ({
  env: { NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false" },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

vi.mock("@/components/workspace/citations/artifact-link", () => ({
  ArtifactLink: (props: any) => <a data-testid="artifact-link" {...props} />,
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({ children, content }: any) => (
    <div data-testid="tooltip" data-content={content}>
      {children}
    </div>
  ),
}));

const mockSetOpen = vi.fn();
const mockSelect = vi.fn();
let mockArtifacts = ["src/app.tsx", "src/utils.ts"];

vi.mock("@/components/workspace/artifacts/context", () => ({
  useArtifacts: () => ({
    artifacts: mockArtifacts,
    setOpen: mockSetOpen,
    select: mockSelect,
    selectedArtifact: "src/app.tsx",
    autoSelect: false,
    deselect: vi.fn(),
    open: true,
    autoOpen: false,
    setArtifacts: vi.fn(),
  }),
}));

vi.mock("@/components/workspace/artifacts/fault-tree-viewer", () => ({
  FaultTreeViewer: ({ content }: any) => (
    <div data-testid="fault-tree-viewer" data-content={content} />
  ),
}));

vi.mock("@/components/workspace/messages/context", () => ({
  useThread: (...args: any[]) => mockUseThread(...args),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import {
  ArtifactFileDetail,
  ArtifactFilePreview,
} from "@/components/workspace/artifacts/artifact-file-detail";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDetail(
  props: Partial<{
    filepath: string;
    threadId: string;
    className: string;
  }> = {},
) {
  return render(
    <ArtifactFileDetail
      filepath={props.filepath ?? "src/app.tsx"}
      threadId={props.threadId ?? "thread-1"}
      className={props.className}
    />,
  );
}

function renderPreview(
  props: Partial<{
    content: string;
    filepath: string;
    isFaultTreeFile: boolean;
    language: string;
    scrollKey: string;
    url: string;
  }> = {},
) {
  return render(
    <ArtifactFilePreview
      content={props.content ?? "preview content"}
      filepath={props.filepath ?? "src/app.tsx"}
      isFaultTreeFile={props.isFaultTreeFile ?? false}
      language={props.language ?? "markdown"}
      scrollKey={props.scrollKey ?? "scroll-key"}
      url={props.url}
    />,
  );
}

// ---------------------------------------------------------------------------
// Reset mocks before each test
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockToggleOnValueChange.current = null;
  mockArtifacts = ["src/app.tsx", "src/utils.ts"];

  mockUseArtifactContent.mockReturnValue({
    content: "test content",
    url: undefined,
    isLoading: false,
    error: null,
  });
  mockGetArtifactViewState.mockReturnValue({
    initialViewMode: "code" as const,
    canPreview: false,
  });
  mockCheckCodeFile.mockReturnValue({
    isCodeFile: true,
    language: "typescript",
  });
  mockGetFileName.mockImplementation(
    (path: string) => path.split("/").pop() || path,
  );
  mockUrlOfArtifact.mockReturnValue("http://mock/artifact");
  mockWriteTextToClipboard.mockResolvedValue(true);
  mockFindToolCallResult.mockReturnValue(undefined);
  mockInstallSkill.mockResolvedValue({
    success: true,
    skill_name: "",
    message: "Skill installed successfully",
  });
  mockUseThread.mockReturnValue({ thread: { messages: [] }, isMock: false });
});

afterEach(() => {
  cleanup();
});

// ===========================================================================
// ArtifactFileDetail
// ===========================================================================

describe("ArtifactFileDetail", () => {
  // -----------------------------------------------------------------------
  // Basic rendering
  // -----------------------------------------------------------------------

  describe("basic rendering", () => {
    test("renders the artifact container", () => {
      renderDetail();
      expect(screen.getByTestId("artifact")).toBeInTheDocument();
    });

    test("renders the artifact header", () => {
      renderDetail();
      expect(screen.getByTestId("artifact-header")).toBeInTheDocument();
    });

    test("renders the artifact content area", () => {
      renderDetail();
      expect(screen.getByTestId("artifact-content")).toBeInTheDocument();
    });

    test("applies custom className", () => {
      renderDetail({ className: "custom-class" });
      const artifact = screen.getByTestId("artifact");
      expect(artifact.className).toContain("custom-class");
    });

    test("passes no className when undefined", () => {
      renderDetail();
      const artifact = screen.getByTestId("artifact");
      expect(artifact.className).not.toContain("undefined");
    });
  });

  // -----------------------------------------------------------------------
  // File type detection and rendering
  // -----------------------------------------------------------------------

  describe("file type detection", () => {
    test("shows Select dropdown for regular (non-write) files", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("select")).toBeInTheDocument();
    });

    test("does not show Select dropdown for write-file paths", () => {
      renderDetail({ filepath: "write-file:/src/output.ts" });
      expect(screen.queryByTestId("select")).not.toBeInTheDocument();
    });

    test("shows filename text for write-file paths", () => {
      renderDetail({ filepath: "write-file:/src/output.ts" });
      expect(screen.getByText("output.ts")).toBeInTheDocument();
    });

    test("renders SelectItem for each artifact in the dropdown", () => {
      renderDetail({ filepath: "src/app.tsx" });
      const items = screen.getAllByTestId("select-item");
      expect(items).toHaveLength(2);
      expect(items[0]).toHaveTextContent("app.tsx");
      expect(items[1]).toHaveTextContent("utils.ts");
    });

    test("uses the correct filepath as Select value", () => {
      renderDetail({ filepath: "src/app.tsx" });
      const select = screen.getByTestId("select");
      expect(select).toHaveAttribute("data-value", "src/app.tsx");
    });

    test("shows code editor for code files in code view mode", () => {
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "typescript",
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    });

    test("shows iframe for non-code files", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
      renderDetail({ filepath: "image.png" });
      expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
      const iframe = document.querySelector("iframe");
      expect(iframe).toBeInTheDocument();
    });

    test("iframe gets correct src for non-code files", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
      mockUrlOfArtifact.mockReturnValue("http://mock/image.png");
      renderDetail({ filepath: "image.png" });
      const iframe = document.querySelector("iframe");
      expect(iframe).toHaveAttribute("src", "http://mock/image.png");
    });

    test("code editor receives correct value from useArtifactContent", () => {
      mockUseArtifactContent.mockReturnValue({
        content: "const x = 1;",
        url: undefined,
        isLoading: false,
        error: null,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("code-editor")).toHaveTextContent(
        "const x = 1;",
      );
    });

    test("code editor falls back to empty string when content is null", () => {
      mockUseArtifactContent.mockReturnValue({
        content: null,
        url: undefined,
        isLoading: false,
        error: null,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("code-editor")).toHaveTextContent("");
    });

    test("code editor falls back to empty string when content is undefined", () => {
      mockUseArtifactContent.mockReturnValue({
        content: undefined,
        url: undefined,
        isLoading: false,
        error: null,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("code-editor")).toHaveTextContent("");
    });

    test("code editor is readonly", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByTestId("code-editor")).toHaveAttribute(
        "data-readonly",
        "true",
      );
    });
  });

  // -----------------------------------------------------------------------
  // Skill file handling
  // -----------------------------------------------------------------------

  describe("skill file handling", () => {
    test("shows install button for .skill files", () => {
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      expect(screen.getByText("Install")).toBeInTheDocument();
    });

    test("does not show install button for non-skill files", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.queryByText("Install")).not.toBeInTheDocument();
    });

    test("install button is wrapped in tooltip with correct text", () => {
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      const tooltip = screen.getByTestId("tooltip");
      expect(tooltip).toHaveAttribute("data-content", "Install this skill");
    });

    test("does not show install button for write-file paths even with .skill extension", () => {
      renderDetail({ filepath: "write-file:/skills/my.skill" });
      expect(screen.queryByText("Install")).not.toBeInTheDocument();
    });

    test("calls installSkill when install button is clicked", async () => {
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      const installBtn = screen.getByText("Install").closest("button")!;
      await act(async () => {
        fireEvent.click(installBtn);
      });
      expect(mockInstallSkill).toHaveBeenCalledWith({
        thread_id: "thread-1",
        path: "skills/my-skill.skill",
      });
    });

    test("shows success toast after successful skill installation", async () => {
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      const installBtn = screen.getByText("Install").closest("button")!;
      await act(async () => {
        fireEvent.click(installBtn);
      });
      expect(mockToastSuccess).toHaveBeenCalledWith(
        "Skill installed successfully",
      );
    });

    test("shows error toast when skill installation returns failure", async () => {
      mockInstallSkill.mockResolvedValue({
        success: false,
        skill_name: "",
        message: "Skill already installed",
      });
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      const installBtn = screen.getByText("Install").closest("button")!;
      await act(async () => {
        fireEvent.click(installBtn);
      });
      expect(mockToastError).toHaveBeenCalledWith("Skill already installed");
    });

    test("shows default error toast when skill installation fails with no message", async () => {
      mockInstallSkill.mockResolvedValue({
        success: false,
        skill_name: "",
        message: undefined as any,
      });
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "skills/my-skill.skill" });
      const installBtn = screen.getByText("Install").closest("button")!;
      await act(async () => {
        fireEvent.click(installBtn);
      });
      expect(mockToastError).toHaveBeenCalledWith("Failed to install skill");
    });

    test("shows error toast when installSkill throws an exception", async () => {
      mockInstallSkill.mockRejectedValue(new Error("Network error"));
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      renderDetail({ filepath: "skills/my-skill.skill" });
      const installBtn = screen.getByText("Install").closest("button")!;
      await act(async () => {
        fireEvent.click(installBtn);
      });
      expect(mockToastError).toHaveBeenCalledWith("Failed to install skill");
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to install skill:",
        expect.any(Error),
      );
      consoleSpy.mockRestore();
    });
  });

  // -----------------------------------------------------------------------
  // View mode toggle (preview support)
  // -----------------------------------------------------------------------

  describe("view mode toggle", () => {
    test("shows toggle group when canPreview is true", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: true,
      });
      renderDetail({ filepath: "src/page.html" });
      expect(screen.getByTestId("toggle-group")).toBeInTheDocument();
    });

    test("does not show toggle group when canPreview is false", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: false,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.queryByTestId("toggle-group")).not.toBeInTheDocument();
    });

    test("has code and preview toggle items", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: true,
      });
      renderDetail({ filepath: "src/page.html" });
      expect(screen.getByTestId("toggle-item-code")).toBeInTheDocument();
      expect(screen.getByTestId("toggle-item-preview")).toBeInTheDocument();
    });

    test("toggle group defaults to the initial view mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: true,
      });
      renderDetail({ filepath: "src/page.html" });
      expect(screen.getByTestId("toggle-group")).toHaveAttribute(
        "data-value",
        "code",
      );
    });

    test("can set initial view mode to preview", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      renderDetail({ filepath: "src/page.html" });
      expect(screen.getByTestId("toggle-group")).toHaveAttribute(
        "data-value",
        "preview",
      );
    });

    test("switches to code view when code toggle is clicked", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      renderDetail({ filepath: "src/page.html" });
      fireEvent.click(screen.getByTestId("toggle-item-code"));
      expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    });

    test("switches to preview view when preview toggle is clicked", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      renderDetail({ filepath: "src/page.html" });
      fireEvent.click(screen.getByTestId("toggle-item-preview"));
      expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Preview content rendering
  // -----------------------------------------------------------------------

  describe("preview content rendering", () => {
    test("renders markdown preview in preview mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "README.md" });
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
      expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
    });

    test("renders HTML preview iframe in preview mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      renderDetail({ filepath: "src/page.html" });
      expect(document.querySelectorAll("iframe").length).toBeGreaterThan(0);
    });

    test("renders SVG preview image in preview mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "svg" });
      renderDetail({ filepath: "diagram.svg" });
      expect(document.querySelectorAll("img").length).toBeGreaterThan(0);
    });

    test("renders FaultTreeViewer for fault_tree.json in preview mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "json" });
      mockGetFileName.mockReturnValue("fault_tree.json");
      renderDetail({ filepath: "output/fault_tree.json" });
      expect(screen.getByTestId("fault-tree-viewer")).toBeInTheDocument();
    });

    test("does not show code editor in preview mode", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      renderDetail({ filepath: "src/page.html" });
      expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
    });

    test("shows code editor when toggling back to code mode from preview", () => {
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      mockCheckCodeFile.mockReturnValue({
        isCodeFile: true,
        language: "markdown",
      });
      renderDetail({ filepath: "README.md" });
      expect(screen.queryByTestId("code-editor")).not.toBeInTheDocument();
      fireEvent.click(screen.getByTestId("toggle-item-code"));
      expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Action buttons
  // -----------------------------------------------------------------------

  describe("action buttons", () => {
    test("renders close button", () => {
      renderDetail();
      expect(screen.getByText("Close")).toBeInTheDocument();
    });

    test("close button calls setOpen(false)", () => {
      renderDetail();
      fireEvent.click(screen.getByText("Close").closest("button")!);
      expect(mockSetOpen).toHaveBeenCalledWith(false);
    });

    test("renders open in new window button for non-write files", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByText("Open in new window")).toBeInTheDocument();
    });

    test("does not show open in new window button for write files", () => {
      renderDetail({ filepath: "write-file:/src/output.ts" });
      expect(screen.queryByText("Open in new window")).not.toBeInTheDocument();
    });

    test("open in new window calls window.open with correct URL", () => {
      mockUrlOfArtifact.mockReturnValue("http://mock/artifact/src/app.tsx");
      const mockOpen = vi.fn().mockReturnValue({ opener: null });
      vi.stubGlobal("open", mockOpen);
      renderDetail({ filepath: "src/app.tsx" });
      fireEvent.click(
        screen.getByText("Open in new window").closest("button")!,
      );
      expect(mockUrlOfArtifact).toHaveBeenCalledWith(
        expect.objectContaining({
          filepath: "src/app.tsx",
          threadId: "thread-1",
        }),
      );
      expect(mockOpen).toHaveBeenCalledWith(
        "http://mock/artifact/src/app.tsx",
        "_blank",
        "noopener,noreferrer",
      );
      vi.unstubAllGlobals();
    });

    test("render download button for non-write files", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByText("Download")).toBeInTheDocument();
    });

    test("does not show download button for write files", () => {
      renderDetail({ filepath: "write-file:/src/output.ts" });
      expect(screen.queryByText("Download")).not.toBeInTheDocument();
    });

    test("download button calls window.open with download flag", () => {
      mockUrlOfArtifact.mockReturnValue("http://mock/artifact?download=true");
      const mockOpen = vi.fn().mockReturnValue({ opener: null });
      vi.stubGlobal("open", mockOpen);
      renderDetail({ filepath: "src/app.tsx" });
      fireEvent.click(screen.getByText("Download").closest("button")!);
      expect(mockUrlOfArtifact).toHaveBeenCalledWith(
        expect.objectContaining({ download: true }),
      );
      expect(mockOpen).toHaveBeenCalled();
      vi.unstubAllGlobals();
    });

    test("renders copy to clipboard button for code files", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(screen.getByText("Copy to clipboard")).toBeInTheDocument();
    });

    test("copy button is disabled when content is empty", () => {
      mockUseArtifactContent.mockReturnValue({
        content: null,
        url: undefined,
        isLoading: false,
        error: null,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(
        screen.getByText("Copy to clipboard").closest("button")!,
      ).toBeDisabled();
    });

    test("copy button is enabled when content exists", () => {
      mockUseArtifactContent.mockReturnValue({
        content: "hello world",
        url: undefined,
        isLoading: false,
        error: null,
      });
      renderDetail({ filepath: "src/app.tsx" });
      expect(
        screen.getByText("Copy to clipboard").closest("button")!,
      ).not.toBeDisabled();
    });

    test("copy success shows success toast", async () => {
      mockWriteTextToClipboard.mockResolvedValue(true);
      renderDetail({ filepath: "src/app.tsx" });
      await act(async () => {
        fireEvent.click(
          screen.getByText("Copy to clipboard").closest("button")!,
        );
      });
      expect(mockWriteTextToClipboard).toHaveBeenCalled();
      expect(mockToastSuccess).toHaveBeenCalledWith("Copied to clipboard");
    });

    test("copy failure shows error toast", async () => {
      mockWriteTextToClipboard.mockResolvedValue(false);
      renderDetail({ filepath: "src/app.tsx" });
      await act(async () => {
        fireEvent.click(
          screen.getByText("Copy to clipboard").closest("button")!,
        );
      });
      expect(mockToastError).toHaveBeenCalledWith("Failed to copy");
    });

    test("copy exception shows error toast", async () => {
      mockWriteTextToClipboard.mockRejectedValue(new Error("Clipboard error"));
      renderDetail({ filepath: "src/app.tsx" });
      await act(async () => {
        fireEvent.click(
          screen.getByText("Copy to clipboard").closest("button")!,
        );
      });
      expect(mockToastError).toHaveBeenCalledWith("Failed to copy");
    });
  });

  // -----------------------------------------------------------------------
  // Write-file specific behavior
  // -----------------------------------------------------------------------

  describe("write-file behavior", () => {
    test("decodes filepath from write-file URL", () => {
      renderDetail({ filepath: "write-file:/src/output%20file.ts" });
      expect(mockGetFileName).toHaveBeenCalledWith("/src/output file.ts");
    });

    test("does not use useArtifactContent for write files (enabled is false)", () => {
      renderDetail({ filepath: "write-file:/src/output.ts" });
      expect(mockUseArtifactContent).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false }),
      );
    });

    test("uses useArtifactContent for regular code files (enabled is true)", () => {
      renderDetail({ filepath: "src/app.tsx" });
      expect(mockUseArtifactContent).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: true }),
      );
    });

    test("disables useArtifactContent for non-code regular files", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
      renderDetail({ filepath: "image.png" });
      expect(mockUseArtifactContent).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false }),
      );
    });

    test("calls findToolCallResult when write-file has tool_call_id", () => {
      mockFindToolCallResult.mockReturnValue("OK");
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      renderDetail({
        filepath: "write-file:/src/output.html?tool_call_id=tc-1",
      });
      expect(mockFindToolCallResult).toHaveBeenCalledWith("tc-1", []);
    });

    test("does not call findToolCallResult when write-file has no tool_call_id", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "code",
        canPreview: false,
      });
      renderDetail({ filepath: "write-file:/src/output.html" });
      expect(mockFindToolCallResult).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // SVG file handling
  // -----------------------------------------------------------------------

  describe("SVG file handling", () => {
    test("SVG file is detected as code with svg language", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "svg" });
      renderDetail({ filepath: "diagram.svg" });
      expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    });

    test("SVG file with preview shows toggle when canPreview is true", () => {
      mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "svg" });
      mockGetArtifactViewState.mockReturnValue({
        initialViewMode: "preview",
        canPreview: true,
      });
      renderDetail({ filepath: "diagram.svg" });
      expect(screen.getByTestId("toggle-group")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // isMock thread behavior
  // -----------------------------------------------------------------------

  describe("isMock thread", () => {
    test("passes isMock to urlOfArtifact for open in new window", () => {
      mockUseThread.mockReturnValue({ thread: { messages: [] }, isMock: true });
      const mockOpen = vi.fn().mockReturnValue({ opener: null });
      vi.stubGlobal("open", mockOpen);
      renderDetail({ filepath: "src/app.tsx" });
      fireEvent.click(
        screen.getByText("Open in new window").closest("button")!,
      );
      expect(mockUrlOfArtifact).toHaveBeenCalledWith(
        expect.objectContaining({ isMock: true }),
      );
      vi.unstubAllGlobals();
    });

    test("passes isMock to urlOfArtifact for download", () => {
      mockUseThread.mockReturnValue({ thread: { messages: [] }, isMock: true });
      const mockOpen = vi.fn().mockReturnValue({ opener: null });
      vi.stubGlobal("open", mockOpen);
      renderDetail({ filepath: "src/app.tsx" });
      fireEvent.click(screen.getByText("Download").closest("button")!);
      expect(mockUrlOfArtifact).toHaveBeenCalledWith(
        expect.objectContaining({ isMock: true }),
      );
      vi.unstubAllGlobals();
    });
  });
});

// ===========================================================================
// ArtifactFilePreview
// ===========================================================================

describe("ArtifactFilePreview", () => {
  // -----------------------------------------------------------------------
  // Markdown rendering
  // -----------------------------------------------------------------------

  describe("markdown rendering", () => {
    test("renders Streamdown component for markdown language", () => {
      renderPreview({ language: "markdown", content: "# Hello" });
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
    });

    test("passes content as children to Streamdown", () => {
      renderPreview({ language: "markdown", content: "# Hello World" });
      expect(screen.getByTestId("streamdown")).toHaveTextContent(
        "# Hello World",
      );
    });

    test("wraps content in a container div", () => {
      const { container } = renderPreview({
        language: "markdown",
        content: "test",
      });
      const wrapper = container.querySelector(".size-full.px-4");
      expect(wrapper).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // HTML rendering
  // -----------------------------------------------------------------------

  describe("HTML rendering", () => {
    test("renders iframe for HTML language", () => {
      renderPreview({ language: "html", content: "<html></html>" });
      expect(document.querySelectorAll("iframe").length).toBeGreaterThan(0);
    });

    test("HTML iframe has correct sandbox attribute", () => {
      renderPreview({ language: "html", content: "<html></html>" });
      const iframe = document.querySelector("iframe[title='Artifact preview']");
      expect(iframe).toBeInTheDocument();
      expect(iframe).toHaveAttribute("sandbox", "allow-scripts allow-forms");
    });

    test("HTML iframe has correct title", () => {
      renderPreview({ language: "html", content: "<html></html>" });
      expect(
        document.querySelector("iframe[title='Artifact preview']"),
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // SVG rendering
  // -----------------------------------------------------------------------

  describe("SVG rendering", () => {
    test("renders image element for SVG language", () => {
      renderPreview({ language: "svg", content: "<svg></svg>" });
      expect(document.querySelectorAll("img").length).toBeGreaterThan(0);
    });

    test("SVG preview has correct alt text from filepath", () => {
      renderPreview({
        language: "svg",
        content: "<svg></svg>",
        filepath: "diagram.svg",
      });
      expect(document.querySelector("img")).toHaveAttribute(
        "alt",
        "diagram.svg",
      );
    });

    test("SVG preview has fallback alt text when no filepath", () => {
      render(
        <ArtifactFilePreview
          content="<svg></svg>"
          language="svg"
          scrollKey="scroll-key"
        />,
      );
      expect(document.querySelector("img")).toHaveAttribute(
        "alt",
        "SVG artifact",
      );
    });

    test("SVG preview container has overflow-auto", () => {
      const { container } = renderPreview({
        language: "svg",
        content: "<svg></svg>",
      });
      expect(container.querySelector(".overflow-auto")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Fault tree rendering
  // -----------------------------------------------------------------------

  describe("fault tree rendering", () => {
    test("renders FaultTreeViewer for fault tree files", () => {
      renderPreview({ isFaultTreeFile: true, content: '{"nodes":[]}' });
      expect(screen.getByTestId("fault-tree-viewer")).toBeInTheDocument();
    });

    test("FaultTreeViewer receives content prop", () => {
      renderPreview({
        isFaultTreeFile: true,
        content: '{"nodes":[{"id":"1"}]}',
      });
      expect(screen.getByTestId("fault-tree-viewer")).toHaveAttribute(
        "data-content",
        '{"nodes":[{"id":"1"}]}',
      );
    });

    test("fault tree takes priority over markdown language", () => {
      renderPreview({
        isFaultTreeFile: true,
        language: "markdown",
        content: "{}",
      });
      expect(screen.getByTestId("fault-tree-viewer")).toBeInTheDocument();
      expect(screen.queryByTestId("streamdown")).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Unknown language returns null
  // -----------------------------------------------------------------------

  describe("unknown language", () => {
    test("returns null for unknown language", () => {
      const { container } = renderPreview({
        language: "python",
        content: "print('hi')",
      });
      expect(container.firstChild).toBeNull();
    });

    test("returns null for empty string language", () => {
      const { container } = renderPreview({ language: "", content: "test" });
      expect(container.firstChild).toBeNull();
    });
  });

  // -----------------------------------------------------------------------
  // Scroll message handling (HTML)
  // -----------------------------------------------------------------------

  describe("HTML scroll message handling", () => {
    test("listens for message events when language is html", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      expect(spy).toHaveBeenCalledWith("message", expect.any(Function));
      spy.mockRestore();
    });

    test("does not listen for message events when language is not html", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "markdown", content: "# Test" });
      const messageCalls = spy.mock.calls.filter((c) => c[0] === "message");
      expect(messageCalls).toHaveLength(0);
      spy.mockRestore();
    });

    test("cleans up message listener on unmount for html", () => {
      const spy = vi.spyOn(window, "removeEventListener");
      const { unmount } = renderPreview({
        language: "html",
        content: "<html></html>",
      });
      unmount();
      expect(spy).toHaveBeenCalledWith("message", expect.any(Function));
      spy.mockRestore();
    });
  });

  // -----------------------------------------------------------------------
  // HTML blob URL management
  // -----------------------------------------------------------------------

  describe("HTML blob URL management", () => {
    test("creates blob URL for html content", () => {
      const spy = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:mock-url");
      renderPreview({ language: "html", content: "<html></html>" });
      expect(spy).toHaveBeenCalled();
      spy.mockRestore();
    });

    test("revokes blob URL on cleanup", () => {
      const createSpy = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:mock-url");
      const revokeSpy = vi
        .spyOn(URL, "revokeObjectURL")
        .mockImplementation(() => {});
      const { unmount } = renderPreview({
        language: "html",
        content: "<html></html>",
      });
      unmount();
      expect(revokeSpy).toHaveBeenCalledWith("blob:mock-url");
      createSpy.mockRestore();
      revokeSpy.mockRestore();
    });
  });

  // -----------------------------------------------------------------------
  // SVG blob URL management
  // -----------------------------------------------------------------------

  describe("SVG blob URL management", () => {
    test("creates blob URL for svg content", () => {
      const spy = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:svg-url");
      renderPreview({ language: "svg", content: "<svg></svg>" });
      expect(spy).toHaveBeenCalled();
      spy.mockRestore();
    });

    test("revokes SVG blob URL on cleanup", () => {
      const createSpy = vi
        .spyOn(URL, "createObjectURL")
        .mockReturnValue("blob:svg-url");
      const revokeSpy = vi
        .spyOn(URL, "revokeObjectURL")
        .mockImplementation(() => {});
      const { unmount } = renderPreview({
        language: "svg",
        content: "<svg></svg>",
      });
      unmount();
      expect(revokeSpy).toHaveBeenCalledWith("blob:svg-url");
      createSpy.mockRestore();
      revokeSpy.mockRestore();
    });
  });

  // -----------------------------------------------------------------------
  // Props handling
  // -----------------------------------------------------------------------

  describe("props handling", () => {
    test("handles custom scrollKey", () => {
      renderPreview({
        language: "html",
        content: "<html></html>",
        scrollKey: "my-custom-key",
      });
      expect(document.querySelector("iframe")).toBeInTheDocument();
    });

    test("handles undefined url prop", () => {
      renderPreview({
        language: "html",
        content: "<html></html>",
        url: undefined,
      });
      expect(document.querySelector("iframe")).toBeInTheDocument();
    });

    test("handles empty content", () => {
      renderPreview({ language: "markdown", content: "" });
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
    });

    test("handles undefined content gracefully", () => {
      renderPreview({ language: "markdown", content: undefined as any });
      expect(screen.getByTestId("streamdown")).toBeInTheDocument();
    });
  });
});

// ===========================================================================
// Internal helper behavior (tested indirectly through components)
// ===========================================================================

describe("internal helper behavior", () => {
  // -----------------------------------------------------------------------
  // isArtifactScrollMessage
  // -----------------------------------------------------------------------

  describe("isArtifactScrollMessage", () => {
    test("HTML preview handles save message with valid coordinates", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      expect(handler).toBeDefined();
      if (handler) {
        const iframe = document.querySelector("iframe");
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "scroll-key:scroll-key",
            type: "save",
            x: 100,
            y: 200,
          },
        });
        Object.defineProperty(event, "source", {
          value: iframe?.contentWindow,
          writable: false,
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("ignores messages from wrong source", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "wrong-source",
            key: "scroll-key:scroll-key",
            type: "save",
            x: 0,
            y: 0,
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("ignores messages with wrong key", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "wrong-key",
            type: "save",
            x: 0,
            y: 0,
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("handles restore-request message type", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "scroll-key:scroll-key",
            type: "restore-request",
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("ignores non-object message data", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        handler(new MessageEvent("message", { data: null }));
        handler(new MessageEvent("message", { data: "hello" }));
        handler(new MessageEvent("message", { data: 42 }));
      }
      spy.mockRestore();
    });

    test("handles save message with non-numeric coordinates", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "scroll-key:scroll-key",
            type: "save",
            x: "not-a-number",
            y: "also-not",
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("handles save message with Infinity coordinates", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "scroll-key:scroll-key",
            type: "save",
            x: Infinity,
            y: -Infinity,
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });

    test("handles save message with NaN coordinates", () => {
      const spy = vi.spyOn(window, "addEventListener");
      renderPreview({ language: "html", content: "<html></html>" });
      const handler = spy.mock.calls.find((c) => c[0] === "message")?.[1] as
        | EventListener
        | undefined;
      if (handler) {
        const event = new MessageEvent("message", {
          data: {
            source: "ideer-artifact-preview-scroll",
            key: "scroll-key:scroll-key",
            type: "save",
            x: NaN,
            y: NaN,
          },
        });
        handler(event);
      }
      spy.mockRestore();
    });
  });
});

// ===========================================================================
// Write-file with tool result states
// ===========================================================================

describe("write-file with tool result states", () => {
  test("write-file with OK tool result allows preview", () => {
    mockFindToolCallResult.mockReturnValue("OK");
    mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "preview",
      canPreview: true,
    });
    renderDetail({ filepath: "write-file:/src/output.html?tool_call_id=tc-1" });
    expect(screen.getByTestId("toggle-group")).toBeInTheDocument();
  });

  test("write-file with error tool result shows code view", () => {
    mockFindToolCallResult.mockReturnValue("Error: permission denied");
    mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });
    renderDetail({ filepath: "write-file:/src/output.html?tool_call_id=tc-1" });
    expect(screen.queryByTestId("toggle-group")).not.toBeInTheDocument();
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("write-file with no tool_call_id param has no toolResult", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "preview",
      canPreview: true,
    });
    renderDetail({ filepath: "write-file:/src/output.html" });
    expect(mockFindToolCallResult).not.toHaveBeenCalled();
  });

  test("write-file with tool_call_id calls findToolCallResult", () => {
    mockFindToolCallResult.mockReturnValue("OK");
    mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "html" });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });
    renderDetail({
      filepath: "write-file:/src/output.html?tool_call_id=tc-42",
    });
    expect(mockFindToolCallResult).toHaveBeenCalledWith("tc-42", []);
  });
});

// ===========================================================================
// Multiple artifact dropdown
// ===========================================================================

describe("multiple artifact dropdown", () => {
  test("renders all artifacts in dropdown", () => {
    mockArtifacts = ["a.ts", "b.ts", "c.ts"];
    renderDetail({ filepath: "a.ts" });
    const items = screen.getAllByTestId("select-item");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("a.ts");
    expect(items[1]).toHaveTextContent("b.ts");
    expect(items[2]).toHaveTextContent("c.ts");
  });

  test("renders empty dropdown when no artifacts", () => {
    mockArtifacts = [];
    renderDetail({ filepath: "src/app.tsx" });
    expect(screen.queryAllByTestId("select-item")).toHaveLength(0);
  });

  test("renders dropdown with single artifact", () => {
    mockArtifacts = ["only-file.ts"];
    renderDetail({ filepath: "only-file.ts" });
    const items = screen.getAllByTestId("select-item");
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent("only-file.ts");
  });
});

// ===========================================================================
// SVG file detection from filepath (lines 87-89, 100-102)
// ===========================================================================

describe("SVG file detection from filepath", () => {
  test("detects SVG from .svg extension without calling checkCodeFile", () => {
    renderDetail({ filepath: "diagram.svg" });
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
  });

  test("detects SVG case-insensitively (.SVG)", () => {
    renderDetail({ filepath: "Diagram.SVG" });
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
  });

  test("detects SVG in nested paths", () => {
    renderDetail({ filepath: "src/assets/icon.svg" });
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
  });

  test("SVG detection overrides checkCodeFile mock for language", () => {
    // Even if checkCodeFile would return something else, isSvgFile takes precedence
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "chart.svg" });
    // Should still show code editor because isSvgFile forces isCodeFile: true
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// Skill file language detection (lines 96-99)
// ===========================================================================

describe("Skill file language detection", () => {
  test(".skill files are treated as markdown without calling checkCodeFile", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "skills/my-skill.skill" });
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
  });

  test(".skill files are detected as code files", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "skills/my-skill.skill" });
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("skill file detection overrides checkCodeFile mock", () => {
    // Even if checkCodeFile would say it's not a code file, skill detection overrides
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "skills/custom.skill" });
    expect(mockCheckCodeFile).not.toHaveBeenCalled();
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });
});

// ===========================================================================
// Write-file language detection (lines 91-95)
// ===========================================================================

describe("Write-file language detection", () => {
  test("write-file always sets isCodeFile to true even when checkCodeFile returns false", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "write-file:/src/file.xyz" });
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("write-file uses language from checkCodeFile", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: true, language: "python" });
    renderDetail({ filepath: "write-file:/src/script.py" });
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("write-file falls back to text language when checkCodeFile returns null language", () => {
    mockCheckCodeFile.mockReturnValue({ isCodeFile: false, language: null });
    renderDetail({ filepath: "write-file:/src/file.unknown" });
    expect(screen.getByTestId("code-editor")).toBeInTheDocument();
  });

  test("write-file calls checkCodeFile with decoded filepath", () => {
    mockCheckCodeFile.mockReturnValue({
      isCodeFile: true,
      language: "typescript",
    });
    renderDetail({ filepath: "write-file:/src/output.ts" });
    expect(mockCheckCodeFile).toHaveBeenCalledWith("/src/output.ts");
  });
});

// ===========================================================================
// ArtifactFilePreview scroll reset (lines 361-363)
// ===========================================================================

describe("ArtifactFilePreview scroll reset", () => {
  test("scrollPositionRef resets when scrollKey changes", () => {
    const { rerender } = render(
      <ArtifactFilePreview
        content="<html></html>"
        language="html"
        scrollKey="key-1"
      />,
    );
    expect(document.querySelector("iframe")).toBeInTheDocument();

    // Change scrollKey - the useEffect at lines 361-363 should fire, resetting scrollPositionRef
    rerender(
      <ArtifactFilePreview
        content="<html></html>"
        language="html"
        scrollKey="key-2"
      />,
    );
    expect(document.querySelector("iframe")).toBeInTheDocument();
  });

  test("scrollPositionRef resets on initial render", () => {
    // The useEffect at lines 361-363 runs on mount too, setting scrollPositionRef to {x:0, y:0}
    render(
      <ArtifactFilePreview
        content="<html></html>"
        language="html"
        scrollKey="initial-key"
      />,
    );
    expect(document.querySelector("iframe")).toBeInTheDocument();
  });

  test("scroll reset effect does not run for non-html languages", () => {
    // The scrollMessageKey useMemo still runs, and the scrollPositionRef effect runs
    // but the message listener effect (lines 365-402) should NOT run for non-html
    const { rerender } = render(
      <ArtifactFilePreview
        content="# Test"
        language="markdown"
        scrollKey="key-1"
      />,
    );
    rerender(
      <ArtifactFilePreview
        content="# Test"
        language="markdown"
        scrollKey="key-2"
      />,
    );
    expect(screen.getByTestId("streamdown")).toBeInTheDocument();
  });
});

// ===========================================================================
// useThrottledValue hook behavior (tested via write-file rendering)
// ===========================================================================

describe("useThrottledValue hook behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("immediately flushes on first render when lastFlushAtRef is 0 (line 546)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "initial",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });
    renderDetail({ filepath: "write-file:/src/file.ts" });
    expect(screen.getByTestId("code-editor")).toHaveTextContent("initial");
  });

  test("sets timeout to flush throttled value after interval (lines 560-564)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/file.ts"
        threadId="thread-1"
      />,
    );
    expect(screen.getByTestId("code-editor")).toHaveTextContent("v1");

    // Update content within the throttle interval
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    // Advance time to fire the pending timeout
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByTestId("code-editor")).toHaveTextContent("v2");
  });

  test("returns early when timeout already exists (line 557)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/file.ts"
        threadId="thread-1"
      />,
    );

    // First update within interval - sets a timeout
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    // Second update while timeout is pending - should return early at line 557
    mockUseArtifactContent.mockReturnValue({
      content: "v3",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    // Advance time to fire the pending timeout
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    // Should show the latest value from the timeout callback
    expect(screen.getByTestId("code-editor")).toHaveTextContent("v3");
  });

  test("elapsed >= intervalMs flushes immediately (lines 546-554)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/file.ts"
        threadId="thread-1"
      />,
    );

    // Advance time past the throttle interval
    act(() => {
      vi.advanceTimersByTime(3500);
    });

    // Now update - elapsed >= intervalMs, should flush immediately
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    expect(screen.getByTestId("code-editor")).toHaveTextContent("v2");
  });

  test("resetKey change flushes value immediately (lines 520-532)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/a.ts"
        threadId="thread-1"
      />,
    );
    expect(screen.getByTestId("code-editor")).toHaveTextContent("v1");

    // Change the resetKey (filepath) - this should flush immediately
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    rerender(
      <ArtifactFileDetail
        filepath="write-file:/src/b.ts"
        threadId="thread-1"
      />,
    );

    expect(screen.getByTestId("code-editor")).toHaveTextContent("v2");
  });

  test("resetKey change cancels pending timeout (lines 525-528)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/a.ts"
        threadId="thread-1"
      />,
    );

    // Update within interval - sets a timeout
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/a.ts"
          threadId="thread-1"
        />,
      );
    });

    // Change resetKey - should cancel the timeout and flush immediately
    mockUseArtifactContent.mockReturnValue({
      content: "v3",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/b.ts"
          threadId="thread-1"
        />,
      );
    });

    expect(screen.getByTestId("code-editor")).toHaveTextContent("v3");

    // Advance timers - the old timeout should have been cancelled
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Value should still be v3 (the timeout was cancelled)
    expect(screen.getByTestId("code-editor")).toHaveTextContent("v3");
  });

  test("cleanup clears timeout on unmount (lines 567-573)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender, unmount } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/file.ts"
        threadId="thread-1"
      />,
    );

    // Trigger a throttle timeout
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    // Unmount while timeout is pending - cleanup effect should clear it
    unmount();

    // Advance timers - should not throw because timeout was cleared
    act(() => {
      vi.advanceTimersByTime(5000);
    });
  });

  test("non-write-file uses intervalMs=0 for immediate flush (lines 534-542)", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "test",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });
    renderDetail({ filepath: "src/app.tsx" });
    // Non-write-file: intervalMs=0, so value is returned immediately via the intervalMs<=0 branch
    expect(screen.getByTestId("code-editor")).toHaveTextContent("test");
  });

  test("multiple rapid updates within interval coalesce to latest value", () => {
    mockUseArtifactContent.mockReturnValue({
      content: "v1",
      url: undefined,
      isLoading: false,
      error: null,
    });
    mockGetArtifactViewState.mockReturnValue({
      initialViewMode: "code",
      canPreview: false,
    });

    const { rerender } = render(
      <ArtifactFileDetail
        filepath="write-file:/src/file.ts"
        threadId="thread-1"
      />,
    );

    // Multiple rapid updates
    mockUseArtifactContent.mockReturnValue({
      content: "v2",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    mockUseArtifactContent.mockReturnValue({
      content: "v3",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    mockUseArtifactContent.mockReturnValue({
      content: "v4",
      url: undefined,
      isLoading: false,
      error: null,
    });
    act(() => {
      rerender(
        <ArtifactFileDetail
          filepath="write-file:/src/file.ts"
          threadId="thread-1"
        />,
      );
    });

    // Advance past the interval
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    // Should show the latest value
    expect(screen.getByTestId("code-editor")).toHaveTextContent("v4");
  });
});
