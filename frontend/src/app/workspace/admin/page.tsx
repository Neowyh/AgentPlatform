"use client";

import { Building2Icon, ShieldIcon, UsersIcon, WrenchIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getAdminStats, type AdminStats } from "@/core/admin/api";

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
    key: "total_agents" as const,
    label: "智能体总数",
    icon: ShieldIcon,
    href: "/workspace/agents",
    color: "text-purple-500",
  },
  {
    key: "total_skills" as const,
    label: "技能总数",
    icon: WrenchIcon,
    href: "/workspace/admin/tools",
    color: "text-orange-500",
  },
];

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex size-full flex-col">
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
        {loading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-sm">
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {statCards.map((card) => (
              <Link key={card.key} href={card.href}>
                <Card className="transition-shadow hover:shadow-md">
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
