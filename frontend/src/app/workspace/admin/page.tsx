"use client";

import {
  Building2Icon,
  ClipboardCheckIcon,
  ScrollTextIcon,
  UsersIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAdminStats } from "@/core/admin/hooks";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

const statCards = [
  {
    key: "total_users" as const,
    labelKey: "totalUsers",
    icon: UsersIcon,
    href: "/workspace/admin/users",
    color: "text-blue-500",
  },
  {
    key: "total_departments" as const,
    labelKey: "totalDepartments",
    icon: Building2Icon,
    href: "/workspace/admin/departments",
    color: "text-green-500",
  },
  {
    key: "total_tools" as const,
    labelKey: "totalTools",
    icon: WrenchIcon,
    href: "/workspace/admin/tools",
    color: "text-orange-500",
  },
  {
    key: "pending_applications" as const,
    labelKey: "pendingApplications",
    icon: ClipboardCheckIcon,
    href: "/workspace/admin/visibility-applications",
    color: "text-yellow-500",
  },
  {
    key: "total_resources" as const,
    labelKey: "totalResources",
    icon: WrenchIcon,
    href: "/workspace/admin/resources",
    color: "text-indigo-500",
  },
  {
    key: "audit_logs" as const,
    labelKey: "auditLogs",
    icon: ScrollTextIcon,
    href: "/workspace/admin/audit-logs",
    color: "text-slate-500",
  },
] as const;

export default function AdminDashboardPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin =
    user?.system_role === "super_admin" ||
    user?.system_role === "department_admin";
  const { data: stats, isLoading, error } = useAdminStats(isAdmin);

  return (
    <div className="flex size-full flex-col" data-testid="admin-dashboard">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="type-page-title font-semibold">
            {t.admin.dashboard.title}
          </h1>
          <p className="text-muted-foreground type-body mt-0.5">
            {t.admin.dashboard.subtitle}
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.dashboard.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error instanceof Error ? error.message : String(error)}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {statCards.map((card) => (
              <Link key={card.key} href={card.href}>
                <Card
                  className="transition-shadow hover:shadow-md"
                  data-testid="admin-stat-card"
                >
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="type-body font-medium">
                      {t.admin.dashboard[card.labelKey]}
                    </CardTitle>
                    <card.icon className={`h-4 w-4 ${card.color}`} />
                  </CardHeader>
                  <CardContent>
                    <div className="type-body font-bold">
                      {stats?.[card.key] ?? 0}
                    </div>
                    <CardDescription className="type-body">
                      {t.admin.dashboard.viewDetails}
                    </CardDescription>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
