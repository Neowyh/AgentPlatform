"use client";

import {
  BellIcon,
  CableIcon,
  InfoIcon,
  BrainIcon,
  PaletteIcon,
  PlugZapIcon,
  SparklesIcon,
  UsersRoundIcon,
  UserIcon,
  WrenchIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
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
import { SubagentSettingsPage } from "@/components/workspace/settings/subagent-settings-page";
import { useChannelProviders } from "@/core/channels/hooks";
import { hasUsableChannelProvider } from "@/core/channels/provider-state";
import { useI18n } from "@/core/i18n/hooks";
import {
  isLarkIntegrationUsable,
  useLarkIntegrationStatus,
} from "@/core/integrations/lark";
import { cn } from "@/lib/utils";

import { legacySettingsDestination } from "./legacy-settings-destination";

export type SettingsSection =
  | "account"
  | "appearance"
  | "channels"
  | "integrations"
  | "memory"
  | "notification"
  | "subagents"
  | "skills"
  | "tools"
  | "about";

type SettingsDialogProps = Omit<
  React.ComponentProps<typeof Dialog>,
  "onOpenChange"
> & {
  defaultSection?: SettingsSection;
  onOpenChange?: (open: boolean) => void;
};

export function SettingsDialog(props: SettingsDialogProps) {
  const { defaultSection = "appearance", onOpenChange, ...dialogProps } = props;
  const { t } = useI18n();
  const router = useRouter();
  const [activeSection, setActiveSection] =
    useState<SettingsSection>(defaultSection);

  // Channels is a deployment capability, not a universal setting: only
  // surface it when the backend reports something actually usable — a
  // configured, running channel provider. Failed or still-loading probes
  // hide the entry too, so an unknown capability never renders as an
  // actionable one; visibility here stays a UI concern and never replaces
  // server-side permission checks.
  const {
    enabled: channelsEnabled,
    providers,
    isLoading: channelsLoading,
    error: channelsError,
  } = useChannelProviders();
  const channelsAvailable =
    !channelsLoading &&
    !channelsError &&
    channelsEnabled &&
    hasUsableChannelProvider(providers);
  const {
    data: larkStatus,
    isLoading: larkLoading,
    error: larkError,
  } = useLarkIntegrationStatus();
  const integrationsAvailable =
    !larkLoading && !larkError && isLarkIntegrationUsable(larkStatus);

  // One availability map serves both the nav list and the fallback below, so
  // a section can never be listed while its page is unreachable.
  const sectionAvailability: Partial<Record<SettingsSection, boolean>> =
    useMemo(
      () => ({
        channels: channelsAvailable,
        integrations: integrationsAvailable,
      }),
      [channelsAvailable, integrationsAvailable],
    );

  // A deep link (or stale trigger) onto a capability section that the
  // deployment lacks falls back to the familiar default instead of rendering
  // a page for a capability that does not exist.
  const effectiveSection: SettingsSection =
    sectionAvailability[activeSection] === false ? "appearance" : activeSection;

  useEffect(() => {
    // When opening the dialog, ensure the active section follows the caller's intent.
    // This allows triggers like "About" to open the dialog directly on that page.
    if (dialogProps.open) {
      const destination = legacySettingsDestination(defaultSection);
      if (destination) {
        onOpenChange?.(false);
        router.push(destination);
        return;
      }
      setActiveSection(defaultSection);
    }
  }, [defaultSection, dialogProps.open, onOpenChange, router]);

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
      {
        id: "subagents",
        label: t.settings.sections.subagents,
        icon: UsersRoundIcon,
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
      t.settings.sections.subagents,
      t.settings.sections.notification,
      t.settings.sections.skills,
      t.settings.sections.tools,
      t.settings.sections.about,
    ],
  );
  return (
    <Dialog
      {...dialogProps}
      onOpenChange={(open) => onOpenChange?.(open)}
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
              {/* 合并回归修复：恢复本地"不可用能力入口不渲染"的门控——
                  sectionAvailability 同时服务导航列表与深链回退，缺了 filter
                  会让不可用渠道以可点击入口的形式暴露。 */}
              {sections
                .filter(({ id }) => sectionAvailability[id] ?? true)
                .map(({ id, label, icon: Icon }) => {
                  const active = effectiveSection === id;
                  return (
                    <li key={id}>
                      <button
                        type="button"
                        onClick={() => {
                          const destination = legacySettingsDestination(id);
                          if (destination) {
                            onOpenChange?.(false);
                            router.push(destination);
                          } else {
                            setActiveSection(id as SettingsSection);
                          }
                        }}
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
              {effectiveSection === "account" && <AccountSettingsPage />}
              {effectiveSection === "appearance" && <AppearanceSettingsPage />}
              {effectiveSection === "memory" && <MemorySettingsPage />}
              {effectiveSection === "subagents" && <SubagentSettingsPage />}
              {effectiveSection === "notification" && (
                <NotificationSettingsPage />
              )}
              {effectiveSection === "channels" && <ChannelsSettingsPage />}
              {effectiveSection === "integrations" && (
                <IntegrationsSettingsPage />
              )}
              {effectiveSection === "about" && <AboutSettingsPage />}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
