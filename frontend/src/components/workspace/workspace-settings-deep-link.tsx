"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import {
  openSettingsDialog,
  type SettingsSection,
  useSettingsDialog,
} from "./settings";
import { legacySettingsDestination } from "./settings/legacy-settings-destination";

const SETTINGS_SECTIONS = new Set<SettingsSection>([
  "account",
  "appearance",
  "channels",
  "memory",
  "subagents",
  "notification",
  "about",
]);

function asSettingsSection(value: string | null): SettingsSection | null {
  if (!value) return null;
  return SETTINGS_SECTIONS.has(value as SettingsSection)
    ? (value as SettingsSection)
    : null;
}

/**
 * Bridges the `?settings=<section>` query param to the shared settings dialog
 * store. It does not mount its own dialog — a single {@link SettingsDialogHost}
 * renders the one dialog — so a deep link can never race a second dialog opened
 * from the nav menu or command palette.
 */
export function WorkspaceSettingsDeepLink() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { open } = useSettingsDialog();
  const openedFromDeepLinkRef = useRef(false);

  useEffect(() => {
    const rawSection = searchParams.get("settings");
    // 合并形态：skills/tools 已移出设置对话框（入口改跳能力中心），
    // 但旧深链 ?settings=skills|tools 仍须按 legacySettingsDestination 重定向。
    const legacyDestination = legacySettingsDestination(rawSection);
    if (rawSection && legacyDestination) {
      router.replace(legacyDestination);
      return;
    }
    const nextSection = asSettingsSection(rawSection);
    if (nextSection) {
      openedFromDeepLinkRef.current = true;
      openSettingsDialog(nextSection);
    }
  }, [router, searchParams]);

  useEffect(() => {
    if (open || !openedFromDeepLinkRef.current) {
      return;
    }
    openedFromDeepLinkRef.current = false;
    if (searchParams.has("settings")) {
      const next = new URLSearchParams(searchParams);
      next.delete("settings");
      const suffix = next.toString();
      router.replace(suffix ? `${pathname}?${suffix}` : pathname, {
        scroll: false,
      });
    }
  }, [open, pathname, router, searchParams]);

  return null;
}
