/**
 * Shared YAML validation for workflow editor pages.
 *
 * Performs structural checks without requiring a full YAML parser:
 *   - Non-empty content
 *   - Parseable key-value structure at the top level
 *   - Required fields: schema_version: 2, name (string), nodes (non-empty list)
 *   - Basic indentation consistency
 */

// ---------------------------------------------------------------------------
// Lightweight helpers – no external dependency required.
// ---------------------------------------------------------------------------

interface TopLevelFields {
  schemaVersion: boolean;
  name?: string;
  nodesPresent: boolean;
  nodesHasItems: boolean;
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
  const fields: TopLevelFields = {
    schemaVersion: false,
    nodesPresent: false,
    nodesHasItems: false,
  };
  const errors: string[] = [];

  const lines = yaml.split("\n");

  // Track whether we are inside a block sequence under "nodes:".
  let inNodesBlock = false;
  let nodesIndent = -1;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i] ?? "";

    // Skip blank lines and comments.
    if (raw.trim() === "" || raw.trim().startsWith("#")) continue;

    // Calculate indentation (number of leading spaces).
    const indent = raw.length - raw.trimStart().length;
    const line = raw.trim();

    // ---- Inside the nodes block -------------------------------------------
    if (inNodesBlock) {
      if (indent <= nodesIndent && line !== "") {
        inNodesBlock = false;
      } else if (line.startsWith("- ")) {
        fields.nodesHasItems = true;
        // We only need to know there is at least one item – keep scanning for
        // potential syntax errors but stop counting.
      }
    }

    // ---- Top-level keys ---------------------------------------------------
    if (indent === 0 && !inNodesBlock) {
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

      if (key === "schema_version" && value === "2")
        fields.schemaVersion = true;
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

      if (key === "nodes") {
        fields.nodesPresent = true;
        if (value === "" || value === "[]") {
          // Empty mapping or explicit empty list.
          inNodesBlock = value === "";
          nodesIndent = indent;
          if (value === "[]") {
            fields.nodesHasItems = false; // explicitly empty
          }
        } else if (value.startsWith("[")) {
          // Inline list – treat as having items if more than just "[".
          fields.nodesHasItems = value.length > 2;
        }
      }
    }
  }

  return { fields, errors };
}

/**
 * Check that every action-type node has a non-empty action name.
 */
function checkEmptyActionNames(content: string): string[] {
  const errors: string[] = [];
  const lines = content.split("\n");

  // Walk through nodes inside the "nodes:" block.  Node items start with "- "
  // (indent >= nodesIndent).  Within each node we look for property "action:"
  // and, once found, check for "name: \"\"" in its children.
  let inNodes = false;
  let nodesIndent = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    const trimmed = line.trim();
    const indent = line.length - trimmed.length;

    if (trimmed === "" || trimmed.startsWith("#")) continue;

    // Detect the start of the nodes block
    if (!inNodes) {
      if (trimmed === "nodes:" || trimmed.startsWith("nodes:")) {
        inNodes = true;
        nodesIndent = indent;
      }
      continue;
    }

    // Still in nodes: a line at or shallower than nodes: itself exits
    if (indent <= nodesIndent) {
      inNodes = false;
      continue;
    }

    // Look for a node item "- ..." that has "type: action"
    if (!trimmed.startsWith("- ")) continue;
    const itemIndent = indent;

    // Scan forward through the node properties to see if it's an action node
    // with an empty name.
    if (_scanNodeForEmptyAction(lines, i + 1, itemIndent)) {
      errors.push(
        'Action node has empty "name" — provide a valid agent or tool name',
      );
    }
  }

  return errors;
}

/** Starting at `start` in `lines`, look for `type: action` then `action: . name: ""`. */
function _scanNodeForEmptyAction(
  lines: string[],
  start: number,
  itemIndent: number,
): boolean {
  let isAction = false;

  for (let j = start; j < lines.length; j++) {
    const prop = lines[j]!;
    const propTrimmed = prop.trim();
    const propIndent = prop.length - propTrimmed.length;

    if (propTrimmed === "" || propTrimmed.startsWith("#")) continue;
    if (propIndent <= itemIndent) break;

    if (/^type:\s*action/.test(propTrimmed)) {
      isAction = true;
    }

    if (isAction && propTrimmed === "action:") {
      const actionIndent = propIndent;

      for (let k = j + 1; k < lines.length; k++) {
        const child = lines[k]!;
        const childTrimmed = child.trim();
        const childIndent = child.length - childTrimmed.length;

        if (childTrimmed === "" || childTrimmed.startsWith("#")) continue;
        if (childIndent <= actionIndent) break;

        if (
          /^name:\s*""$/.test(childTrimmed) ||
          /^name:\s*''$/.test(childTrimmed)
        ) {
          return true;
        }
      }
      break;
    }
  }

  return false;
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

  // 2. Required v2 marker and name
  if (!fields.schemaVersion)
    errors.push('Required field "schema_version" must be 2');
  if (fields.name === undefined) {
    errors.push('Missing required field: "name"');
  } else if (fields.name === "") {
    errors.push('Required field "name" must have a value');
  }

  // 3. Required field: nodes (must be a non-empty list)
  if (!fields.nodesPresent) {
    errors.push('Missing required field: "nodes"');
  } else if (!fields.nodesHasItems) {
    errors.push('Required field "nodes" must contain at least one node');
  }

  // 4. Check that action-type nodes have a non-empty action name.
  const actionNameErrors = checkEmptyActionNames(trimmed);
  errors.push(...actionNameErrors);

  // 5. Basic bracket balance check (catches unclosed arrays / objects).
  const opens = (trimmed.match(/\[/g) ?? []).length;
  const closes = (trimmed.match(/\]/g) ?? []).length;
  if (opens !== closes) {
    errors.push("Unbalanced brackets: check for unclosed arrays");
  }

  const braceOpens = (trimmed.match(/\{/g) ?? []).length;
  const braceCloses = (trimmed.match(/\}/g) ?? []).length;
  if (braceOpens !== braceCloses) {
    errors.push("Unbalanced braces: check for unclosed inline mappings");
  }

  return errors;
}
