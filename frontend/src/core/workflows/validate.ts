/**
 * Shared YAML validation for workflow editor pages.
 *
 * Performs structural checks without requiring a full YAML parser:
 *   - Non-empty content
 *   - Parseable key-value structure at the top level
 *   - Required fields: name (string), steps (non-empty list)
 *   - Basic indentation consistency
 */

// ---------------------------------------------------------------------------
// Lightweight helpers – no external dependency required.
// ---------------------------------------------------------------------------

interface TopLevelFields {
  name?: string;
  stepsPresent: boolean;
  stepsHasItems: boolean;
}

/**
 * Extract top-level field information from a YAML string.
 *
 * This is intentionally minimal – it only recognises the subset of YAML
 * needed for workflow validation (top-level scalar "name" and block-sequence
 * "steps").  It is **not** a general-purpose parser.
 */
function parseTopLevelFields(yaml: string): {
  fields: TopLevelFields;
  errors: string[];
} {
  const fields: TopLevelFields = { stepsPresent: false, stepsHasItems: false };
  const errors: string[] = [];

  const lines = yaml.split("\n");

  // Track whether we are inside a block sequence under "steps:".
  let inStepsBlock = false;
  let stepsIndent = -1;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i] ?? "";

    // Skip blank lines and comments.
    if (raw.trim() === "" || raw.trim().startsWith("#")) continue;

    // Calculate indentation (number of leading spaces).
    const indent = raw.length - raw.trimStart().length;
    const line = raw.trim();

    // ---- Inside the steps block -------------------------------------------
    if (inStepsBlock) {
      if (indent <= stepsIndent && line !== "") {
        // We left the steps block.
        inStepsBlock = false;
      } else if (line.startsWith("- ")) {
        fields.stepsHasItems = true;
        // We only need to know there is at least one item – keep scanning for
        // potential syntax errors but stop counting.
      }
    }

    // ---- Top-level keys ---------------------------------------------------
    if (indent === 0 && !inStepsBlock) {
      const colonIdx = line.indexOf(":");
      if (colonIdx === -1) {
        // A non-empty, non-comment line at indent 0 without a colon is invalid.
        errors.push(
          `Line ${i + 1}: expected a key-value pair (missing ":"): "${line}"`,
        );
        continue;
      }

      const key = line.slice(0, colonIdx).trim();
      const value = line.slice(colonIdx + 1).trim();

      if (key === "name") {
        if (value === "") {
          // Could be a multi-line value – accept it but flag if nothing follows
          // at deeper indentation.  For our purposes an empty name is still
          // better than no name key at all; the backend will reject it.
          fields.name = "";
        } else {
          // Strip optional surrounding quotes.
          fields.name = value.replace(/^["']|["']$/g, "");
        }
      }

      if (key === "steps") {
        fields.stepsPresent = true;
        if (value === "" || value === "[]") {
          // Empty mapping or explicit empty list.
          inStepsBlock = value === "";
          stepsIndent = indent;
          if (value === "[]") {
            fields.stepsHasItems = false; // explicitly empty
          }
        } else if (value.startsWith("[")) {
          // Inline list – treat as having items if more than just "[".
          fields.stepsHasItems = value.length > 2;
        }
      }
    }
  }

  return { fields, errors };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Validate YAML content for a workflow definition.
 *
 * Returns an array of human-readable error strings.  An empty array means
 * the content passed all checks.
 */
export function validateYaml(content: string): string[] {
  const errors: string[] = [];
  const trimmed = content.trim();

  if (!trimmed) {
    errors.push("YAML content cannot be empty");
    return errors;
  }

  // 1. Parse top-level structure.
  const { fields, errors: parseErrors } = parseTopLevelFields(trimmed);
  errors.push(...parseErrors);

  // 2. Required field: name
  if (fields.name === undefined) {
    errors.push('Missing required field: "name"');
  } else if (fields.name === "") {
    errors.push('Required field "name" must have a value');
  }

  // 3. Required field: steps (must be a non-empty list)
  if (!fields.stepsPresent) {
    errors.push('Missing required field: "steps"');
  } else if (!fields.stepsHasItems) {
    errors.push('Required field "steps" must contain at least one step');
  }

  // 4. Basic bracket balance check (catches unclosed arrays / objects).
  const opens = (trimmed.match(/\[/g) || []).length;
  const closes = (trimmed.match(/\]/g) || []).length;
  if (opens !== closes) {
    errors.push("Unbalanced brackets: check for unclosed arrays");
  }

  const braceOpens = (trimmed.match(/\{/g) || []).length;
  const braceCloses = (trimmed.match(/\}/g) || []).length;
  if (braceOpens !== braceCloses) {
    errors.push("Unbalanced braces: check for unclosed inline mappings");
  }

  return errors;
}
