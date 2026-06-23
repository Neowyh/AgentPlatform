import {
  BookOpenTextIcon,
  CompassIcon,
  FileCodeIcon,
  FileCogIcon,
  FilePlayIcon,
  FileTextIcon,
  ImageIcon,
} from "lucide-react";
import { describe, expect, test } from "vitest";

import {
  checkCodeFile,
  getFileExtension,
  getFileExtensionDisplayName,
  getFileIcon,
  getFileName,
} from "@/core/utils/files";

// ---------------------------------------------------------------------------
// getFileName
// ---------------------------------------------------------------------------
describe("getFileName", () => {
  test("returns the last path segment for a unix path", () => {
    expect(getFileName("/home/user/project/file.ts")).toBe("file.ts");
  });

  test("returns the filename when there is no directory prefix", () => {
    expect(getFileName("readme.md")).toBe("readme.md");
  });

  test("handles deeply nested paths", () => {
    expect(getFileName("a/b/c/d/e/f.txt")).toBe("f.txt");
  });

  test("returns the trailing segment even for a trailing slash (empty string)", () => {
    expect(getFileName("a/b/")).toBe("");
  });

  test("handles a single-segment path", () => {
    expect(getFileName("file.txt")).toBe("file.txt");
  });

  test("handles paths with spaces and special characters", () => {
    expect(getFileName("/path/to/my file (copy).pdf")).toBe(
      "my file (copy).pdf",
    );
  });
});

// ---------------------------------------------------------------------------
// getFileExtension
// ---------------------------------------------------------------------------
describe("getFileExtension", () => {
  test("returns the extension in lowercase for a simple filename", () => {
    expect(getFileExtension("file.TXT")).toBe("txt");
  });

  test("returns the last extension segment for a compound extension", () => {
    expect(getFileExtension("archive.tar.gz")).toBe("gz");
  });

  test("returns the extension for a full path", () => {
    expect(getFileExtension("/home/user/file.PY")).toBe("py");
  });

  test("returns the entire filename when there is no dot (single segment)", () => {
    // "Makefile".split(".").pop()! === "Makefile"
    expect(getFileExtension("Makefile")).toBe("makefile");
  });

  test("is case-insensitive via toLocaleLowerCase", () => {
    expect(getFileExtension("image.JPEG")).toBe("jpeg");
  });

  test("handles dotfiles like .gitignore", () => {
    // ".gitignore".split(".") => ["", "gitignore"] => pop => "gitignore"
    expect(getFileExtension(".gitignore")).toBe("gitignore");
  });
});

