export function legacySettingsDestination(
  section: string | null,
): string | null {
  switch (section) {
    case "skills":
      return "/workspace/capabilities/skills";
    case "tools":
      return "/workspace/capabilities/connectors";
    default:
      return null;
  }
}
