"use client";

import {
  BellIcon,
  CableIcon,
  InfoIcon,
  BrainIcon,
  PaletteIcon,
  PlugZapIcon,
  SparklesIcon,
  UserIcon,
  WrenchIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AboutSettingsPage } from "@/components/workspace/settings/about-settings-page";
import { AccountSettingsPage } from "@/components/workspace/settings/account-settings-page";
import { AppearanceSettingsPage } from "@/components/workspace/settings/appearance-settings-page";
import { ChannelsSettingsPage } from "@/components/workspace/settings/channels-settings-page";
import { IntegrationsSettingsPage } from "@/components/workspace/settings/integrations-settings-page";
import { MemorySettingsPage } from "@/components/workspace/settings/memory-settings-page";
import { NotificationSettingsPage } from "@/components/workspace/settings/notification-settings-page";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

// The skill/tool management pages are heavy (Markdown editors, MCP clients);
// keep them out of the dialog bundle while the restored sections stay
// reachable — the boundary guard in lazy-panels.test.ts pins this.
const SkillSettingsPage = dynamic(
  () =>
    import("@/components/workspace/settings/skill-settings-page").then(
      (module) => module.SkillSettingsPage,
    ),
);
const ToolSettingsPage = dynamic(
  () =>
    import("@/components/workspace/settings/tool-settings-page").then(
      (module) => module.ToolSettingsPage,
    ),
);

export type SettingsSection =
  | "account"
  | "appearance"
  | "channels"
  | "integrations"
  | "memory"
  | "notification"
  | "tools"
  | "subagents"
  | "skills"
  | "about";

type SettingsDialogProps = React.ComponentProps<typeof Dialog> & {
  defaultSection?: SettingsSection;
};

export function SettingsDialog(props: SettingsDialogProps) {
  const { defaultSection = "appearance", ...dialogProps } = props;
  const { t } = useI18n();
  const [activeSection, setActiveSection] =
    useState<SettingsSection>(defaultSection);

  useEffect(() => {
    // When opening the dialog, ensure the active section follows the caller's intent.
    // This allows triggers like "About" to open the dialog directly on that page.
    if (dialogProps.open) {
      setActiveSection(defaultSection);
    }
  }, [defaultSection, dialogProps.open]);

  const sections = useMemo(
    () => [
      {
        id: "account",
        label: t.settings.sections.account,
        icon: UserIcon,
      },
      {
        id: "appearance",
        label: t.settings.sections.appearance,
        icon: PaletteIcon,
      },
      {
        id: "notification",
        label: t.settings.sections.notification,
        icon: BellIcon,
      },
      {
        id: "channels",
        label: t.settings.sections.channels,
        icon: CableIcon,
      },
      {
        id: "integrations",
        label: t.settings.sections.integrations,
        icon: PlugZapIcon,
      },
      {
        id: "memory",
        label: t.settings.sections.memory,
        icon: BrainIcon,
      },
      { id: "skills", label: t.settings.sections.skills, icon: SparklesIcon },
      { id: "tools", label: t.settings.sections.tools, icon: WrenchIcon },
      { id: "about", label: t.settings.sections.about, icon: InfoIcon },
    ],
    [
      t.settings.sections.account,
      t.settings.sections.appearance,
      t.settings.sections.channels,
      t.settings.sections.integrations,
      t.settings.sections.memory,
      t.settings.sections.notification,
      t.settings.sections.tools,
      t.settings.sections.about,
    ],
  );
  return (
    <Dialog
      {...dialogProps}
      onOpenChange={(open) => props.onOpenChange?.(open)}
      data-testid="settings-dialog"
    >
      <DialogContent
        className="workbench-settings-dialog flex h-[75vh] max-h-[calc(100vh-2rem)] flex-col sm:max-w-5xl md:max-w-6xl"
        aria-describedby={undefined}
        data-testid="settings-dialog-content"
      >
        <DialogHeader className="gap-1">
          <DialogTitle>{t.settings.title}</DialogTitle>
          <p className="text-muted-foreground type-body">
            {t.settings.description}
          </p>
        </DialogHeader>
        <div className="workbench-settings-layout grid min-h-0 flex-1 gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
          <nav className="bg-sidebar min-h-0 overflow-y-auto rounded-lg border p-2">
            <ul className="space-y-1 pr-1">
              {sections.map(({ id, label, icon: Icon }) => {
                const active = activeSection === id;
                return (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => setActiveSection(id as SettingsSection)}
                      data-testid={`settings-tab-${id}`}
                      className={cn(
                        "type-body flex w-full items-center gap-3 rounded-md px-3 py-2 font-medium transition-colors",
                        active
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon className="size-4" />
                      <span>{label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <ScrollArea className="h-full min-h-0 rounded-lg border">
            <div className="space-y-8 p-6">
              {activeSection === "account" && <AccountSettingsPage />}
              {activeSection === "appearance" && <AppearanceSettingsPage />}
              {activeSection === "memory" && <MemorySettingsPage />}
              {activeSection === "notification" && <NotificationSettingsPage />}
              {activeSection === "channels" && <ChannelsSettingsPage />}
              {activeSection === "integrations" && <IntegrationsSettingsPage />}
              {activeSection === "skills" && <SkillSettingsPage />}
              {activeSection === "tools" && <ToolSettingsPage />}
              {activeSection === "about" && <AboutSettingsPage />}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
