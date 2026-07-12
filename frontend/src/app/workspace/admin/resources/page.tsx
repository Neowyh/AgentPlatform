"use client";

import { ArrowLeftIcon, BoxIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { listResources } from "@/core/admin/api";
import type { AdminResource } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";

const RESOURCE_TYPES = [
  { value: "", label: "全部" },
  { value: "agent", label: "智能体" },
  { value: "tool", label: "工具" },
  { value: "skill", label: "Skill" },
  { value: "workflow", label: "工作流" },
];

const VISIBILITY_LABELS: Record<string, string> = {
  private: "私有",
  department: "部门",
  public: "公开",
};

const TYPE_STYLES: Record<string, string> = {
  agent: "bg-purple-100 text-purple-800",
  tool: "bg-orange-100 text-orange-800",
  skill: "bg-blue-100 text-blue-800",
  workflow: "bg-green-100 text-green-800",
};

const VISIBILITY_STYLES: Record<string, string> = {
  private: "bg-gray-100 text-gray-800",
  department: "bg-blue-100 text-blue-800",
  public: "bg-green-100 text-green-800",
};

const PAGE_SIZE = 50;

export default function ResourcesPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [resources, setResources] = useState<AdminResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState("");

  useEffect(() => {
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;

    setLoading(true);
    setError(null);
    listResources({
      resource_type: filterType || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((data) => {
        setResources(data.resources);
        setTotal(data.total);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [user, filterType, page]);

  if (
    user?.system_role !== "super_admin" &&
    user?.system_role !== "department_admin"
  ) {
    router.replace("/workspace");
    return null;
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex size-full flex-col">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Link href="/workspace/admin">
            <Button variant="ghost" size="icon-sm">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-semibold">资源管理</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              共 {total} 个资源
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex items-center gap-2">
          {RESOURCE_TYPES.map((t) => (
            <Button
              key={t.value}
              variant={filterType === t.value ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setFilterType(t.value);
                setPage(1);
              }}
            >
              {t.label}
            </Button>
          ))}
        </div>

        {loading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-sm">
            {error}
          </div>
        ) : resources.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <BoxIcon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground text-sm">暂无资源</p>
          </div>
        ) : (
          <>
            <div
              className="overflow-x-auto rounded-md border"
              data-testid="resource-table"
            >
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b text-left">
                    <th className="px-4 py-3 font-medium">类型</th>
                    <th className="px-4 py-3 font-medium">名称</th>
                    <th className="px-4 py-3 font-medium">可见性</th>
                    <th className="px-4 py-3 font-medium">创建者</th>
                    <th className="px-4 py-3 font-medium">创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {resources.map((r) => (
                    <tr
                      key={r.id}
                      className="hover:bg-muted/30 border-b last:border-b-0"
                      data-testid="resource-row"
                    >
                      <td className="px-4 py-3">
                        <Badge className={TYPE_STYLES[r.resource_type] ?? ""}>
                          {r.resource_type_label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-medium">{r.resource_id}</td>
                      <td className="px-4 py-3">
                        <Badge
                          className={VISIBILITY_STYLES[r.visibility] ?? ""}
                          variant="outline"
                        >
                          {VISIBILITY_LABELS[r.visibility] ?? r.visibility}
                        </Badge>
                      </td>
                      <td className="text-muted-foreground px-4 py-3">
                        {r.owner_username ?? "-"}
                      </td>
                      <td className="text-muted-foreground px-4 py-3">
                        {r.created_at
                          ? new Date(r.created_at).toLocaleDateString("zh-CN")
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  上一页
                </Button>
                <span className="text-muted-foreground text-sm">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
