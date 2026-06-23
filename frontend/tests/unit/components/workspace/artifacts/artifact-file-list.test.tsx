import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      common: {
        install: "Install",
        download: "Download",
      },
    },
    changeLocale: vi.fn(),
  }),
}));

const mockSelect = vi.fn();
const mockSetOpen = vi.fn();
vi.mock("@/components/workspace/artifacts/context", () => ({
  useArtifacts: () => ({
    select: mockSelect,
    setOpen: mockSetOpen,
  }),
}));

const mockInstallSkill = vi.fn();
vi.mock("@/core/skills/api", () => ({
  installSkill: (...args: unknown[]) => mockInstallSkill(...args),
}));

vi.mock("@/core/artifacts/utils", () => ({
  urlOfArtifact: ({
    filepath,
    threadId,
    download,
  }: {
    filepath: string;
    threadId: string;
    download?: boolean;
  }) => `/artifacts/${threadId}/${filepath}${download ? "?download=true" : ""}`,
}));

vi.mock("@/core/utils/files", () => ({
  getFileExtensionDisplayName: (file: string) => {
    const ext = file.split(".").pop() ?? "";
    return ext.toUpperCase();
  },
  getFileIcon: (file: string, className: string) => (
    <span data-testid="file-icon" className={className}>
      icon
    </span>
  ),
  getFileName: (file: string) => file.split("/").pop() ?? file,
}));

const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let ArtifactFileList: typeof import("@/components/workspace/artifacts/artifact-file-list").ArtifactFileList;

beforeEach(async () => {
  vi.clearAllMocks();
  const mod =
    await import("@/components/workspace/artifacts/artifact-file-list");
  ArtifactFileList = mod.ArtifactFileList;
});

afterEach(() => {
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ArtifactFileList", () => {
  test("renders file cards for each file", () => {
    render(
      <ArtifactFileList files={["report.pdf", "data.csv"]} threadId="t-1" />,
    );
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getByText("data.csv")).toBeInTheDocument();
  });

  test("clicking a file card calls select and setOpen", () => {
    render(<ArtifactFileList files={["file.txt"]} threadId="t-1" />);
    fireEvent.click(screen.getByText("file.txt"));
    expect(mockSelect).toHaveBeenCalledWith("file.txt");
    expect(mockSetOpen).toHaveBeenCalledWith(true);
  });

  test("renders download links for each file", () => {
    render(<ArtifactFileList files={["doc.pdf"]} threadId="t-1" />);
    const downloadLinks = screen.getAllByText("Download");
    expect(downloadLinks.length).toBeGreaterThan(0);
  });

  test("does not render install button for non-.skill files", () => {
    render(<ArtifactFileList files={["doc.pdf"]} threadId="t-1" />);
    expect(screen.queryByText("Install")).not.toBeInTheDocument();
  });

  test("renders install button for .skill files", () => {
    render(<ArtifactFileList files={["my-skill.skill"]} threadId="t-1" />);
    expect(screen.getByText("Install")).toBeInTheDocument();
  });

  test("install button calls installSkill API", async () => {
    mockInstallSkill.mockResolvedValue({
      success: true,
      message: "Installed!",
    });

    render(<ArtifactFileList files={["test.skill"]} threadId="t-1" />);

    fireEvent.click(screen.getByText("Install"));

    await waitFor(() => {
      expect(mockInstallSkill).toHaveBeenCalledWith({
        thread_id: "t-1",
        path: "test.skill",
      });
    });
  });

  test("install success shows toast", async () => {
    mockInstallSkill.mockResolvedValue({
      success: true,
      message: "Skill installed",
    });

    render(<ArtifactFileList files={["test.skill"]} threadId="t-1" />);
    fireEvent.click(screen.getByText("Install"));

    await waitFor(() => {
      expect(mockToastSuccess).toHaveBeenCalledWith("Skill installed");
    });
  });

  test("install failure shows error toast", async () => {
    mockInstallSkill.mockResolvedValue({
      success: false,
      message: "Install failed",
    });

    render(<ArtifactFileList files={["test.skill"]} threadId="t-1" />);
    fireEvent.click(screen.getByText("Install"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Install failed");
    });
  });

  test("install API error shows error toast", async () => {
    mockInstallSkill.mockRejectedValue(new Error("Network error"));

    render(<ArtifactFileList files={["test.skill"]} threadId="t-1" />);
    fireEvent.click(screen.getByText("Install"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith("Failed to install skill");
    });
  });

  test("renders empty list when files is empty", () => {
    const { container } = render(
      <ArtifactFileList files={[]} threadId="t-1" />,
    );
    const list = container.querySelector("ul");
    expect(list).toBeInTheDocument();
    expect(list?.children.length).toBe(0);
  });

  test("applies custom className", () => {
    const { container } = render(
      <ArtifactFileList
        files={["f.txt"]}
        threadId="t-1"
        className="custom-list"
      />,
    );
    expect(container.firstElementChild).toHaveClass("custom-list");
  });

  test("download link has correct href", () => {
    render(<ArtifactFileList files={["doc.pdf"]} threadId="t-1" />);
    const link = screen.getByText("Download").closest("a");
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("download=true"),
    );
  });

  test("renders file extension badge", () => {
    render(<ArtifactFileList files={["report.pdf"]} threadId="t-1" />);
    expect(screen.getByText("PDF file")).toBeInTheDocument();
  });

  test("renders file icon for each file", () => {
    render(<ArtifactFileList files={["a.txt", "b.csv"]} threadId="t-1" />);
    const icons = screen.getAllByTestId("file-icon");
    expect(icons.length).toBe(2);
  });

  test("download link click stops propagation to prevent card selection", () => {
    render(<ArtifactFileList files={["doc.pdf"]} threadId="t-1" />);

    const downloadLink = screen.getByText("Download").closest("a")!;
    const clickEvent = new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
    });
    const stopPropagationSpy = vi.spyOn(clickEvent, "stopPropagation");

    downloadLink.dispatchEvent(clickEvent);

    expect(stopPropagationSpy).toHaveBeenCalled();
    // Card click handler (selectArtifact/setOpen) should NOT be called
    // because the download link click was stopped
  });
});
