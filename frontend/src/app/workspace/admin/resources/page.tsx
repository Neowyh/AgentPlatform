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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  archiveResource,
  listResources,
  listUsers,
  restoreResource,
  suspendResource,
} from "@/core/admin/api";
import type { AdminResource, User } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

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
  const { t } = useI18n();
  const { user } = useAuth();

  const RESOURCE_TYPES = [
    { value: "all", label: t.admin.resources.allTypesLabel },
    { value: "agent", label: t.admin.resources.agentLabel },
    { value: "tool", label: t.admin.resources.toolLabel },
    { value: "skill", label: "Skill" },
    { value: "workflow", label: t.admin.resources.workflowLabel },
  ];

  const VISIBILITY_LABELS: Record<string, string> = {
    private: t.admin.resources.privateLabel,
    department: t.admin.resources.departmentLabel,
    public: t.admin.resources.publicLabel,
  };

  const LIFECYCLE_LABELS: Record<string, string> = {
    active: t.admin.resources.activeLabel,
    archived: t.admin.resources.archivedLabel,
    suspended: t.admin.resources.suspendedLabel,
  };

  const [resources, setResources] = useState<AdminResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterType, setFilterType] = useState("all");
  const [filterVisibility, setFilterVisibility] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterOwner, setFilterOwner] = useState("all");
  const [users, setUsers] = useState<User[]>([]);
  const [actingOn, setActingOn] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    listResources({
      resource_type: filterType !== "all" ? filterType : undefined,
      visibility: filterVisibility !== "all" ? filterVisibility : undefined,
      lifecycle_status: filterStatus !== "all" ? filterStatus : undefined,
      owner_id: filterOwner !== "all" ? filterOwner : undefined,
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
  }, [filterType, filterVisibility, filterStatus, filterOwner, page]);

  useEffect(() => {
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;
    reload();
  }, [user, reload]);

  useEffect(() => {
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;
    listUsers({ limit: 500 })
      .then((data) => setUsers(data.users))
      .catch(() => setUsers([]));
  }, [user]);

  const handleFilterChange = (setter: (value: string) => void) => {
    return (value: string) => {
      setter(value);
      setPage(1);
    };
  };

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
            {t.admin.resources.suspendAction}
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
            {t.admin.resources.restoreAction}
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
            {t.admin.resources.archiveAction}
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
            <h1 className="type-page-title font-semibold">
              {t.admin.resources.pageTitle}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {t.admin.resources.totalCount(total)}
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Select
            value={filterType}
            onValueChange={handleFilterChange(setFilterType)}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder={t.admin.resources.typeLabel} />
            </SelectTrigger>
            <SelectContent>
              {RESOURCE_TYPES.map((rt) => (
                <SelectItem key={rt.value} value={rt.value}>
                  {rt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filterVisibility}
            onValueChange={handleFilterChange(setFilterVisibility)}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder={t.admin.resources.visibilityLabel} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t.admin.resources.allVisibilityLabel}
              </SelectItem>
              <SelectItem value="private">
                {t.admin.resources.privateLabel}
              </SelectItem>
              <SelectItem value="department">
                {t.admin.resources.departmentLabel}
              </SelectItem>
              <SelectItem value="public">
                {t.admin.resources.publicLabel}
              </SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filterStatus}
            onValueChange={handleFilterChange(setFilterStatus)}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder={t.admin.resources.statusLabel} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t.admin.resources.allStatusLabel}
              </SelectItem>
              <SelectItem value="active">
                {t.admin.resources.activeLabel}
              </SelectItem>
              <SelectItem value="archived">
                {t.admin.resources.archivedLabel}
              </SelectItem>
              <SelectItem value="suspended">
                {t.admin.resources.suspendedLabel}
              </SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filterOwner}
            onValueChange={handleFilterChange(setFilterOwner)}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder={t.admin.resources.ownerLabel} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t.admin.resources.allOwnersLabel}
              </SelectItem>
              {users.map((u) => (
                <SelectItem key={u.id} value={u.id}>
                  {u.username}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {actionError && (
          <div className="text-destructive type-body mb-4">{actionError}</div>
        )}

        {loading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.resources.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error}
          </div>
        ) : resources.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <BoxIcon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground type-body">
              {t.admin.resources.empty}
            </p>
          </div>
        ) : (
          <>
            <div
              className="overflow-x-auto rounded-md border"
              data-testid="resource-table"
            >
              <table className="type-body w-full">
                <thead>
                  <tr className="bg-muted/50 border-b text-left">
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.typeLabel}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.nameLabel}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.visibilityLabel}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.statusLabel}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.ownerLabel}
                    </th>
                    <th className="px-4 py-3 font-medium">
                      {t.admin.resources.createdAtLabel}
                    </th>
                    <th className="px-4 py-3 text-right">
                      {t.admin.resources.actionsLabel}
                    </th>
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
                  {t.admin.resources.prevPage}
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
                  {t.admin.resources.nextPage}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
