import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const { navigation, settings } = vi.hoisted(() => ({
  navigation: {
    pathname: "/workspace/chats/new",
    query: "",
    replace: vi.fn(),
  },
  settings: { openDialog: vi.fn() },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.query),
}));
vi.mock("@/components/workspace/settings", () => ({
  openSettingsDialog: settings.openDialog,
  useSettingsDialog: () => ({ open: false }),
}));

import { WorkspaceSettingsDeepLink } from "@/components/workspace/workspace-settings-deep-link";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("legacy settings deep links", () => {
  test.each([
    ["skills", "/workspace/capabilities/skills"],
    ["tools", "/workspace/capabilities/connectors"],
  ])("%s opens %s without the settings dialog", (section, destination) => {
    navigation.query = `settings=${section}`;
    render(<WorkspaceSettingsDeepLink />);

    expect(navigation.replace).toHaveBeenCalledWith(destination);
    expect(settings.openDialog).not.toHaveBeenCalled();
  });
});
