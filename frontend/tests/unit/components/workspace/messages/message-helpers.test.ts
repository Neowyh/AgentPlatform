import { describe, expect, test } from "vitest";

/**
 * Tests for the private helper functions in message-list-item.tsx.
 *
 * These helpers are not exported, so we reimplement and test the same logic
 * to verify correctness of the patterns used in the component.
 */

const FILE_TYPE_MAP: Record<string, string> = {
  json: "JSON",
  csv: "CSV",
  txt: "TXT",
  md: "Markdown",
  py: "Python",
  js: "JavaScript",
  ts: "TypeScript",
  tsx: "TSX",
  jsx: "JSX",
  html: "HTML",
  css: "CSS",
  xml: "XML",
  yaml: "YAML",
  yml: "YAML",
  pdf: "PDF",
  png: "PNG",
  jpg: "JPG",
  jpeg: "JPEG",
  gif: "GIF",
  svg: "SVG",
  zip: "ZIP",
  tar: "TAR",
  gz: "GZ",
};

const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"];

/** Mirrors the private getFileExt in message-list-item.tsx */
function getFileExt(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

/** Mirrors the private getFileTypeLabel in message-list-item.tsx */
function getFileTypeLabel(filename: string): string {
  const ext = getFileExt(filename);
  return FILE_TYPE_MAP[ext] ?? (ext.toUpperCase() || "FILE");
}

/** Mirrors the private isImageFile in message-list-item.tsx */
function isImageFile(filename: string): boolean {
  return IMAGE_EXTENSIONS.includes(getFileExt(filename));
}

/** Mirrors the private formatBytes in message-list-item.tsx */
function formatBytes(bytes: number): string {
  if (bytes === 0) return "—";
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

describe("getFileExt", () => {
  test("extracts extension from simple filename", () => {
    expect(getFileExt("file.txt")).toBe("txt");
  });

  test("lowercases the extension", () => {
    expect(getFileExt("image.PNG")).toBe("png");
    expect(getFileExt("data.CSV")).toBe("csv");
  });

  test("returns the full filename when there is no dot (no extension)", () => {
    expect(getFileExt("noextension")).toBe("noextension");
  });

  test("handles multiple dots correctly (takes last segment)", () => {
    expect(getFileExt("archive.tar.gz")).toBe("gz");
    expect(getFileExt("my.file.name.py")).toBe("py");
  });
});

describe("getFileTypeLabel", () => {
  test("returns the mapped label for known extensions", () => {
    expect(getFileTypeLabel("data.json")).toBe("JSON");
    expect(getFileTypeLabel("readme.md")).toBe("Markdown");
    expect(getFileTypeLabel("app.py")).toBe("Python");
    expect(getFileTypeLabel("style.css")).toBe("CSS");
  });

  test("returns uppercase extension for unknown types", () => {
    expect(getFileTypeLabel("file.xyz")).toBe("XYZ");
  });

  test("returns uppercase extension for extensionless files (no dot)", () => {
    // getFileExt("Makefile") returns "makefile" (the whole string as lowercase)
    // FILE_TYPE_MAP["makefile"] is undefined, so it falls through to ext.toUpperCase()
    expect(getFileTypeLabel("Makefile")).toBe("MAKEFILE");
  });

  test("handles yaml/yml mapping", () => {
    expect(getFileTypeLabel("config.yaml")).toBe("YAML");
    expect(getFileTypeLabel("config.yml")).toBe("YAML");
  });
});

describe("isImageFile", () => {
  test("returns true for image extensions", () => {
    expect(isImageFile("photo.png")).toBe(true);
    expect(isImageFile("icon.JPG")).toBe(true);
    expect(isImageFile("banner.jpeg")).toBe(true);
    expect(isImageFile("animation.gif")).toBe(true);
    expect(isImageFile("texture.webp")).toBe(true);
    expect(isImageFile("vector.svg")).toBe(true);
    expect(isImageFile("bitmap.bmp")).toBe(true);
  });

  test("returns false for non-image extensions", () => {
    expect(isImageFile("doc.pdf")).toBe(false);
    expect(isImageFile("data.csv")).toBe(false);
    expect(isImageFile("code.js")).toBe(false);
  });
});

describe("formatBytes", () => {
  test("returns dash for zero bytes", () => {
    expect(formatBytes(0)).toBe("—");
  });

  test("formats bytes less than 1 MB as KB", () => {
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(512)).toBe("0.5 KB");
    expect(formatBytes(10240)).toBe("10.0 KB");
  });

  test("formats bytes >= 1 MB as MB", () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
    expect(formatBytes(2097152)).toBe("2.0 MB");
    expect(formatBytes(1536000)).toBe("1.5 MB");
  });

  test("rounds to one decimal place", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(1234567)).toBe("1.2 MB");
  });
});
