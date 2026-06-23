import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockWriteTextToClipboard = vi.fn();
vi.mock("@/core/clipboard", () => ({
  writeTextToClipboard: (...args: unknown[]) =>
    mockWriteTextToClipboard(...args),
}));

const mockToast = { error: vi.fn() };
vi.mock("sonner", () => ({ toast: mockToast }));

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      clipboard: {
        copyToClipboard: "Copy to clipboard",
        failedToCopyToClipboard: "Failed to copy",
      },
    },
  }),
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: string;
  }) => (
    <div data-testid="tooltip" title={content}>
      {children}
    </div>
  ),
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

let CopyButton: typeof import("@/components/workspace/copy-button").CopyButton;

beforeEach(async () => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const mod = await import("@/components/workspace/copy-button");
  CopyButton = mod.CopyButton;
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("CopyButton", () => {
  test("renders the copy icon by default", () => {
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="hello" />);
    const button = screen.getByRole("button");
    expect(button).toBeInTheDocument();
  });

  test("calls writeTextToClipboard on click", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="text to copy" />);

    await user.click(screen.getByRole("button"));
    expect(mockWriteTextToClipboard).toHaveBeenCalledWith("text to copy");
  });

  test("shows check icon after successful copy", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="hello" />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      const checkIcon = document.querySelector(".text-green-500");
      expect(checkIcon).toBeInTheDocument();
    });
  });

  test("reverts to copy icon after 2 seconds", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="hello" />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(document.querySelector(".text-green-500")).toBeInTheDocument();
    });

    vi.advanceTimersByTime(2000);

    await waitFor(() => {
      expect(document.querySelector(".text-green-500")).not.toBeInTheDocument();
    });
  });

  test("shows toast error when clipboard write fails", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockResolvedValue(false);
    render(<CopyButton clipboardData="hello" />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith("Failed to copy");
    });
  });

  test("shows toast error when clipboard write throws", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockRejectedValue(new Error("network error"));
    render(<CopyButton clipboardData="hello" />);

    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith("Failed to copy");
    });
  });

  test("passes additional props to Button", () => {
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="hello" className="my-class" disabled />);
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute(
      "class",
      expect.stringContaining("my-class"),
    );
    expect(button).toBeDisabled();
  });

  test("wraps content in Tooltip with copy text", () => {
    mockWriteTextToClipboard.mockResolvedValue(true);
    render(<CopyButton clipboardData="hello" />);
    const tooltip = screen.getByTestId("tooltip");
    expect(tooltip).toHaveAttribute("title", "Copy to clipboard");
  });

  test("uses correct clipboardData on each render", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockWriteTextToClipboard.mockResolvedValue(true);
    const { rerender } = render(<CopyButton clipboardData="first" />);

    await user.click(screen.getByRole("button"));
    expect(mockWriteTextToClipboard).toHaveBeenCalledWith("first");

    rerender(<CopyButton clipboardData="second" />);
    await user.click(screen.getByRole("button"));
    expect(mockWriteTextToClipboard).toHaveBeenCalledWith("second");
  });
});
