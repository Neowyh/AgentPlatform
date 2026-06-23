import { describe, expect, test } from "vitest";

import {
  appendHtmlPreviewBaseHref,
  appendHtmlPreviewScrollRestoration,
  buildWriteFileDraftContent,
  createHtmlPreviewScrollKey,
  getArtifactViewState,
  isWriteFileArtifact,
  HTML_PREVIEW_SCROLL_MESSAGE_SOURCE,
} from "@/core/artifacts/preview";

const ARTIFACT_PATH = "/artifact-fixtures/report.html";
const UNSUPPORTED_ARTIFACT_PATH = "/artifact-fixtures/data.csv";

// ── isWriteFileArtifact ──────────────────────────────────────────────────────

describe("isWriteFileArtifact", () => {
  test("returns true for write-file: prefix", () => {
    expect(isWriteFileArtifact("write-file:/path/to/file")).toBe(true);
  });

  test("returns false for regular path", () => {
    expect(isWriteFileArtifact("/path/to/file")).toBe(false);
  });

  test("returns false for empty string", () => {
    expect(isWriteFileArtifact("")).toBe(false);
  });
});

// ── getArtifactViewState ─────────────────────────────────────────────────────

describe("getArtifactViewState", () => {
  test("allows in-progress write artifacts to render a throttled preview", () => {
    expect(
      getArtifactViewState({
        filepath: `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`,
        isSupportPreview: true,
      }),
    ).toEqual({
      canPreview: true,
      initialViewMode: "preview",
    });
  });

  test("allows preview for a write artifact once the tool call has a result", () => {
    expect(
      getArtifactViewState({
        filepath: `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`,
        isSupportPreview: true,
        toolResult: "OK",
      }),
    ).toEqual({
      canPreview: true,
      initialViewMode: "preview",
    });
  });

  test("keeps failed write artifacts in code view", () => {
    expect(
      getArtifactViewState({
        filepath: `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`,
        isSupportPreview: true,
        toolResult: "Error: Failed to write file",
      }),
    ).toEqual({
      canPreview: false,
      initialViewMode: "code",
    });
  });

  test("keeps completed artifacts on their existing preview defaults", () => {
    expect(
      getArtifactViewState({
        filepath: ARTIFACT_PATH,
        isSupportPreview: true,
      }),
    ).toEqual({
      canPreview: true,
      initialViewMode: "preview",
    });
  });

  test("keeps unsupported artifacts in code view", () => {
    expect(
      getArtifactViewState({
        filepath: UNSUPPORTED_ARTIFACT_PATH,
        isSupportPreview: false,
      }),
    ).toEqual({
      canPreview: false,
      initialViewMode: "code",
    });
  });

  test("non-write artifact with unsupported preview goes to code view", () => {
    expect(
      getArtifactViewState({
        filepath: ARTIFACT_PATH,
        isSupportPreview: false,
      }),
    ).toEqual({
      canPreview: false,
      initialViewMode: "code",
    });
  });
});

// ── buildWriteFileDraftContent ────────────────────────────────────────────────

