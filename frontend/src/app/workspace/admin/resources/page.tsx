"use client";

import {
  ArchiveIcon,
  ArrowLeftIcon,
  BanIcon,
  BoxIcon,
  RefreshCwIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  archiveResource,
  listResources,
  restoreResource,
  suspendResource,
} from "@/core/admin/api";
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

const LIFECYCLE_LABELS: Record<string, string> = {
  active: "启用",
  archived: "已归档",
  suspended: "已下架",
};

const LIFECYCLE_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-800",
  suspended: "bg-red-100 text-red-800",
};

const RESOURCE_UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

const PAGE_SIZE = 50;

function isCanonicalResource(resource: AdminResource): boolean {
  return RESOURCE_UUID_PATTERN.test(resource.id);
}

export default function ResourcesPage() {
  const { user } = useAuth();
  const [resources, setResources] = useState<AdminResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState("");
  const [actingOn, setActingOn] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = useCallback(() => {
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
  }, [filterType, page]);

  useEffect(() => {
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;
    reload();
  }, [user, reload]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const isSuperAdmin = user?.system_role === "super_admin";

  const handleLifecycleAction = useCallback(
    async (
      resource: AdminResource,
      action: "archive" | "suspend" | "restore",
    ) => {
      setActingOn(resource.id);
      setActionError(null);
      try {
        if (action === "archive") await archiveResource(resource.id);
        else if (action === "suspend") await suspendResource(resource.id);
        else await restoreResource(resource.id);
        reload();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : String(err));
      } finally {
        setActingOn(null);
      }
    },
    [reload],
  );

  const renderActions = (resource: AdminResource) => {
    if (!isCanonicalResource(resource)) return null;
    const lifecycle = resource.lifecycle_status ?? "active";
    return (
      <div className="flex items-center justify-end gap-2">
        {isSuperAdmin && lifecycle === "active" && (
          <Button
            variant="outline"
            size="sm"
            disabled={actingOn === resource.id}
            onClick={() => handleLifecycleAction(resource, "suspend")}
          >
            <BanIcon className="h-3.5 w-3.5" />
            下架
          </Button>
        )}
        {isSuperAdmin && lifecycle === "suspended" && (
          <Button
            variant="outline"
            size="sm"
            disabled={actingOn === resource.id}
            onClick={() => handleLifecycleAction(resource, "restore")}
          >
            <RefreshCwIcon className="h-3.5 w-3.5" />
            恢复
          </Button>
        )}
        {lifecycle !== "suspended" && (
          <Button
            variant="outline"
            size="sm"
            disabled={actingOn === resource.id}
            onClick={() => handleLifecycleAction(resource, "archive")}
          >
            <ArchiveIcon className="h-3.5 w-3.5" />
            归档
          </Button>
        )}
      </div>
    );
  };

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

        {actionError && (
          <div className="text-destructive mb-4 text-sm">{actionError}</div>
        )}

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
                    <th className="px-4 py-3 font-medium">状态</th>
                    <th className="px-4 py-3 font-medium">创建者</th>
                    <th className="px-4 py-3 font-medium">创建时间</th>
                    <th className="px-4 py-3 text-right">操作</th>
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
                      <td className="px-4 py-3">
                        {isCanonicalResource(r) && r.lifecycle_status && (
                          <Badge
                            className={
                              LIFECYCLE_STYLES[r.lifecycle_status] ?? ""
                            }
                            variant="outline"
                          >
                            {LIFECYCLE_LABELS[r.lifecycle_status] ??
                              r.lifecycle_status}
                          </Badge>
                        )}
                      </td>
                      <td className="text-muted-foreground px-4 py-3">
                        {r.owner_username ?? "-"}
                      </td>
                      <td className="text-muted-foreground px-4 py-3">
                        {r.created_at
                          ? new Date(r.created_at).toLocaleDateString("zh-CN")
                          : "-"}
                      </td>
                      <td className="px-4 py-3">{renderActions(r)}</td>
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
