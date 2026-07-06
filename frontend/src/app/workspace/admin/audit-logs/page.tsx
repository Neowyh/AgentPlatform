"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listAuditLogs } from "@/core/audit-logs/api";
import type { AuditLog } from "@/core/audit-logs/types";
import { useAuth } from "@/core/auth/AuthProvider";

const ACTION_LABELS: Record<string, string> = {
  create: "创建",
  update: "更新",
  delete: "删除",
  review: "审批",
  approve: "批准",
  reject: "驳回",
  withdraw: "撤回",
  grant: "授权",
  revoke: "撤销",
  apply: "申请",
  withdrawal: "撤回",
};

const ACTION_BADGE_CLASSES: Record<string, string> = {
  create:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100 border-green-200 dark:border-green-800",
  update:
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100 border-blue-200 dark:border-blue-800",
  delete:
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100 border-red-200 dark:border-red-800",
  review: "bg-secondary text-secondary-foreground",
  approve: "bg-secondary text-secondary-foreground",
  reject: "bg-destructive text-destructive-foreground",
  withdraw: "bg-destructive text-destructive-foreground",
  withdrawal: "bg-destructive text-destructive-foreground",
  grant: "bg-secondary text-secondary-foreground",
  revoke: "bg-destructive text-destructive-foreground",
  apply:
    "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100 border-amber-200 dark:border-amber-800",
};

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  tool: "工具",
  skill: "Skill",
  workflow: "工作流",
  agent: "智能体",
};

