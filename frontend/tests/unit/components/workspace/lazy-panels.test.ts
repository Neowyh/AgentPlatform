import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "@rstest/core";

const FRONTEND_ROOT = path.resolve(__dirname, "../../../..");
const read = (relativePath: string) =>
  readFileSync(path.join(FRONTEND_ROOT, relativePath), "utf8");

describe("interaction-only bundle boundaries", () => {
  it("does not import the settings dialog until its store is open", () => {
    const host = read(
      "src/components/workspace/settings/settings-dialog-host.tsx",
    );
    expect(host).toContain("dynamic(");
    expect(host).toContain("if (!open)");
    expect(host).not.toContain(
      'import { SettingsDialog } from "./settings-dialog"',
    );
  });

  it("loads each settings page from its active section", () => {
    const dialog = read(
      "src/components/workspace/settings/settings-dialog.tsx",
    );
    // The dialog module is itself behind the host's dynamic() boundary, so its
    // statically imported pages still load only when the dialog opens; each
    // page must additionally render only for its active section.
    const sectionsAndPages = [
      ["account", "AccountSettingsPage"],
      ["appearance", "AppearanceSettingsPage"],
      ["memory", "MemorySettingsPage"],
      ["notification", "NotificationSettingsPage"],
      ["about", "AboutSettingsPage"],
    ] as const;
    for (const [section, page] of sectionsAndPages) {
      expect(dialog).toContain(`activeSection === "${section}"`);
      expect(dialog).toContain(page);
    }
    // The heavy MCP/skill/subagent management pages moved to their own
    // workbench surfaces; they must not rejoin the dialog bundle.
    expect(dialog).not.toMatch(
      /import \{ (?:Tool|Skill|Subagent)SettingsPage \} from "@\/components\/workspace\/settings\//,
    );
  });

  it("keeps right-panel implementations behind dynamic imports", () => {
    const chatBox = read("src/components/workspace/chats/chat-box.tsx");
    expect(chatBox).toContain('import dynamic from "next/dynamic"');
    expect(chatBox).not.toMatch(
      /import \{ (?:ArtifactFileDetail|ArtifactFileList|BrowserViewPanel|SidecarPanel)/,
    );
    expect(chatBox.match(/dynamic\(/g)?.length).toBeGreaterThanOrEqual(4);
  });
});
