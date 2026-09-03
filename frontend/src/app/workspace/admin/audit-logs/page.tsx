"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
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
import { useI18n } from "@/core/i18n/hooks";

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

export default function AuditLogsPage() {
  const { user: currentUser } = useAuth();
  const { t } = useI18n();

  const actionLabels: Record<string, string> = {
    create: t.admin.auditLogs.actionCreate,
    update: t.admin.auditLogs.actionUpdate,
    delete: t.admin.auditLogs.actionDelete,
    review: t.admin.auditLogs.actionReview,
    approve: t.admin.auditLogs.actionApprove,
    reject: t.admin.auditLogs.actionReject,
    withdraw: t.admin.auditLogs.actionWithdraw,
    grant: t.admin.auditLogs.actionGrant,
    revoke: t.admin.auditLogs.actionRevoke,
    apply: t.admin.auditLogs.actionApply,
    withdrawal: t.admin.auditLogs.actionWithdrawal,
  };

  const resourceTypeLabels: Record<string, string> = {
    tool: t.admin.auditLogs.resourceTypeTool,
    skill: t.admin.auditLogs.resourceTypeSkill,
    workflow: t.admin.auditLogs.resourceTypeWorkflow,
    agent: t.admin.auditLogs.resourceTypeAgent,
  };

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

    void fetchLogs().finally(() => setLoading(false));
  }, [currentUser, fetchLogs]);

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
      setDetailJson(t.admin.auditLogs.none);
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
            <h1 className="type-page-title font-semibold">
              {t.admin.auditLogs.pageTitle}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {t.admin.auditLogs.pageDescription}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.auditLogs.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <Label className="type-body">
                  {t.admin.auditLogs.operatorLabel}
                </Label>
                <Input
                  placeholder={t.admin.auditLogs.userIdPlaceholder}
                  value={filterActorId}
                  onChange={(e) => {
                    setFilterActorId(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 w-40"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="type-body">
                  {t.admin.auditLogs.actionTypeLabel}
                </Label>
                <Select
                  value={filterAction}
                  onValueChange={(v) => {
                    setFilterAction(v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="h-9 w-32">
                    <SelectValue
                      placeholder={t.admin.auditLogs.actionTypeLabel}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t.admin.auditLogs.all}</SelectItem>
                    <SelectItem value="create">
                      {t.admin.auditLogs.actionCreate}
                    </SelectItem>
                    <SelectItem value="update">
                      {t.admin.auditLogs.actionUpdate}
                    </SelectItem>
                    <SelectItem value="delete">
                      {t.admin.auditLogs.actionDelete}
                    </SelectItem>
                    <SelectItem value="review">
                      {t.admin.auditLogs.actionReview}
                    </SelectItem>
                    <SelectItem value="approve">
                      {t.admin.auditLogs.actionApprove}
                    </SelectItem>
                    <SelectItem value="reject">
                      {t.admin.auditLogs.actionReject}
                    </SelectItem>
                    <SelectItem value="withdraw">
                      {t.admin.auditLogs.actionWithdraw}
                    </SelectItem>
                    <SelectItem value="grant">
                      {t.admin.auditLogs.actionGrant}
                    </SelectItem>
                    <SelectItem value="revoke">
                      {t.admin.auditLogs.actionRevoke}
                    </SelectItem>
                    <SelectItem value="apply">
                      {t.admin.auditLogs.actionApply}
                    </SelectItem>
                    <SelectItem value="withdrawal">
                      {t.admin.auditLogs.actionWithdrawal}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="type-body">
                  {t.admin.auditLogs.resourceTypeLabel}
                </Label>
                <Select
                  value={filterResourceType}
                  onValueChange={(v) => {
                    setFilterResourceType(v);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="h-9 w-28">
                    <SelectValue
                      placeholder={t.admin.auditLogs.resourceTypeLabel}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t.admin.auditLogs.all}</SelectItem>
                    <SelectItem value="tool">
                      {t.admin.auditLogs.resourceTypeTool}
                    </SelectItem>
                    <SelectItem value="skill">
                      {t.admin.auditLogs.resourceTypeSkill}
                    </SelectItem>
                    <SelectItem value="workflow">
                      {t.admin.auditLogs.resourceTypeWorkflow}
                    </SelectItem>
                    <SelectItem value="agent">
                      {t.admin.auditLogs.resourceTypeAgent}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="type-body">
                  {t.admin.auditLogs.startTimeLabel}
                </Label>
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
                <Label className="type-body">
                  {t.admin.auditLogs.endTimeLabel}
                </Label>
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
                {t.admin.auditLogs.reset}
              </Button>
              <span className="text-muted-foreground type-body ml-auto">
                {t.admin.auditLogs.totalCount(total)}
              </span>
            </div>

            {/* Logs list */}
            {logs.length === 0 ? (
              <Card>
                <CardContent className="flex h-40 items-center justify-center">
                  <p className="text-muted-foreground type-body">
                    {t.admin.auditLogs.emptyState}
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
                        <CardTitle className="type-body font-mono">
                          {log.id.slice(0, 8)}...
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {resourceTypeLabels[log.resource_type ?? ""] ??
                              log.resource_type ??
                              "—"}
                          </Badge>
                          <Badge
                            className={ACTION_BADGE_CLASSES[log.action] ?? ""}
                          >
                            {actionLabels[log.action] ?? log.action}
                          </Badge>
                        </div>
                      </div>
                      <CardDescription>
                        {new Date(log.created_at).toLocaleString()}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground type-body">
                        <span className="font-medium">
                          {t.admin.auditLogs.operatorLabel}:
                        </span>{" "}
                        {log.actor_id ?? t.admin.auditLogs.system}
                        {log.resource_id ? (
                          <>
                            {" "}
                            |{" "}
                            <span className="font-medium">
                              {t.admin.auditLogs.resourceLabel}:
                            </span>{" "}
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
                  {t.admin.auditLogs.previousPage}
                </Button>
                <span className="text-muted-foreground type-body">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t.admin.auditLogs.nextPage}
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
            <DialogTitle>{t.admin.auditLogs.detailTitle}</DialogTitle>
            <DialogDescription>
              {t.admin.auditLogs.logIdLabel}: {detailLog?.id}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.actionTypeLabel}
                </Label>
                <p>
                  <Badge
                    className={
                      ACTION_BADGE_CLASSES[detailLog?.action ?? ""] ?? ""
                    }
                  >
                    {actionLabels[detailLog?.action ?? ""] ?? detailLog?.action}
                  </Badge>
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.actionTimeLabel}
                </Label>
                <p className="type-body">
                  {detailLog?.created_at
                    ? new Date(detailLog.created_at).toLocaleString()
                    : "—"}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.operatorLabel}
                </Label>
                <p className="type-body">
                  {detailLog?.actor_id ?? t.admin.auditLogs.system}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.ipAddressLabel}
                </Label>
                <p className="type-body">{detailLog?.ip_address ?? "—"}</p>
              </div>
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.resourceTypeLabel}
                </Label>
                <p className="type-body">
                  {resourceTypeLabels[detailLog?.resource_type ?? ""] ??
                    detailLog?.resource_type ??
                    "—"}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground type-body">
                  {t.admin.auditLogs.resourceIdLabel}
                </Label>
                <p className="type-body">{detailLog?.resource_id ?? "—"}</p>
              </div>
            </div>
            <div>
              <Label className="text-muted-foreground type-body">
                {t.admin.auditLogs.detailContentLabel}
              </Label>
              <pre className="bg-muted type-body mt-1 max-h-60 overflow-auto rounded-md p-3">
                {detailJson}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