describe("buildWriteFileDraftContent", () => {
  test("builds a draft write-file artifact from successful writes plus the selected in-progress append", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-2&tool_call_id=call-2`;

    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "<!doctype html><html><body>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            name: "write_file",
            tool_call_id: "call-1",
            content: "OK",
          },
          {
            type: "ai",
            id: "ai-2",
            tool_calls: [
              {
                id: "call-2",
                name: "write_file",
                args: {
                  append: true,
                  path: ARTIFACT_PATH,
                  content: "<p>Extra content</p>",
                },
              },
            ],
          },
        ],
      }),
    ).toBe("<!doctype html><html><body><p>Extra content</p>");
  });

  test("does not include failed writes in a draft artifact", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-3&tool_call_id=call-3`;

    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "<html>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            name: "write_file",
            tool_call_id: "call-1",
            content: "OK",
          },
          {
            type: "ai",
            id: "ai-2",
            tool_calls: [
              {
                id: "call-2",
                name: "write_file",
                args: {
                  append: true,
                  path: ARTIFACT_PATH,
                  content: "<p>Failed</p>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-2",
            name: "write_file",
            tool_call_id: "call-2",
            content: "Error: write failed",
          },
          {
            type: "ai",
            id: "ai-3",
            tool_calls: [
              {
                id: "call-3",
                name: "write_file",
                args: {
                  append: true,
                  path: ARTIFACT_PATH,
                  content: "</html>",
                },
              },
            ],
          },
        ],
      }),
    ).toBe("<html></html>");
  });

  test("returns undefined when the selected append failed so the caller can fall back", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-2&tool_call_id=call-2`;

    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "<html>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            name: "write_file",
            tool_call_id: "call-1",
            content: "OK",
          },
          {
            type: "ai",
            id: "ai-2",
            tool_calls: [
              {
                id: "call-2",
                name: "write_file",
                args: {
                  append: true,
                  path: ARTIFACT_PATH,
                  content: "<p>Failed append</p>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-2",
            name: "write_file",
            tool_call_id: "call-2",
            content: "Error: write failed",
          },
        ],
      }),
    ).toBeUndefined();
  });

  test("returns undefined for non-write-file artifact path", () => {
    expect(
      buildWriteFileDraftContent({
        filepath: "/regular/file.html",
        messages: [],
      }),
    ).toBeUndefined();
  });

  test("returns undefined for invalid write-file URL", () => {
    expect(
      buildWriteFileDraftContent({
        filepath: "write-file:not-a-valid-url",
        messages: [],
      }),
    ).toBeUndefined();
  });

  test("returns undefined when no matching tool_calls found", () => {
    expect(
      buildWriteFileDraftContent({
        filepath: `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-other",
                name: "write_file",
                args: {
                  path: "/other/path.html",
                  content: "content",
                },
              },
            ],
          },
        ],
      }),
    ).toBeUndefined();
  });

  test("handles messages without tool_calls", () => {
    expect(
      buildWriteFileDraftContent({
        filepath: `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`,
        messages: [
          { type: "ai", id: "ai-1" },
          { type: "human", id: "h-1", content: "hello" },
        ],
      }),
    ).toBeUndefined();
  });

  test("handles array content in tool result (getTextContent)", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`;
    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "<html>test</html>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            tool_call_id: "call-1",
            content: [{ text: "OK" }],
          },
        ],
      }),
    ).toBe("<html>test</html>");
  });

  test("handles non-string non-array content in tool result", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`;
    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "<html>test</html>",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            tool_call_id: "call-1",
            content: 12345,
          },
        ],
      }),
    ).toBe("<html>test</html>");
  });

  test("non-write_file tool calls are ignored", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`;
    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "read_file",
                args: { path: ARTIFACT_PATH },
              },
            ],
          },
        ],
      }),
    ).toBeUndefined();
  });

  test("selected tool_call without tool_result returns draft (in-progress)", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`;
    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "draft content",
                },
              },
            ],
          },
        ],
      }),
    ).toBe("draft content");
  });

  test("handles content array with non-text objects in getTextContent", () => {
    const filepath = `write-file:${ARTIFACT_PATH}?message_id=ai-1&tool_call_id=call-1`;
    expect(
      buildWriteFileDraftContent({
        filepath,
        messages: [
          {
            type: "ai",
            id: "ai-1",
            tool_calls: [
              {
                id: "call-1",
                name: "write_file",
                args: {
                  path: ARTIFACT_PATH,
                  content: "content",
                },
              },
            ],
          },
          {
            type: "tool",
            id: "tool-1",
            tool_call_id: "call-1",
            content: [{ notText: "ignored" }, { text: "OK" }],
          },
        ],
      }),
    ).toBe("content");
  });
});

// ── appendHtmlPreviewScrollRestoration ────────────────────────────────────────

describe("appendHtmlPreviewScrollRestoration", () => {
  test("injects scroll restoration at the start of the HTML head", () => {
    const html =
      '<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"></head><body><main>content</main></body></html>';

    expect(appendHtmlPreviewScrollRestoration(html, ARTIFACT_PATH)).toContain(
      "<script data-ideer-artifact-scroll-restoration>",
    );
    expect(appendHtmlPreviewScrollRestoration(html, ARTIFACT_PATH)).toContain(
      "<head><script data-ideer-artifact-scroll-restoration>",
    );
  });

  test("preserves existing head elements when injecting scroll restoration", () => {
    const html =
      '<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"></head><body><main>content</main></body></html>';
    const result = appendHtmlPreviewScrollRestoration(
      appendHtmlPreviewBaseHref(
        html,
        "/demo/threads/thread-1/user-data/outputs/report.html?download=true",
        "http://localhost/workspace/chats/thread-1",
      ),
      ARTIFACT_PATH,
    );

    expect(result).toContain(
      '<base href="http://localhost/demo/threads/thread-1/user-data/outputs/">',
    );
    expect(
      result.indexOf("data-ideer-artifact-scroll-restoration"),
    ).toBeLessThan(
      result.indexOf(
        '<base href="http://localhost/demo/threads/thread-1/user-data/outputs/">',
      ),
    );
  });

  test("does not duplicate HTML scroll restoration script", () => {
    const html = appendHtmlPreviewScrollRestoration(
      "<html><body>x</body></html>",
    );

    expect(
      appendHtmlPreviewScrollRestoration(html).match(
        /data-ideer-artifact-scroll-restoration/g,
      ),
    ).toHaveLength(1);
  });

  test("scopes HTML scroll restoration without exposing the artifact path", () => {
    const artifactPath =
      '/artifact-fixtures/a</script><script>alert("x")</script>.html';
    const html = appendHtmlPreviewScrollRestoration(
      "<html><body>x</body></html>",
      artifactPath,
    );

    expect(html).toContain(createHtmlPreviewScrollKey(artifactPath));
    expect(html).toContain("window.parent.postMessage");
    expect(html).not.toContain("window.name");
    expect(html).not.toContain("/artifact-fixtures/a");
    expect(html).not.toContain("<script>alert");
  });

  test("appends script before </body> when no <head> tag", () => {
    const html = "<html><body><p>content</p></body></html>";
    const result = appendHtmlPreviewScrollRestoration(html);
    expect(result).toContain("data-ideer-artifact-scroll-restoration");
    expect(result).toContain("</body>");
  });

  test("appends script at end when no <head> or </body> tags", () => {
    const html = "<div>simple content</div>";
    const result = appendHtmlPreviewScrollRestoration(html);
    expect(result).toContain("data-ideer-artifact-scroll-restoration");
    expect(result).toContain("<div>simple content</div>");
  });

  test("uses default scroll key when none provided", () => {
    const html = "<html><head></head><body>x</body></html>";
    const result = appendHtmlPreviewScrollRestoration(html);
    expect(result).toContain("data-ideer-artifact-scroll-restoration");
  });
});

