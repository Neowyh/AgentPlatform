"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { useAgent } from "@/core/agents";
import type { Agent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import type { Translations } from "@/core/i18n/locales/types";

interface BreadcrumbSegment {
  label: string;
  href?: string;
}

function getBreadcrumbSegments(
  pathname: string,
  t: Translations,
  agentLabel?: string,
): BreadcrumbSegment[] {
  const segments: BreadcrumbSegment[] = [];
  const parts = pathname.split("/").filter(Boolean);

  // Always start with Workspace
  if (parts[0] === "workspace") {
    segments.push({ label: t.breadcrumb.workspace, href: "/workspace" });

    // Handle different routes
    if (parts[1] === "capabilities" && parts[2] === "experts") {
      segments.push({
        label: t.sidebar.capabilities,
        href: "/workspace/capabilities/experts",
      });

      if (parts[2]) {
        const agentName = parts[3];
        if (agentName) {
          segments.push({
            label: t.resources.experts,
            href: "/workspace/capabilities/experts",
          });
        }
        const { label, href } = agentName
          ? {
              label: agentLabel ?? t.common.loading,
              href: `/workspace/capabilities/experts/${agentName}`,
            }
          : {
              label: t.resources.experts,
              href: "/workspace/capabilities/experts",
            };
        segments.push({
          label,
          href,
        });

        if (parts[4] === "edit") {
          segments.push({ label: t.common.edit });
        } else if (parts[4] === "chats") {
          segments.push({ label: t.breadcrumb.chats });

          if (parts[5] && parts[5] !== "new") {
            segments.push({ label: t.pages.untitled });
          }
        }
      }
    } else if (parts[1] === "chats") {
      segments.push({ label: t.breadcrumb.chats, href: "/workspace/chats" });

      if (parts[2] && parts[2] !== "new") {
        segments.push({ label: t.pages.untitled });
      }
    } else if (parts[1] === "workflows") {
      segments.push({
        label: t.breadcrumb.workflows,
        href: "/workspace/workflows",
      });

      if (parts[2]) {
        const workflowName = parts[2];
        segments.push({
          label: workflowName,
          href: `/workspace/workflows/${workflowName}`,
        });

        if (parts[3] === "edit") {
          segments.push({ label: t.breadcrumb.edit });
        } else if (parts[3] === "runs") {
          segments.push({ label: t.breadcrumb.runs });
        }
      }
    } else if (parts[1] === "resources") {
      segments.push({
        label: t.sidebar.resources,
        href: "/workspace/resources",
      });

      if (parts[2]) {
        const resourceId = parts[2];
        segments.push({
          label: resourceId,
          href: `/workspace/resources/${resourceId}`,
        });
      }
    } else if (parts[1] === "capabilities") {
      const tab = parts[2] ?? "experts";
      const tabLabels: Record<string, string> = {
        experts: t.resources.experts,
        skills: t.resources.skills,
        connectors: t.resources.connectors,
      };
      segments.push({
        label: t.sidebar.capabilities,
        href: "/workspace/capabilities/experts",
      });
      segments.push({
        label: tabLabels[tab] ?? tab,
        href: `/workspace/capabilities/${tab}`,
      });
      if (parts[3]) {
        segments.push({
          label: parts[3],
          href: `/workspace/capabilities/${tab}/${parts[3]}`,
        });
      }
    } else if (parts[1] === "automations") {
      segments.push({
        label: t.sidebar.workflows,
        href: "/workspace/workflows",
      });

      if (parts[2]) {
        const automationId = parts[2];
        segments.push({
          label: automationId,
          href: `/workspace/automations/${automationId}`,
        });
      }
    } else if (parts[1] === "library") {
      segments.push({
        label: t.sidebar.library,
        href: "/workspace/library",
      });

      if (parts[2]) {
        const docId = parts[2];
        segments.push({
          label: docId,
          href: `/workspace/library/${docId}`,
        });
      }
    } else if (parts[1] === "admin") {
      segments.push({
        label: t.workspace.adminPanel,
        href: "/workspace/admin",
      });

      if (parts[2] === "users") {
        segments.push({ label: t.workspace.userManagement });
      } else if (parts[2] === "agents") {
        segments.push({ label: t.workspace.departmentManagement });
      }
    }
  }

  return segments;
}

export function WorkspaceBreadcrumb({ agent }: { agent?: Agent } = {}) {
  const pathname = usePathname();
  const { t } = useI18n();
  const parts = pathname.split("/").filter(Boolean);
  const agentId =
    parts[1] === "capabilities" && parts[2] === "experts"
      ? parts[3]
      : undefined;
  const { agent: fetchedAgent } = useAgent(agent ? undefined : agentId);
  const segments = getBreadcrumbSegments(
    pathname,
    t,
    agent?.name ?? fetchedAgent?.name,
  );

  if (segments.length <= 1) {
    return null;
  }

  return (
    <Breadcrumb className="px-6 py-2">
      <BreadcrumbList>
        {segments.map((segment, index) => (
          <BreadcrumbItem key={index}>
            {index > 0 && <BreadcrumbSeparator />}
            {segment.href ? (
              <BreadcrumbLink asChild>
                <Link href={segment.href}>{segment.label}</Link>
              </BreadcrumbLink>
            ) : (
              <BreadcrumbPage>{segment.label}</BreadcrumbPage>
            )}
          </BreadcrumbItem>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
