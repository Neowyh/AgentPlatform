/**
 * Shared YAML validation for workflow editor pages.
 */

export function validateYaml(content: string): string[] {
  const errors: string[] = [];
  const trimmed = content.trim();

  if (!trimmed) {
    errors.push("YAML content cannot be empty");
    return errors;
  }

  // Basic structural checks
  if (!trimmed.includes("name:")) {
    errors.push('Missing required field: "name"');
  }
  if (!trimmed.includes("steps:")) {
    errors.push('Missing required field: "steps"');
  }

  return errors;
}