// ---------------------------------------------------------------------------
// checkCodeFile
// ---------------------------------------------------------------------------
describe("checkCodeFile", () => {
  test("returns isCodeFile: true and correct language for a known extension", () => {
    expect(checkCodeFile("app.ts")).toEqual({
      isCodeFile: true,
      language: "typescript",
    });
  });

  test("returns isCodeFile: true for python files", () => {
    expect(checkCodeFile("main.py")).toEqual({
      isCodeFile: true,
      language: "python",
    });
  });

  test("returns isCodeFile: true for yaml/yml", () => {
    expect(checkCodeFile("config.yaml")).toEqual({
      isCodeFile: true,
      language: "yaml",
    });
    expect(checkCodeFile("config.yml")).toEqual({
      isCodeFile: true,
      language: "yaml",
    });
  });

  test("returns isCodeFile: true for C++ variants", () => {
    expect(checkCodeFile("main.cpp")).toEqual({
      isCodeFile: true,
      language: "cpp",
    });
    expect(checkCodeFile("header.hpp")).toEqual({
      isCodeFile: true,
      language: "cpp",
    });
  });

  test("returns isCodeFile: true for docker-related files", () => {
    expect(checkCodeFile("Dockerfile")).toEqual({
      isCodeFile: true,
      language: "dockerfile",
    });
    expect(checkCodeFile("app.docker")).toEqual({
      isCodeFile: true,
      language: "docker",
    });
  });

  test("returns isCodeFile: true for markdown", () => {
    expect(checkCodeFile("README.md")).toEqual({
      isCodeFile: true,
      language: "markdown",
    });
  });

  test("returns isCodeFile: true for graphql", () => {
    expect(checkCodeFile("schema.graphql")).toEqual({
      isCodeFile: true,
      language: "graphql",
    });
    expect(checkCodeFile("query.gql")).toEqual({
      isCodeFile: true,
      language: "graphql",
    });
  });

  test("returns isCodeFile: false and language: null for an unknown extension", () => {
    expect(checkCodeFile("file.xyz")).toEqual({
      isCodeFile: false,
      language: null,
    });
  });

  test("returns isCodeFile: false for binary-like extensions", () => {
    expect(checkCodeFile("photo.jpg")).toEqual({
      isCodeFile: false,
      language: null,
    });
  });

  test("handles full paths with directories", () => {
    expect(checkCodeFile("/src/components/App.tsx")).toEqual({
      isCodeFile: true,
      language: "tsx",
    });
  });

  test("is case-insensitive (extension upper-cased)", () => {
    expect(checkCodeFile("FILE.PY")).toEqual({
      isCodeFile: true,
      language: "python",
    });
  });

  test("checks every mapped extension category at least once", () => {
    // Text
    expect(checkCodeFile("a.txt").isCodeFile).toBe(true);
    // JS/TS
    expect(checkCodeFile("a.jsx").isCodeFile).toBe(true);
    // Web
    expect(checkCodeFile("a.css").isCodeFile).toBe(true);
    // Java/JVM
    expect(checkCodeFile("a.java").isCodeFile).toBe(true);
    // Go
    expect(checkCodeFile("a.go").isCodeFile).toBe(true);
    // Rust
    expect(checkCodeFile("a.rs").isCodeFile).toBe(true);
    // Shell
    expect(checkCodeFile("a.sh").isCodeFile).toBe(true);
    // Config & Data
    expect(checkCodeFile("a.json").isCodeFile).toBe(true);
    // SQL
    expect(checkCodeFile("a.sql").isCodeFile).toBe(true);
    // Other languages
    expect(checkCodeFile("a.swift").isCodeFile).toBe(true);
    // Infrastructure
    expect(checkCodeFile("a.tf").isCodeFile).toBe(true);
    // Git
    expect(checkCodeFile(".gitignore").isCodeFile).toBe(true);
    // Misc
    expect(checkCodeFile("a.proto").isCodeFile).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// getFileExtensionDisplayName
// ---------------------------------------------------------------------------
describe("getFileExtensionDisplayName", () => {
  test("returns 'Word' for .doc", () => {
    expect(getFileExtensionDisplayName("report.doc")).toBe("Word");
  });

  test("returns 'Word' for .docx", () => {
    expect(getFileExtensionDisplayName("report.docx")).toBe("Word");
  });

  test("returns 'Markdown' for .md", () => {
    expect(getFileExtensionDisplayName("README.md")).toBe("Markdown");
  });

  test("returns 'Text' for .txt", () => {
    expect(getFileExtensionDisplayName("notes.txt")).toBe("Text");
  });

  test("returns 'PowerPoint' for .ppt", () => {
    expect(getFileExtensionDisplayName("slides.ppt")).toBe("PowerPoint");
  });

  test("returns 'PowerPoint' for .pptx", () => {
    expect(getFileExtensionDisplayName("slides.pptx")).toBe("PowerPoint");
  });

  test("returns 'Excel' for .xls", () => {
    expect(getFileExtensionDisplayName("budget.xls")).toBe("Excel");
  });

  test("returns 'Excel' for .xlsx", () => {
    expect(getFileExtensionDisplayName("budget.xlsx")).toBe("Excel");
  });

  test("returns uppercase extension for unknown extensions", () => {
    expect(getFileExtensionDisplayName("file.xyz")).toBe("XYZ");
  });

  test("returns uppercase extension for a known code extension not in the switch", () => {
    expect(getFileExtensionDisplayName("app.py")).toBe("PY");
  });

  test("works with a full path", () => {
    expect(getFileExtensionDisplayName("/documents/report.docx")).toBe("Word");
  });

  test("handles case-insensitivity for extension matching", () => {
    expect(getFileExtensionDisplayName("FILE.MD")).toBe("Markdown");
  });

  test("handles dotfiles (e.g., .gitignore)", () => {
    // ".gitignore" => fileName = ".gitignore", extension = "gitignore"
    expect(getFileExtensionDisplayName(".gitignore")).toBe("GITIGNORE");
  });
});

// ---------------------------------------------------------------------------
// getFileIcon
// ---------------------------------------------------------------------------
describe("getFileIcon", () => {
  // lucide-react icons are wrapped in forwardRef, so result.type is the
  // forwardRef wrapper object, not a plain function with a .name property.
  // We compare result.type directly against the imported icon references.

  test("returns FileCogIcon for .skill files", () => {
    const result = getFileIcon("agent.skill");
    expect(result).toBeDefined();
    expect(result.type).toBe(FileCogIcon);
  });

  test("returns CompassIcon for .html files", () => {
    const result = getFileIcon("index.html");
    expect(result.type).toBe(CompassIcon);
  });

  test("returns BookOpenTextIcon for .txt files", () => {
    const result = getFileIcon("notes.txt");
    expect(result.type).toBe(BookOpenTextIcon);
  });

  test("returns BookOpenTextIcon for .md files", () => {
    const result = getFileIcon("README.md");
    expect(result.type).toBe(BookOpenTextIcon);
  });

  test("returns ImageIcon for image extensions", () => {
    const imageExts = [
      "jpg",
      "jpeg",
      "png",
      "gif",
      "bmp",
      "tiff",
      "ico",
      "webp",
      "svg",
      "heic",
    ];
    for (const ext of imageExts) {
      const result = getFileIcon(`photo.${ext}`);
      expect(result.type).toBe(ImageIcon);
    }
  });

  test("returns FilePlayIcon for audio extensions", () => {
    const audioExts = [
      "mp3",
      "wav",
      "ogg",
      "aac",
      "m4a",
      "flac",
      "wma",
      "aiff",
      "ape",
    ];
    for (const ext of audioExts) {
      const result = getFileIcon(`track.${ext}`);
      expect(result.type).toBe(FilePlayIcon);
    }
  });

  test("returns FilePlayIcon for video extensions", () => {
    const videoExts = ["mp4", "mov", "m4v"];
    for (const ext of videoExts) {
      const result = getFileIcon(`clip.${ext}`);
      expect(result.type).toBe(FilePlayIcon);
    }
  });

  test("returns FileCodeIcon for known code file extensions", () => {
    const codeExts = ["ts", "tsx", "js", "py", "rs", "go", "java"];
    for (const ext of codeExts) {
      const result = getFileIcon(`source.${ext}`);
      expect(result.type).toBe(FileCodeIcon);
    }
  });

  test("returns FileTextIcon for completely unknown extensions", () => {
    const result = getFileIcon("file.xyz");
    expect(result.type).toBe(FileTextIcon);
  });

  test("returns FileTextIcon for binary/image-like extensions not in any switch case and not code files", () => {
    const result = getFileIcon("app.exe");
    expect(result.type).toBe(FileTextIcon);
  });

  test("forwards the className prop to the icon component", () => {
    const result = getFileIcon("notes.txt", "my-class");
    expect(result.props.className).toBe("my-class");
  });

  test("omits className when not provided", () => {
    const result = getFileIcon("notes.txt");
    expect(result.props.className).toBeUndefined();
  });

  test("returns FileCodeIcon for code files with className", () => {
    const result = getFileIcon("app.ts", "icon-lg");
    expect(result.type).toBe(FileCodeIcon);
    expect(result.props.className).toBe("icon-lg");
  });

  test("uses getFileExtension internally (case-insensitive)", () => {
    const result = getFileIcon("FILE.HTML");
    expect(result.type).toBe(CompassIcon);
  });

  test("handles full paths with directories", () => {
    const result = getFileIcon("/src/components/App.tsx");
    expect(result.type).toBe(FileCodeIcon);
  });
});
