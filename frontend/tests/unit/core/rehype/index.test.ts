import type { Root, Element, Text } from "hast";
import { describe, expect, test, vi, beforeEach } from "vitest";

// Mock react's useMemo to return the callback directly
vi.mock("react", () => ({
  useMemo: vi.fn((fn: () => unknown) => fn()),
}));

import {
  rehypeSplitWordsIntoSpans,
  useRehypeSplitWordsIntoSpans,
} from "@/core/rehype";

// ── Helpers ──────────────────────────────────────────────────────────────

function makeTextNode(value: string): Text {
  return { type: "text", value };
}

function makeElement(
  tagName: string,
  children: Array<Element | Text>,
): Element {
  return {
    type: "element",
    tagName,
    properties: {},
    children,
  };
}

function makeRoot(children: Array<Element | Text>): Root {
  return {
    type: "root",
    children: children as Root["children"],
  };
}

// ── Tests ────────────────────────────────────────────────────────────────

describe("rehypeSplitWordsIntoSpans", () => {
  test("returns a function (rehype plugin)", () => {
    const plugin = rehypeSplitWordsIntoSpans();
    expect(typeof plugin).toBe("function");
  });

  test("splits English text inside <p> into span-wrapped words", () => {
    const tree = makeRoot([makeElement("p", [makeTextNode("Hello world")])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const p = tree.children[0] as Element;
    expect(p.tagName).toBe("p");
    // English text gets segmented into words
    expect(p.children.length).toBeGreaterThan(0);
    for (const child of p.children) {
      expect(child.type).toBe("element");
      if (child.type === "element") {
        expect(child.tagName).toBe("span");
        expect(child.properties?.className).toBe("animate-fade-in");
      }
    }
  });

  test("splits text inside heading tags (h1-h6)", () => {
    for (const tag of ["h1", "h2", "h3", "h4", "h5", "h6"]) {
      const tree = makeRoot([makeElement(tag, [makeTextNode("Test heading")])]);
      const plugin = rehypeSplitWordsIntoSpans();
      plugin(tree);

      const heading = tree.children[0] as Element;
      expect(heading.tagName).toBe(tag);
      const spans = heading.children.filter(
        (c) => c.type === "element" && c.tagName === "span",
      );
      expect(spans.length).toBeGreaterThan(0);
    }
  });

  test("splits text inside <li> tags", () => {
    const tree = makeRoot([makeElement("li", [makeTextNode("List item")])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const li = tree.children[0] as Element;
    const spans = li.children.filter(
      (c) => c.type === "element" && c.tagName === "span",
    );
    expect(spans.length).toBeGreaterThan(0);
  });

  test("splits text inside <strong> tags", () => {
    const tree = makeRoot([makeElement("strong", [makeTextNode("Bold text")])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const strong = tree.children[0] as Element;
    const spans = strong.children.filter(
      (c) => c.type === "element" && c.tagName === "span",
    );
    expect(spans.length).toBeGreaterThan(0);
  });

  test("does not modify text inside unsupported tags", () => {
    const tree = makeRoot([makeElement("div", [makeTextNode("Skip this")])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const div = tree.children[0] as Element;
    // div is not in the target list, so the text node should remain unchanged
    const textChild = div.children.find((c) => c.type === "text");
    expect(textChild?.value).toBe("Skip this");
  });

  test("passes through non-text children unchanged", () => {
    const childElement = makeElement("span", [makeTextNode("inner")]);
    const tree = makeRoot([makeElement("p", [childElement])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const p = tree.children[0] as Element;
    // The nested element should be preserved (not a text node)
    const nested = p.children.find(
      (c) => c.type === "element" && c.tagName === "span",
    );
    expect(nested).toBeDefined();
  });

  test("CJK text nodes are kept as-is without splitting", () => {
    const tree = makeRoot([makeElement("p", [makeTextNode("你好世界")])]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const p = tree.children[0] as Element;
    // CJK text should be kept as a text node (not wrapped in spans)
    const textChild = p.children.find((c) => c.type === "text");
    expect(textChild).toBeDefined();
    expect(textChild?.value).toBe("你好世界");
  });

  test("handles element with no children gracefully", () => {
    const tree = makeRoot([makeElement("p", [])]);
    const plugin = rehypeSplitWordsIntoSpans();
    // Should not throw
    expect(() => plugin(tree)).not.toThrow();
  });

  test("handles mixed children (text + elements)", () => {
    const tree = makeRoot([
      makeElement("p", [
        makeTextNode("Hello "),
        makeElement("em", [makeTextNode("world")]),
      ]),
    ]);
    const plugin = rehypeSplitWordsIntoSpans();
    plugin(tree);

    const p = tree.children[0] as Element;
    // Text "Hello " gets split, <em> element is preserved
    expect(p.children.length).toBeGreaterThan(0);
  });
});

describe("useRehypeSplitWordsIntoSpans", () => {
  test("returns plugin array when enabled is true (default)", () => {
    const result = useRehypeSplitWordsIntoSpans();
    expect(result).toEqual([rehypeSplitWordsIntoSpans]);
  });

  test("returns plugin array when enabled is explicitly true", () => {
    const result = useRehypeSplitWordsIntoSpans(true);
    expect(result).toEqual([rehypeSplitWordsIntoSpans]);
  });

  test("returns empty array when enabled is false", () => {
    const result = useRehypeSplitWordsIntoSpans(false);
    expect(result).toEqual([]);
  });
});