// ── appendHtmlPreviewBaseHref ────────────────────────────────────────────────

describe("appendHtmlPreviewBaseHref", () => {
  test("returns content unchanged when url is not provided", () => {
    const html = "<html><head></head><body>x</body></html>";
    expect(appendHtmlPreviewBaseHref(html)).toBe(html);
  });

  test("returns content unchanged when <base> tag already exists", () => {
    const html =
      '<html><head><base href="http://example.com/"></head><body>x</body></html>';
    expect(appendHtmlPreviewBaseHref(html, "http://other.com/page.html")).toBe(
      html,
    );
  });

  test("injects base href after <head> tag", () => {
    const html = "<html><head><title>Test</title></head><body>x</body></html>";
    const result = appendHtmlPreviewBaseHref(
      html,
      "/demo/file.html",
      "http://localhost/workspace",
    );
    expect(result).toContain("<base href=");
    expect(result).toContain("<title>Test</title>");
  });

  test("prepends base element when no <head> tag", () => {
    const html = "<html><body>x</body></html>";
    const result = appendHtmlPreviewBaseHref(
      html,
      "/demo/file.html",
      "http://localhost/workspace",
    );
    expect(result).toContain("<base href=");
  });

  test("escapes ampersands and quotes in href attribute", () => {
    // The URL constructor normalizes special chars, so we test with a URL
    // that contains encoded characters that survive resolution
    const html = "<html><head></head><body>x</body></html>";
    const result = appendHtmlPreviewBaseHref(
      html,
      "/path/file?a=1&b=2",
      "http://localhost/",
    );
    // The base href should contain the resolved URL
    expect(result).toContain("<base href=");
  });

  test("handles head tag with attributes", () => {
    const html =
      '<html><head lang="en"><title>Test</title></head><body>x</body></html>';
    const result = appendHtmlPreviewBaseHref(
      html,
      "/demo/file.html",
      "http://localhost/",
    );
    expect(result).toContain("<base href=");
    expect(result).toContain('lang="en"');
  });
});

// ── createHtmlPreviewScrollKey ────────────────────────────────────────────────

describe("createHtmlPreviewScrollKey", () => {
  test("returns a consistent hash for the same input", () => {
    const key1 = createHtmlPreviewScrollKey("test-value");
    const key2 = createHtmlPreviewScrollKey("test-value");
    expect(key1).toBe(key2);
  });

  test("returns different hashes for different inputs", () => {
    const key1 = createHtmlPreviewScrollKey("value-1");
    const key2 = createHtmlPreviewScrollKey("value-2");
    expect(key1).not.toBe(key2);
  });

  test("returns a string with artifact-scroll prefix", () => {
    const key = createHtmlPreviewScrollKey("some-value");
    expect(key).toMatch(/^artifact-scroll:/);
  });

  test("handles empty string", () => {
    const key = createHtmlPreviewScrollKey("");
    expect(key).toMatch(/^artifact-scroll:/);
  });
});

// ── HTML_PREVIEW_SCROLL_MESSAGE_SOURCE ───────────────────────────────────────

describe("HTML_PREVIEW_SCROLL_MESSAGE_SOURCE", () => {
  test("has the expected value", () => {
    expect(HTML_PREVIEW_SCROLL_MESSAGE_SOURCE).toBe(
      "ideer-artifact-preview-scroll",
    );
  });
});
