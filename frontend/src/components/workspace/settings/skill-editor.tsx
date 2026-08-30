"use client";

import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { basicLightInit } from "@uiw/codemirror-theme-basic";
import { monokaiInit } from "@uiw/codemirror-theme-monokai";
import CodeMirror from "@uiw/react-codemirror";
import { AlertCircleIcon, SaveIcon, XIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useCallback, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SkillEditorProps {
  skillName: string;
  initialContent: string;
  onSave: (content: string) => Promise<void>;
  onClose: () => void;
}

interface FrontmatterValidation {
  valid: boolean;
  errors: string[];
}

function parseYamlFrontmatter(content: string): FrontmatterValidation {
  const errors: string[] = [];

  // Check if frontmatter exists
  if (!content.startsWith("---")) {
    errors.push("Missing YAML frontmatter (must start with ---)");
    return { valid: false, errors };
  }

  const endIndex = content.indexOf("---", 3);
  if (endIndex === -1) {
    errors.push("Unterminated YAML frontmatter (missing closing ---)");
    return { valid: false, errors };
  }

  const frontmatter = content.slice(3, endIndex).trim();

  // Check for required fields
  if (!frontmatter.includes("name:")) {
    errors.push('Missing required field: "name"');
  }
  if (!frontmatter.includes("description:")) {
    errors.push('Missing required field: "description"');
  }

  return { valid: errors.length === 0, errors };
}

const customDarkTheme = monokaiInit({
  settings: {
    background: "transparent",
    gutterBackground: "transparent",
    gutterForeground: "#555",
    gutterActiveForeground: "#fff",
    fontSize: "var(--text-base)",
  },
});

const customLightTheme = basicLightInit({
  settings: {
    background: "transparent",
    fontSize: "var(--text-base)",
  },
});

export function SkillEditor({
  skillName,
  initialContent,
  onSave,
  onClose,
}: SkillEditorProps) {
  const { resolvedTheme } = useTheme();
  const [content, setContent] = useState(initialContent);
  const [isSaving, setIsSaving] = useState(false);
  const [validation, setValidation] = useState<FrontmatterValidation>({
    valid: true,
    errors: [],
  });

  const extensions = useMemo(
    () => [
      markdown({
        base: markdownLanguage,
        codeLanguages: languages,
      }),
    ],
    [],
  );

  const handleChange = useCallback((value: string) => {
    setContent(value);
    setValidation(parseYamlFrontmatter(value));
  }, []);

  const handleSave = useCallback(async () => {
    const result = parseYamlFrontmatter(content);
    setValidation(result);

    if (!result.valid) {
      return;
    }

    setIsSaving(true);
    try {
      await onSave(content);
    } catch (err) {
      console.error("Failed to save skill:", err);
    } finally {
      setIsSaving(false);
    }
  }, [content, onSave]);

  // Escape HTML entities to prevent XSS
  const escapeHtml = useCallback((unsafe: string) => {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }, []);

  // Simple markdown preview (basic rendering with XSS protection)
  const renderPreview = useCallback(
    (text: string) => {
      // Extract content after frontmatter
      const endIndex = text.indexOf("---", 3);
      const bodyContent =
        endIndex !== -1 ? text.slice(endIndex + 3).trim() : text;

      // First escape HTML to prevent XSS attacks
      const escaped = escapeHtml(bodyContent);

      // Basic markdown rendering on escaped content
      return escaped
        .replace(
          /^### (.+)$/gm,
          '<h3 class="text-base font-semibold mt-4 mb-2">$1</h3>',
        )
        .replace(
          /^## (.+)$/gm,
          '<h2 class="text-base font-semibold mt-6 mb-3">$1</h2>',
        )
        .replace(
          /^# (.+)$/gm,
          '<h1 class="text-base font-bold mt-8 mb-4">$1</h1>',
        )
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(
          /`(.+?)`/g,
          '<code class="bg-muted rounded px-1 py-0.5 text-base">$1</code>',
        )
        .replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>')
        .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
        .replace(/\n\n/g, '</p><p class="mb-4">')
        .replace(/\n/g, "<br />");
    },
    [escapeHtml],
  );

  return (
    <div className="flex size-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h2 className="text-base font-semibold">Edit Skill: {skillName}</h2>
          <p className="text-muted-foreground text-base">
            Edit the SKILL.md content for this skill
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            <XIcon className="mr-1.5 h-4 w-4" />
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            <SaveIcon className="mr-1.5 h-4 w-4" />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {/* Validation errors */}
      {!validation.valid && (
        <div className="border-b px-4 py-2">
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertDescription>
              <ul className="list-inside list-disc">
                {validation.errors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* Editor and Preview */}
      <div className="flex min-h-0 flex-1">
        {/* Editor */}
        <div className="flex w-1/2 flex-col border-r">
          <div className="border-b px-4 py-2">
            <span className="text-base font-medium">Editor</span>
          </div>
          <div className="flex-1 overflow-auto">
            <CodeMirror
              value={content}
              onChange={handleChange}
              extensions={extensions}
              theme={
                resolvedTheme === "dark" ? customDarkTheme : customLightTheme
              }
              className="h-full [&_.cm-editor]:h-full [&_.cm-focused]:outline-none!"
              basicSetup={{
                lineNumbers: true,
                foldGutter: true,
                highlightActiveLine: true,
                highlightActiveLineGutter: true,
              }}
            />
          </div>
        </div>

        {/* Preview */}
        <div className="flex w-1/2 flex-col">
          <div className="border-b px-4 py-2">
            <span className="text-base font-medium">Preview</span>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <div
              className={cn(
                "prose prose-sm dark:prose-invert max-w-none",
                "[&_h1]:mt-8 [&_h1]:mb-4 [&_h1]:text-base [&_h1]:font-bold",
                "[&_h2]:mt-6 [&_h2]:mb-3 [&_h2]:text-base [&_h2]:font-semibold",
                "[&_h3]:mt-4 [&_h3]:mb-2 [&_h3]:text-base [&_h3]:font-semibold",
                "[&_p]:mb-4",
                "[&_li]:ml-4",
                "[&_code]:bg-muted [&_code]:rounded [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-base",
              )}
              dangerouslySetInnerHTML={{
                __html: `<p class="mb-4">${renderPreview(content)}</p>`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
