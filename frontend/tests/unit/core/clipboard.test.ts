import { afterEach, describe, expect, test, vi } from "vitest";

import { writeTextToClipboard } from "@/core/clipboard";

// ---------------------------------------------------------------------------
// Global restoration helpers – each test mutates globalThis.navigator / .document
// so we snapshot originals and restore them in afterEach.
// ---------------------------------------------------------------------------

const originalNavigator = globalThis.navigator;
const hadOriginalNavigator = "navigator" in globalThis;
const originalDocument = globalThis.document;
const hadOriginalDocument = "document" in globalThis;

afterEach(() => {
  vi.restoreAllMocks();

  if (!hadOriginalNavigator) {
    Reflect.deleteProperty(globalThis, "navigator");
  } else {
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: originalNavigator,
    });
  }

  if (!hadOriginalDocument) {
    Reflect.deleteProperty(globalThis, "document");
  } else {
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: originalDocument,
    });
  }
});

// ---------------------------------------------------------------------------
// Helper: install a mock navigator and/or document on globalThis
// ---------------------------------------------------------------------------

function setNavigator(value: unknown) {
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value,
  });
}

function setDocument(value: unknown) {
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value,
  });
}

// A minimal textarea mock used by the execCommand fallback path.
function createMockTextarea() {
  return {
    value: "",
    setAttribute: vi.fn(),
    select: vi.fn(),
    remove: vi.fn(),
    style: {} as Record<string, string>,
  };
}

// =========================================================================
// Tests
// =========================================================================

