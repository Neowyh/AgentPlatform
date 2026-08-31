"use client";

import { BellIcon } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import type { ResourceNotification } from "@/core/resources/api";
import {
  useMarkAllResourceNotificationsRead,
  useMarkResourceNotificationRead,
  useResourceNotifications,
} from "@/core/resources/hooks";

function resourceName(notification: ResourceNotification): string {
  const detail = notification.detail ?? {};
  return (
    (detail.resource_display_name as string) ||
    (detail.resource_slug as string) ||
    notification.resource_id
  );
}

export function ResourceNotificationCenter() {
  const { t } = useI18n();
  const { data, isLoading } = useResourceNotifications();
  const markRead = useMarkResourceNotificationRead();
  const markAllRead = useMarkAllResourceNotificationsRead();

  const unreadCount = data?.unread_count ?? 0;

  const items = useMemo(() => data?.items ?? [], [data]);

  const visibilityLabel = (visibility: unknown): string => {
    if (typeof visibility === "string") {
      if (visibility === "private") return t.resources.visibilityPrivate;
      if (visibility === "department") return t.resources.visibilityDepartment;
      if (visibility === "public") return t.resources.visibilityPublic;
      return visibility;
    }
    if (typeof visibility === "number") {
      return String(visibility);
    }
    return "";
  };

  const titleFor = (notification: ResourceNotification): string => {
    const detail = notification.detail ?? {};
    switch (notification.event) {
      case "visibility_reduced":
        return t.resources.notificationsVisibilityReduced(
          resourceName(notification),
        );
      case "visibility_reduced_cascade":
        return t.resources.notificationsVisibilityReducedCascade(
          resourceName(notification),
        );
      case "admin_visibility_reduced":
        return t.resources.notificationsAdminVisibilityReduced(
          typeof detail.impacted_count === "number" ? detail.impacted_count : 0,
        );
      default:
        return t.resources.notificationsUnknownEvent;
    }
  };

  const subtitleFor = (notification: ResourceNotification): string => {
    const detail = notification.detail ?? {};
    const previous = visibilityLabel(detail.previous_visibility);
    const current = visibilityLabel(detail.visibility);
    if (previous && current) {
      return `${previous} → ${current}`;
    }
    const createdAt = notification.created_at
      ? new Date(notification.created_at).toLocaleString()
      : "";
    return createdAt;
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllRead.mutateAsync();
      toast.success(t.resources.notificationsMarkAllReadDone);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton
            tooltip={t.resources.notificationsTitle}
            className="relative"
            data-testid="resource-notification-trigger"
          >
            <BellIcon className="size-4" />
            {unreadCount > 0 && (
              <span className="bg-destructive text-destructive-foreground type-compact absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 font-semibold">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          sideOffset={4}
          className="w-80"
          onCloseAutoFocus={(event) => event.preventDefault()}
        >
          <DropdownMenuLabel className="flex items-center justify-between">
            <span>{t.resources.notificationsTitle}</span>
            {unreadCount > 0 && (
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground type-body cursor-pointer"
                onClick={handleMarkAllRead}
                disabled={markAllRead.isPending}
              >
                {t.resources.notificationsMarkAllRead}
              </button>
            )}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {isLoading && items.length === 0 ? (
            <p className="text-muted-foreground type-body px-3 py-6 text-center">
              ...
            </p>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground type-body px-3 py-6 text-center">
              {t.resources.notificationsEmpty}
            </p>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              {items.map((notification) => (
                <DropdownMenuItem
                  key={notification.id}
                  className="flex cursor-pointer flex-col items-start gap-0.5 py-2"
                  onClick={() => {
                    if (notification.read_at === null) {
                      void markRead.mutateAsync(notification.id);
                    }
                  }}
                >
                  <span
                    className={
                      notification.read_at === null ? "font-medium" : undefined
                    }
                  >
                    {titleFor(notification)}
                  </span>
                  <span className="text-muted-foreground type-body">
                    {subtitleFor(notification)}
                  </span>
                </DropdownMenuItem>
              ))}
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  );
}
