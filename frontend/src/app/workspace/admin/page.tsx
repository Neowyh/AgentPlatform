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

const statCards = [
  {
    key: "total_users" as const,
    label: "用户总数",
    icon: UsersIcon,
    href: "/workspace/admin/users",
    color: "text-blue-500",
  },
  {
    key: "total_departments" as const,
    label: "部门总数",
    icon: Building2Icon,
    href: "/workspace/admin/departments",
    color: "text-green-500",
  },
  {
    key: "total_tools" as const,
    label: "工具总数",
    icon: WrenchIcon,
    href: "/workspace/admin/tools",
    color: "text-orange-500",
  },
  {
    key: "pending_applications" as const,
    label: "待审批申请",
    icon: ClipboardCheckIcon,
    href: "/workspace/admin/visibility-applications",
    color: "text-yellow-500",
  },
  {
    key: "total_resources" as const,
    label: "资源总数",
    icon: WrenchIcon,
    href: "/workspace/admin/resources",
    color: "text-indigo-500",
  },
  {
    key: "audit_logs" as const,
    label: "审计日志",
    icon: ScrollTextIcon,
    href: "/workspace/admin/audit-logs",
    color: "text-slate-500",
  },
];

export default function AdminDashboardPage() {
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
          <h1 className="text-xl font-semibold">管理后台</h1>
          <p className="text-muted-foreground mt-0.5 text-sm">
            管理用户、部门和系统工具
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-sm">
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
                    <CardTitle className="text-sm font-medium">
                      {card.label}
                    </CardTitle>
                    <card.icon className={`h-4 w-4 ${card.color}`} />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {stats?.[card.key] ?? 0}
                    </div>
                    <CardDescription className="text-xs">
                      点击查看详情
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
