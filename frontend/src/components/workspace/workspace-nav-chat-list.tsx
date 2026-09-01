"use client";

import {
  BookOpenIcon,
  MessagesSquare,
  NetworkIcon,
  WorkflowIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton isActive={pathname === "/workspace/chats"} asChild>
            <Link className="text-sidebar-foreground" href="/workspace/chats">
              <MessagesSquare />
              <span>{t.sidebar.chats}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={
              pathname.startsWith("/workspace/capabilities") ||
              pathname.startsWith("/workspace/resources")
            }
            asChild
          >
            <Link
              className="text-sidebar-foreground"
              href="/workspace/capabilities/experts"
            >
              <NetworkIcon />
              <span>{t.sidebar.capabilities}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={
              pathname.startsWith("/workspace/workflows") ||
              pathname.startsWith("/workspace/automations")
            }
            asChild
          >
            <Link
              className="text-sidebar-foreground"
              href="/workspace/workflows"
            >
              <WorkflowIcon />
              <span>{t.sidebar.workflows}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/library")}
            asChild
          >
            <Link className="text-sidebar-foreground" href="/workspace/library">
              <BookOpenIcon />
              <span>{t.sidebar.library}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