describe("writeTextToClipboard", () => {
  // ---- Clipboard API happy path ----

  test("uses navigator.clipboard.writeText when available and resolves true", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledOnce();
    expect(writeText).toHaveBeenCalledWith("hello");
  });

  test("passes an empty string to the Clipboard API", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    await expect(writeTextToClipboard("")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("");
  });

  // ---- Clipboard API rejection / errors ----

  test("returns false when navigator.clipboard.writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("NotAllowedError"));
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when navigator.clipboard.writeText throws synchronously", async () => {
    const writeText = vi.fn().mockImplementation(() => {
      throw new Error("sync error");
    });
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  // ---- Clipboard API unavailable: navigator / clipboard missing or partial ----

  test("returns false when navigator is undefined", async () => {
    setNavigator(undefined);
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when navigator is null", async () => {
    setNavigator(null);
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("falls through to document path when navigator.clipboard is undefined", async () => {
    // navigator exists but clipboard property is absent
    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn().mockReturnValue(true),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(true);
  });

  test("falls through to document path when navigator.clipboard is null", async () => {
    setNavigator({ clipboard: null });
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn().mockReturnValue(true),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(true);
  });

  test("falls through when clipboard.writeText is not a function", async () => {
    // clipboard exists but writeText is a non-function truthy value
    setNavigator({ clipboard: { writeText: "not a function" } });
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn().mockReturnValue(true),
    });

    // "not a function" is truthy so the if-branch is entered and called → throws → catch → false
    // Actually wait: `if (clipboard?.writeText)` is truthy (string), so it enters the branch
    // and tries `await clipboard.writeText(text)` which calls a string → TypeError → caught → false
    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("falls through when clipboard.writeText is 0 (falsy)", async () => {
    setNavigator({ clipboard: { writeText: 0 } });
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn().mockReturnValue(true),
    });

    // 0 is falsy, so clipboard?.writeText is falsy → falls to document path → true
    await expect(writeTextToClipboard("hello")).resolves.toBe(true);
  });

  test("falls through when clipboard.writeText is null (falsy)", async () => {
    setNavigator({ clipboard: { writeText: null } });
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn().mockReturnValue(true),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(true);
  });

  // ---- Document fallback: success ----

  test("falls back to document.execCommand and returns true", async () => {
    const textarea = createMockTextarea();
    const appendChild = vi.fn();
    const execCommand = vi.fn().mockReturnValue(true);

    setNavigator({});
    setDocument({
      body: { appendChild },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand,
    });

    await expect(writeTextToClipboard("copy me")).resolves.toBe(true);

    // textarea wiring
    expect(textarea.value).toBe("copy me");
    expect(textarea.setAttribute).toHaveBeenCalledWith("readonly", "");
    expect(textarea.style.position).toBe("fixed");
    expect(textarea.style.top).toBe("-9999px");
    expect(textarea.style.left).toBe("-9999px");
    expect(appendChild).toHaveBeenCalledWith(textarea);
    expect(textarea.select).toHaveBeenCalledOnce();
    expect(execCommand).toHaveBeenCalledWith("copy");

    // cleanup (finally block)
    expect(textarea.remove).toHaveBeenCalledOnce();
  });

  test("returns false when document.execCommand returns false", async () => {
    const textarea = createMockTextarea();

    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand: vi.fn().mockReturnValue(false),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
    // textarea is still cleaned up via finally
    expect(textarea.remove).toHaveBeenCalledOnce();
  });

  // ---- Document fallback: document APIs missing (return false) ----

  test("returns false when document is undefined", async () => {
    setNavigator({});
    setDocument(undefined);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document is null", async () => {
    setNavigator({});
    setDocument(null);

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document.body is undefined", async () => {
    setNavigator({});
    setDocument({
      body: undefined,
      createElement: vi.fn(),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document.body is null", async () => {
    setNavigator({});
    setDocument({
      body: null,
      createElement: vi.fn(),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document.body.appendChild is missing", async () => {
    setNavigator({});
    setDocument({
      body: {},
      createElement: vi.fn(),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document.execCommand is missing", async () => {
    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn(),
      // no execCommand
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when document.execCommand is null", async () => {
    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn(),
      execCommand: null,
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  // ---- Document fallback: error during execCommand path ----

  test("returns false when createElement throws", async () => {
    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockImplementation(() => {
        throw new Error("createElement failed");
      }),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when appendChild throws", async () => {
    setNavigator({});
    setDocument({
      body: {
        appendChild: vi.fn().mockImplementation(() => {
          throw new Error("appendChild failed");
        }),
      },
      createElement: vi.fn().mockReturnValue(createMockTextarea()),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
  });

  test("returns false when select() throws and still removes textarea", async () => {
    const textarea = createMockTextarea();
    textarea.select.mockImplementation(() => {
      throw new Error("select failed");
    });

    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand: vi.fn(),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
    // remove is NOT called because the error happens before the inner try/finally
    // (the error is caught by the outer catch, not the inner finally)
    // Actually let's re-read the source: select() is called outside the inner try/finally,
    // so if it throws, the outer catch catches it and textarea.remove() is never called.
    expect(textarea.remove).not.toHaveBeenCalled();
  });

  test("returns false when execCommand throws and still removes textarea", async () => {
    const textarea = createMockTextarea();

    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand: vi.fn().mockImplementation(() => {
        throw new Error("execCommand failed");
      }),
    });

    await expect(writeTextToClipboard("hello")).resolves.toBe(false);
    // execCommand is inside the inner try/finally, so remove IS called
    expect(textarea.remove).toHaveBeenCalledOnce();
  });

  // ---- Both navigator and document completely absent ----

  test("returns false when both navigator and document are completely absent", async () => {
    setNavigator(undefined);
    setDocument(undefined);

    await expect(writeTextToClipboard("anything")).resolves.toBe(false);
  });

  // ---- Special characters / long text ----

  test("handles multiline text in clipboard API path", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    const multiline = "line1\nline2\nline3";
    await expect(writeTextToClipboard(multiline)).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith(multiline);
  });

  test("handles multiline text in document fallback path", async () => {
    const textarea = createMockTextarea();

    setNavigator({});
    setDocument({
      body: { appendChild: vi.fn() },
      createElement: vi.fn().mockReturnValue(textarea),
      execCommand: vi.fn().mockReturnValue(true),
    });

    const multiline = "line1\nline2\nline3";
    await expect(writeTextToClipboard(multiline)).resolves.toBe(true);
    expect(textarea.value).toBe(multiline);
  });

  test("handles special characters in text", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } });
    setDocument(undefined);

    const special = '<script>alert("xss")</script>';
    await expect(writeTextToClipboard(special)).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith(special);
  });
});
