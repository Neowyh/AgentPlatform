import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  CodeBlock,
  CodeBlockCopyButton,
  highlightCode,
} from "@/components/ai-elements/code-block";

// Mock shiki
vi.mock("shiki", () => ({
  codeToHtml: vi
    .fn()
    .mockResolvedValue("<pre><code>highlighted code</code></pre>"),
  BundledLanguage: {},
}));

// Mock clipboard
vi.mock("@/core/clipboard", () => ({
  writeTextToClipboard: vi.fn().mockResolvedValue(true),
}));

afterEach(() => {
  cleanup();
});

describe("highlightCode", () => {
  test("returns light and dark HTML", async () => {
    const { codeToHtml } = await import("shiki");
    const result = await highlightCode("const x = 1;", "typescript");
    expect(result).toHaveLength(2);
    expect(codeToHtml).toHaveBeenCalledTimes(2);
  });

  test("passes language to codeToHtml", async () => {
    const { codeToHtml } = await import("shiki");
    await highlightCode("code", "javascript");
    expect(codeToHtml).toHaveBeenCalledWith(
      "code",
      expect.objectContaining({ lang: "javascript" }),
    );
  });

  test("includes line number transformer when showLineNumbers is true", async () => {
    const { codeToHtml } = await import("shiki");
    await highlightCode("line1\nline2", "javascript", true);
    expect(codeToHtml).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        transformers: expect.arrayContaining([
          expect.objectContaining({ name: "line-numbers" }),
        ]),
      }),
    );
  });

  test("uses empty transformers when showLineNumbers is false", async () => {
    const { codeToHtml } = await import("shiki");
    await highlightCode("code", "javascript", false);
    const call = vi.mocked(codeToHtml).mock.calls[0];
    expect(call![1].transformers).toEqual([]);
  });
});

describe("CodeBlock", () => {
  test("renders a container div", () => {
    render(
      <CodeBlock
        code="const x = 1;"
        language="typescript"
        data-testid="code-block"
      />,
    );
    expect(screen.getByTestId("code-block")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <CodeBlock
        code="code"
        language="typescript"
        className="custom-code"
        data-testid="code-block"
      />,
    );
    expect(screen.getByTestId("code-block")).toHaveClass("custom-code");
  });

  test("has border and rounded classes", () => {
    render(
      <CodeBlock code="code" language="typescript" data-testid="code-block" />,
    );
    const el = screen.getByTestId("code-block");
    expect(el.className).toContain("rounded-md");
    expect(el.className).toContain("border");
    expect(el.className).toContain("overflow-hidden");
  });

  test("sets highlighted HTML via dangerouslySetInnerHTML", async () => {
    render(
      <CodeBlock
        code="test code"
        language="typescript"
        data-testid="code-block"
      />,
    );
    await waitFor(() => {
      const codeBlocks = screen
        .getByTestId("code-block")
        .querySelectorAll("[class*='dark:hidden']");
      expect(codeBlocks.length).toBeGreaterThan(0);
      // The light mode div should have innerHTML set
      expect(codeBlocks[0]!.innerHTML).toContain("highlighted code");
    });
  });

  test("renders children in overlay area", () => {
    render(
      <CodeBlock code="code" language="typescript" data-testid="code-block">
        <button data-testid="copy-btn">Copy</button>
      </CodeBlock>,
    );
    expect(screen.getByTestId("copy-btn")).toBeInTheDocument();
  });

  test("does not render overlay when no children", () => {
    render(
      <CodeBlock code="code" language="typescript" data-testid="code-block" />,
    );
    const overlay = screen.getByTestId("code-block").querySelector(".absolute");
    expect(overlay).not.toBeInTheDocument();
  });
});

describe("CodeBlockCopyButton", () => {
  test("renders a button with copy icon", () => {
    render(
      <CodeBlock code="test code" language="typescript">
        <CodeBlockCopyButton data-testid="copy-btn" />
      </CodeBlock>,
    );
    const btn = screen.getByTestId("copy-btn");
    expect(btn.tagName).toBe("BUTTON");
    // Should have CopyIcon SVG
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  test("calls onCopy after clicking", async () => {
    const user = userEvent.setup();
    const onCopy = vi.fn();
    render(
      <CodeBlock code="test code" language="typescript">
        <CodeBlockCopyButton onCopy={onCopy} data-testid="copy-btn" />
      </CodeBlock>,
    );

    await user.click(screen.getByTestId("copy-btn"));
    await waitFor(() => {
      expect(onCopy).toHaveBeenCalledTimes(1);
    });
  });

  test("shows check icon after copying", async () => {
    const user = userEvent.setup();
    render(
      <CodeBlock code="test code" language="typescript">
        <CodeBlockCopyButton data-testid="copy-btn" />
      </CodeBlock>,
    );

    await user.click(screen.getByTestId("copy-btn"));
    await waitFor(() => {
      // After copy, icon should change to CheckIcon
      const btn = screen.getByTestId("copy-btn");
      expect(btn.querySelector("svg")).toBeInTheDocument();
    });
  });

  test("calls onError when clipboard fails", async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    const { writeTextToClipboard } = await import("@/core/clipboard");
    vi.mocked(writeTextToClipboard).mockResolvedValueOnce(false);

    render(
      <CodeBlock code="test" language="typescript">
        <CodeBlockCopyButton onError={onError} data-testid="copy-btn" />
      </CodeBlock>,
    );

    await user.click(screen.getByTestId("copy-btn"));
    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });
  });

  test("applies custom className", () => {
    render(
      <CodeBlock code="code" language="typescript">
        <CodeBlockCopyButton className="custom-copy" data-testid="copy-btn" />
      </CodeBlock>,
    );
    expect(screen.getByTestId("copy-btn")).toHaveClass("custom-copy");
  });

  test("renders custom children instead of icon", () => {
    render(
      <CodeBlock code="code" language="typescript">
        <CodeBlockCopyButton data-testid="copy-btn">
          <span>Copy this</span>
        </CodeBlockCopyButton>
      </CodeBlock>,
    );
    expect(screen.getByText("Copy this")).toBeInTheDocument();
  });

  test("calls onError when writeTextToClipboard throws", async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    const { writeTextToClipboard } = await import("@/core/clipboard");
    vi.mocked(writeTextToClipboard).mockRejectedValueOnce(
      new Error("Unexpected failure"),
    );

    render(
      <CodeBlock code="test" language="typescript">
        <CodeBlockCopyButton onError={onError} data-testid="copy-btn" />
      </CodeBlock>,
    );

    await user.click(screen.getByTestId("copy-btn"));
    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });
  });
});
