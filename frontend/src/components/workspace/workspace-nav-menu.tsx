"use client";

import {
  BoxIcon,
  Building2Icon,
  ChevronsUpDown,
  ClipboardCheckIcon,
  InfoIcon,
  ScrollTextIcon,
  Settings2Icon,
  SettingsIcon,
  ShieldIcon,
  UsersIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

import { ResourceNotificationCenter } from "./resource-notification-center";
import { useSettingsDialog } from "./settings";

function NavMenuButtonContent({
  isSidebarOpen,
  t,
}: {
  isSidebarOpen: boolean;
  t: ReturnType<typeof useI18n>["t"];
}) {
  return isSidebarOpen ? (
    <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
      <SettingsIcon className="size-4" />
      <span>{t.workspace.settingsAndMore}</span>
      <ChevronsUpDown className="text-muted-foreground ml-auto size-4" />
    </div>
  ) : (
    <div className="flex size-full items-center justify-center">
      <SettingsIcon className="text-muted-foreground size-4" />
    </div>
  );
}

export function WorkspaceNavMenu() {
  const { openSettings } = useSettingsDialog();
  const [mounted, setMounted] = useState(false);
  const { open: isSidebarOpen } = useSidebar();
  const { t } = useI18n();
  const { user } = useAuth();

  // Enterprise RBAC: only super admins and department admins get the
  // management entries. The dialog itself is owned by the global
  // SettingsDialogHost; this menu only requests a section.
  const isAdmin =
    user?.system_role === "super_admin" ||
    user?.system_role === "department_admin";

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <SidebarMenu className="w-full">
      <ResourceNotificationCenter />
      <SidebarMenuItem>
        {mounted ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                data-testid="nav-menu-trigger"
              >
                <NavMenuButtonContent isSidebarOpen={isSidebarOpen} t={t} />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
              align="end"
              sideOffset={4}
            >
              <DropdownMenuGroup>
                <DropdownMenuItem
                  onClick={() => {
                    openSettings("appearance");
                  }}
                  data-testid="settings-menu-item"
                >
                  <Settings2Icon />
                  {t.common.settings}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
              </DropdownMenuGroup>
              {isAdmin && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuGroup>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin">
                        <ShieldIcon />
                        {t.workspace.adminPanel}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/users">
                        <UsersIcon />
                        {t.workspace.userManagement}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/departments">
                        <Building2Icon />
                        {t.workspace.departmentManagement}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/tools">
                        <WrenchIcon />
                        {t.workspace.toolManagement}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/resources">
                        <BoxIcon />
                        {t.workspace.resourceManagement}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/visibility-applications">
                        <ClipboardCheckIcon />
                        {t.workspace.applicationManagement}
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/workspace/admin/audit-logs">
                        <ScrollTextIcon />
                        {t.workspace.auditLogManagement}
                      </Link>
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  openSettings("about");
                }}
                data-testid="about-settings-menu-item"
              >
                <InfoIcon />
                {t.workspace.about}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <SidebarMenuButton size="lg" className="pointer-events-none">
            <NavMenuButtonContent isSidebarOpen={isSidebarOpen} t={t} />
          </SidebarMenuButton>
        )}
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
