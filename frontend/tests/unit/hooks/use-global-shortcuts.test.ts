import { cleanup, renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useGlobalShortcuts } from "@/hooks/use-global-shortcuts";

// Helper to create and dispatch a KeyboardEvent on window
function dispatchKey(
  key: string,
  options: Partial<KeyboardEventInit> = {},
  target?: EventTarget,
) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    ...options,
  });
  if (target) {
    Object.defineProperty(event, "target", { value: target, writable: false });
  }
  window.dispatchEvent(event);
  return event;
}

// Helper to create a mock DOM element with a given tagName
function mockElement(tagName: string, isContentEditable = false) {
  const el = document.createElement(tagName);
  if (isContentEditable) {
    el.contentEditable = "true";
    // jsdom may not fully compute isContentEditable for dynamically created
    // elements, so we explicitly define the property to ensure it returns true.
    Object.defineProperty(el, "isContentEditable", {
      value: true,
      configurable: true,
    });
  }
  return el;
}

describe("useGlobalShortcuts", () => {
  let addSpy: ReturnType<typeof vi.spyOn>;
  let removeSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addSpy = vi.spyOn(window, "addEventListener");
    removeSpy = vi.spyOn(window, "removeEventListener");
  });

  afterEach(() => {
    cleanup();
    addSpy.mockRestore();
    removeSpy.mockRestore();
    vi.restoreAllMocks();
  });

  // ---------------------------------------------------------------
  // Listener lifecycle
  // ---------------------------------------------------------------

  it("registers a keydown listener on mount", () => {
    const addEventSpy = vi.spyOn(window, "addEventListener");
    renderHook(() =>
      useGlobalShortcuts([{ key: "k", meta: true, action: vi.fn() }]),
    );
    expect(addEventSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
  });

  it("removes the keydown listener on unmount", () => {
    const removeEventSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() =>
      useGlobalShortcuts([{ key: "k", meta: true, action: vi.fn() }]),
    );
    unmount();
    expect(removeEventSpy).toHaveBeenCalledWith(
      "keydown",
      expect.any(Function),
    );
  });

  // ---------------------------------------------------------------
  // Basic shortcut matching
  // ---------------------------------------------------------------

  it("fires action when key + meta (Cmd/Ctrl) match", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("k", { metaKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("fires action with Ctrl key (not just meta)", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "s", meta: true, action }]));

    dispatchKey("s", { ctrlKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("fires action for a shortcut that does not require meta", () => {
    const action = vi.fn();
    renderHook(() =>
      useGlobalShortcuts([{ key: "escape", meta: false, action }]),
    );

    dispatchKey("Escape");
    expect(action).toHaveBeenCalledTimes(1);
  });

  // ---------------------------------------------------------------
  // Case-insensitive key matching
  // ---------------------------------------------------------------

  it("matches keys case-insensitively", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "K", meta: true, action }]));

    dispatchKey("k", { metaKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("matches lowercase event key against uppercase shortcut key", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("K", { metaKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  // ---------------------------------------------------------------
  // Shift key handling
  // ---------------------------------------------------------------

  it("fires action when shift is required and present", () => {
    const action = vi.fn();
    renderHook(() =>
      useGlobalShortcuts([{ key: "n", meta: true, shift: true, action }]),
    );

    dispatchKey("n", { metaKey: true, shiftKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("does not fire action when shift is required but absent", () => {
    const action = vi.fn();
    renderHook(() =>
      useGlobalShortcuts([{ key: "n", meta: true, shift: true, action }]),
    );

    dispatchKey("n", { metaKey: true, shiftKey: false });
    expect(action).not.toHaveBeenCalled();
  });

  it("does not fire action when shift is present but not required", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("k", { metaKey: true, shiftKey: true });
    expect(action).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // Meta key requirement
  // ---------------------------------------------------------------

  it("does not fire meta-required shortcut when meta is not pressed", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("k", { metaKey: false, ctrlKey: false });
    expect(action).not.toHaveBeenCalled();
  });

  it("does not fire non-meta shortcut when meta is pressed", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "a", meta: false, action }]));

    dispatchKey("a", { metaKey: true });
    expect(action).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // Input suppression (except Cmd+K)
  // ---------------------------------------------------------------

  it("suppresses shortcut when focus is inside an INPUT element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "n", meta: true, action }]));

    const input = mockElement("INPUT");
    document.body.appendChild(input);
    dispatchKey("n", { metaKey: true }, input);
    document.body.removeChild(input);

    expect(action).not.toHaveBeenCalled();
  });

  it("suppresses shortcut when focus is inside a TEXTAREA element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "/", meta: true, action }]));

    const textarea = mockElement("TEXTAREA");
    document.body.appendChild(textarea);
    dispatchKey("/", { metaKey: true }, textarea);
    document.body.removeChild(textarea);

    expect(action).not.toHaveBeenCalled();
  });

  it("suppresses shortcut when focus is inside a contentEditable element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: ",", meta: true, action }]));

    const editable = mockElement("DIV", true);
    document.body.appendChild(editable);
    dispatchKey(",", { metaKey: true }, editable);
    document.body.removeChild(editable);

    expect(action).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // Cmd+K exception (always fires in inputs)
  // ---------------------------------------------------------------

  it("fires Cmd+K even when focus is inside an INPUT element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    const input = mockElement("INPUT");
    document.body.appendChild(input);
    dispatchKey("k", { metaKey: true }, input);
    document.body.removeChild(input);

    expect(action).toHaveBeenCalledTimes(1);
  });

  it("fires Cmd+K even when focus is inside a TEXTAREA element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    const textarea = mockElement("TEXTAREA");
    document.body.appendChild(textarea);
    dispatchKey("k", { metaKey: true }, textarea);
    document.body.removeChild(textarea);

    expect(action).toHaveBeenCalledTimes(1);
  });

  it("fires Cmd+K even when focus is inside a contentEditable element", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    const editable = mockElement("DIV", true);
    document.body.appendChild(editable);
    dispatchKey("k", { metaKey: true }, editable);
    document.body.removeChild(editable);

    expect(action).toHaveBeenCalledTimes(1);
  });

  // ---------------------------------------------------------------
  // Multiple shortcuts
  // ---------------------------------------------------------------

  it("fires the correct shortcut when multiple are registered", () => {
    const actionK = vi.fn();
    const actionN = vi.fn();
    const actionSlash = vi.fn();

    renderHook(() =>
      useGlobalShortcuts([
        { key: "k", meta: true, action: actionK },
        { key: "n", meta: true, shift: true, action: actionN },
        { key: "/", meta: true, action: actionSlash },
      ]),
    );

    dispatchKey("/", { metaKey: true });
    expect(actionSlash).toHaveBeenCalledTimes(1);
    expect(actionK).not.toHaveBeenCalled();
    expect(actionN).not.toHaveBeenCalled();
  });

  it("fires only the first matching shortcut", () => {
    const action1 = vi.fn();
    const action2 = vi.fn();

    renderHook(() =>
      useGlobalShortcuts([
        { key: "a", meta: true, action: action1 },
        { key: "a", meta: true, action: action2 },
      ]),
    );

    dispatchKey("a", { metaKey: true });
    expect(action1).toHaveBeenCalledTimes(1);
    expect(action2).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // No match scenarios
  // ---------------------------------------------------------------

  it("does not fire any action when no shortcut matches", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("x", { metaKey: true });
    expect(action).not.toHaveBeenCalled();
  });

  it("does not fire action for an unrelated key without meta", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    dispatchKey("z");
    expect(action).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // preventDefault
  // ---------------------------------------------------------------

  it("calls preventDefault on the event when a shortcut fires", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    const event = new KeyboardEvent("keydown", {
      key: "k",
      metaKey: true,
      bubbles: true,
    });
    const preventSpy = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(preventSpy).toHaveBeenCalledTimes(1);
  });

  it("does not call preventDefault when shortcut does not match", () => {
    const action = vi.fn();
    renderHook(() => useGlobalShortcuts([{ key: "k", meta: true, action }]));

    const event = new KeyboardEvent("keydown", {
      key: "x",
      metaKey: true,
      bubbles: true,
    });
    const preventSpy = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(preventSpy).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // Empty shortcuts array
  // ---------------------------------------------------------------

  it("handles an empty shortcuts array without errors", () => {
    expect(() => {
      renderHook(() => useGlobalShortcuts([]));
      dispatchKey("k", { metaKey: true });
    }).not.toThrow();
  });

  // ---------------------------------------------------------------
  // Listener re-registration when shortcuts change
  // ---------------------------------------------------------------

  it("re-registers listener when shortcuts array reference changes", () => {
    const removeEventSpy = vi.spyOn(window, "removeEventListener");

    const action1 = vi.fn();
    const { rerender } = renderHook(
      ({ shortcuts }) => useGlobalShortcuts(shortcuts),
      {
        initialProps: {
          shortcuts: [{ key: "k", meta: true, action: action1 }],
        },
      },
    );

    const action2 = vi.fn();
    rerender({ shortcuts: [{ key: "n", meta: true, action: action2 }] });

    // The old listener should have been removed and a new one added
    expect(removeEventSpy).toHaveBeenCalledWith(
      "keydown",
      expect.any(Function),
    );

    // The new shortcut should work
    dispatchKey("n", { metaKey: true });
    expect(action2).toHaveBeenCalledTimes(1);
    expect(action1).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------
  // Suppressed shortcut falls through to next matching shortcut
  // ---------------------------------------------------------------

  it("falls through to next shortcut when current is suppressed in input", () => {
    const suppressedAction = vi.fn();
    const fallbackAction = vi.fn();

    renderHook(() =>
      useGlobalShortcuts([
        { key: "n", meta: true, action: suppressedAction },
        { key: "n", meta: true, shift: true, action: fallbackAction },
      ]),
    );

    const input = mockElement("INPUT");
    document.body.appendChild(input);

    // First shortcut matches but is suppressed (in INPUT), second does not match (shift required)
    dispatchKey("n", { metaKey: true }, input);
    expect(suppressedAction).not.toHaveBeenCalled();
    expect(fallbackAction).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });
});
