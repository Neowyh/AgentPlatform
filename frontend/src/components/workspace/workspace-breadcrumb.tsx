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

interface BreadcrumbSegment {
  label: string;
  href?: string;
}

function getBreadcrumbSegments(pathname: string): BreadcrumbSegment[] {
  const segments: BreadcrumbSegment[] = [];
  const parts = pathname.split("/").filter(Boolean);

  // Always start with Workspace
  if (parts[0] === "workspace") {
    segments.push({ label: "Workspace", href: "/workspace" });

    // Handle different routes
    if (parts[1] === "agents") {
      segments.push({ label: "Agents", href: "/workspace/agents" });

      if (parts[2]) {
        // Agent detail page: /workspace/agents/[agent_name]
        const agentName = parts[2];
        segments.push({
          label: agentName,
          href: `/workspace/agents/${agentName}`,
        });

        if (parts[3] === "edit") {
          segments.push({ label: "Edit" });
        } else if (parts[3] === "chats") {
          segments.push({ label: "Chats" });

          if (parts[4] && parts[4] !== "new") {
            segments.push({ label: "Thread" });
          }
        }
      }
    } else if (parts[1] === "chats") {
      segments.push({ label: "Chats", href: "/workspace/chats" });

      if (parts[2] && parts[2] !== "new") {
        segments.push({ label: "Thread" });
      }
    } else if (parts[1] === "workflows") {
      segments.push({ label: "Workflows", href: "/workspace/workflows" });

      if (parts[2]) {
        const workflowName = parts[2];
        segments.push({
          label: workflowName,
          href: `/workspace/workflows/${workflowName}`,
        });

        if (parts[3] === "edit") {
          segments.push({ label: "Edit" });
        } else if (parts[3] === "runs") {
          segments.push({ label: "Runs" });
        }
      }
    } else if (parts[1] === "admin") {
      segments.push({ label: "Admin", href: "/workspace/admin" });

      if (parts[2] === "users") {
        segments.push({ label: "User Management" });
      } else if (parts[2] === "agents") {
        segments.push({ label: "Agent Management" });
      }
    }
  }

  return segments;
}

export function WorkspaceBreadcrumb() {
  const pathname = usePathname();
  const segments = getBreadcrumbSegments(pathname);

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
