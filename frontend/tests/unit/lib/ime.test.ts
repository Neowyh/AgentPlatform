import { describe, expect, test } from "vitest";

import { isIMEComposing } from "@/lib/ime";

/**
 * Helper to build a minimal React KeyboardEvent-like object.
 * Only the properties accessed by `isIMEComposing` are implemented.
 */
function makeEvent(
  overrides: { isComposing?: boolean; keyCode?: number } = {},
) {
  const { isComposing = false, keyCode = 0 } = overrides;
  return {
    nativeEvent: { isComposing },
    keyCode,
  } as unknown as Parameters<typeof isIMEComposing>[0];
}

describe("isIMEComposing", () => {
  // ------------------------------------------------------------------
  // Default parameter behaviour
  // ------------------------------------------------------------------

  test("returns false when no IME signal is present and isComposing defaults to false", () => {
    expect(isIMEComposing(makeEvent())).toBe(false);
  });

  // ------------------------------------------------------------------
  // isComposing parameter (first disjunct)
  // ------------------------------------------------------------------

  test("returns true when isComposing parameter is true", () => {
    expect(isIMEComposing(makeEvent(), true)).toBe(true);
  });

  test("returns true when isComposing parameter is true even if event signals are absent", () => {
    expect(
      isIMEComposing(makeEvent({ isComposing: false, keyCode: 0 }), true),
    ).toBe(true);
  });

  // ------------------------------------------------------------------
  // nativeEvent.isComposing (second disjunct)
  // ------------------------------------------------------------------

  test("returns true when nativeEvent.isComposing is true", () => {
    expect(isIMEComposing(makeEvent({ isComposing: true }))).toBe(true);
  });

  test("returns true when nativeEvent.isComposing is true and keyCode is 229", () => {
    expect(isIMEComposing(makeEvent({ isComposing: true, keyCode: 229 }))).toBe(
      true,
    );
  });

  // ------------------------------------------------------------------
  // keyCode === 229 (third disjunct)
  // ------------------------------------------------------------------

  test("returns true when keyCode is 229", () => {
    expect(isIMEComposing(makeEvent({ keyCode: 229 }))).toBe(true);
  });

  test("returns true when keyCode is 229 and nativeEvent.isComposing is false", () => {
    expect(
      isIMEComposing(makeEvent({ isComposing: false, keyCode: 229 })),
    ).toBe(true);
  });

  // ------------------------------------------------------------------
  // All three signals active at once
  // ------------------------------------------------------------------

  test("returns true when all three signals are active", () => {
    expect(
      isIMEComposing(makeEvent({ isComposing: true, keyCode: 229 }), true),
    ).toBe(true);
  });

  // ------------------------------------------------------------------
  // Boundary / negative keyCode values
  // ------------------------------------------------------------------

  test("returns false when keyCode is 228 (just below 229)", () => {
    expect(isIMEComposing(makeEvent({ keyCode: 228 }))).toBe(false);
  });

  test("returns false when keyCode is 230 (just above 229)", () => {
    expect(isIMEComposing(makeEvent({ keyCode: 230 }))).toBe(false);
  });

  test("returns false when keyCode is 0 and no other signal", () => {
    expect(isIMEComposing(makeEvent({ keyCode: 0 }))).toBe(false);
  });

  test("returns false when keyCode is negative", () => {
    expect(isIMEComposing(makeEvent({ keyCode: -1 }))).toBe(false);
  });

  // ------------------------------------------------------------------
  // explicit isComposing = false (edge case for the default param)
  // ------------------------------------------------------------------

  test("returns false when isComposing parameter is explicitly false", () => {
    expect(
      isIMEComposing(makeEvent({ isComposing: false, keyCode: 0 }), false),
    ).toBe(false);
  });
});