export default function AuditLogsPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [filterActorId, setFilterActorId] = useState("");
  const [filterAction, setFilterAction] = useState("all");
  const [filterResourceType, setFilterResourceType] = useState("all");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");

  const [detailLog, setDetailLog] = useState<AuditLog | null>(null);
  const [detailJson, setDetailJson] = useState("");

  const pageSize = 20;

  const fetchLogs = useCallback(async () => {
    try {
      const params: Parameters<typeof listAuditLogs>[0] = {
        page,
        page_size: pageSize,
      };
      if (filterActorId) params.actor_id = filterActorId;
      if (filterAction !== "all") params.action = filterAction;
      if (filterResourceType !== "all")
        params.resource_type = filterResourceType;
      if (filterStartDate) params.start_date = filterStartDate;
      if (filterEndDate) params.end_date = filterEndDate;

      const data = await listAuditLogs(params);
      setLogs(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [
    filterActorId,
    filterAction,
    filterResourceType,
    filterStartDate,
    filterEndDate,
    page,
  ]);

  useEffect(() => {
    if (currentUser?.system_role !== "super_admin") {
      return;
    }

    void fetchLogs()
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [currentUser, fetchLogs]);

  if (currentUser?.system_role !== "super_admin") {
    router.replace("/workspace");
    return null;
  }

  const handleViewDetail = (log: AuditLog) => {
    setDetailLog(log);
    if (log.detail) {
      try {
        const parsed = JSON.parse(log.detail);
        setDetailJson(JSON.stringify(parsed, null, 2));
      } catch {
        setDetailJson(log.detail);
      }
    } else {
      setDetailJson("无");
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex size-full flex-col" data-testid="audit-logs-page">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-4">
          <Link
            href="/workspace/admin"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeftIcon className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-xl font-semibold">审计日志</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              浏览和查询系统操作审计记录
            </p>
          </div>
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
          <div className="flex flex-col gap-4">
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">操作者</Label>
                <Input
                  placeholder="用户 ID"
                  value={filterActorId}
                  onChange={(e) => {
                    setFilterActorId(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 w-40"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">操作类型</Label>
                <Select
                  value={filterAction}
                  onValueChange={(v) => {
                    setFilterAction(v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="h-9 w-32">
                    <SelectValue placeholder="操作类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="create">创建</SelectItem>
                    <SelectItem value="update">更新</SelectItem>
                    <SelectItem value="delete">删除</SelectItem>
                    <SelectItem value="review">审批</SelectItem>
                    <SelectItem value="approve">批准</SelectItem>
                    <SelectItem value="reject">驳回</SelectItem>
                    <SelectItem value="withdraw">撤回</SelectItem>
                    <SelectItem value="grant">授权</SelectItem>
                    <SelectItem value="revoke">撤销</SelectItem>
                    <SelectItem value="apply">申请</SelectItem>
                    <SelectItem value="withdrawal">撤回</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">资源类型</Label>
                <Select
                  value={filterResourceType}
                  onValueChange={(v) => {
                    setFilterResourceType(v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="h-9 w-28">
                    <SelectValue placeholder="资源类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="tool">工具</SelectItem>
                    <SelectItem value="skill">Skill</SelectItem>
                    <SelectItem value="workflow">工作流</SelectItem>
                    <SelectItem value="agent">智能体</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">开始时间</Label>
                <Input
                  type="datetime-local"
                  value={filterStartDate}
                  onChange={(e) => {
                    setFilterStartDate(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 w-48"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">结束时间</Label>
                <Input
                  type="datetime-local"
                  value={filterEndDate}
                  onChange={(e) => {
                    setFilterEndDate(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 w-48"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={() => {
                  setFilterActorId("");
                  setFilterAction("all");
                  setFilterResourceType("all");
                  setFilterStartDate("");
                  setFilterEndDate("");
                  setPage(1);
                }}
              >
                重置
              </Button>
              <span className="text-muted-foreground ml-auto text-sm">
                共 {total} 条
              </span>
            </div>

            {/* Logs list */}
            {logs.length === 0 ? (
              <Card>
                <CardContent className="flex h-40 items-center justify-center">
                  <p className="text-muted-foreground text-sm">
                    没有找到审计日志
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-2">
                {logs.map((log) => (
                  <Card
                    key={log.id}
                    className="cursor-pointer transition-shadow hover:shadow-md"
                    onClick={() => handleViewDetail(log)}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="font-mono text-sm">
                          {log.id.slice(0, 8)}...
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {RESOURCE_TYPE_LABELS[log.resource_type ?? ""] ??
                              log.resource_type ??
                              "—"}
                          </Badge>
                          <Badge
                            className={ACTION_BADGE_CLASSES[log.action] ?? ""}
                          >
                            {ACTION_LABELS[log.action] ?? log.action}
                          </Badge>
                        </div>
                      </div>
                      <CardDescription>
                        {new Date(log.created_at).toLocaleString()}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground text-sm">
                        <span className="font-medium">操作者:</span>{" "}
                        {log.actor_id ?? "系统"}
                        {log.resource_id ? (
                          <>
                            {" "}
                            | <span className="font-medium">资源:</span>{" "}
                            {log.resource_id}
                          </>
                        ) : null}
                        {log.ip_address ? (
                          <>
                            {" "}
                            | <span className="font-medium">IP:</span>{" "}
                            {log.ip_address}
                          </>
                        ) : null}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
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
          </div>
        )}
      </div>

      {/* Detail Dialog */}
      <Dialog
        open={!!detailLog}
        onOpenChange={(open) => !open && setDetailLog(null)}
      >
        <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>审计日志详情</DialogTitle>
            <DialogDescription>日志 ID: {detailLog?.id}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-muted-foreground text-xs">
                  操作类型
                </Label>
                <p>
                  <Badge
                    className={
                      ACTION_BADGE_CLASSES[detailLog?.action ?? ""] ?? ""
                    }
                  >
                    {ACTION_LABELS[detailLog?.action ?? ""] ??
                      detailLog?.action}
                  </Badge>
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground text-xs">
                  操作时间
                </Label>
                <p className="text-sm">
                  {detailLog?.created_at
                    ? new Date(detailLog.created_at).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground text-xs">操作者</Label>
                <p className="text-sm">{detailLog?.actor_id ?? "系统"}</p>
              </div>
              <div>
                <Label className="text-muted-foreground text-xs">IP 地址</Label>
                <p className="text-sm">{detailLog?.ip_address ?? "—"}</p>
              </div>
              <div>
                <Label className="text-muted-foreground text-xs">
                  资源类型
                </Label>
                <p className="text-sm">
                  {RESOURCE_TYPE_LABELS[detailLog?.resource_type ?? ""] ??
                    detailLog?.resource_type ??
                    "—"}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground text-xs">资源 ID</Label>
                <p className="text-sm">{detailLog?.resource_id ?? "—"}</p>
              </div>
            </div>
            <div>
              <Label className="text-muted-foreground text-xs">详细内容</Label>
              <pre className="bg-muted mt-1 max-h-60 overflow-auto rounded-md p-3 text-xs">
                {detailJson}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
