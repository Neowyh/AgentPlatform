"use client";

import {
  ArrowLeftIcon,
  Building2Icon,
  EditIcon,
  PlusIcon,
  Trash2Icon,
  UsersIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

// Badge available for future use
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  createDepartment,
  deleteDepartment,
  getDepartmentResources,
  listDepartments,
  updateDepartment,
} from "@/core/admin/api";
import type { Department } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

export default function DepartmentsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editDept, setEditDept] = useState<Department | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Resource reallocation dialog state
  const [reallocDialogOpen, setReallocDialogOpen] = useState(false);
  const [reallocDeptId, setReallocDeptId] = useState<string | null>(null);
  const [reallocResources, setReallocResources] = useState<Array<{
    id: string;
    resource_type: string;
    resource_id: string;
    visibility: string;
    owner_id: string;
  }> | null>(null);
  const [reallocDeptName, setReallocDeptName] = useState("");
  const [reallocLoading, setReallocLoading] = useState(false);
  const [reallocTargetDeptId, setReallocTargetDeptId] = useState<string>("");
  const [reallocSubmitting, setReallocSubmitting] = useState(false);

  const fetchDepartments = useCallback(async () => {
    try {
      const data = await listDepartments();
      setDepartments(data.departments);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    // Only fetch data for authorized users
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;

    void fetchDepartments().finally(() => setLoading(false));
  }, [fetchDepartments, user]);

  // Role check: only super_admin and department_admin can access admin pages
  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error(t.admin.departments.enterDepartmentName);
      return;
    }
    setSubmitting(true);
    try {
      await createDepartment({
        name: name.trim(),
        description: description.trim(),
      });
      toast.success(t.admin.departments.createdSuccess);
      setCreateOpen(false);
      setName("");
      setDescription("");
      await fetchDepartments();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async () => {
    if (!editDept || !name.trim()) {
      toast.error(t.admin.departments.enterDepartmentName);
      return;
    }
    setSubmitting(true);
    try {
      await updateDepartment(editDept.id, {
        name: name.trim(),
        description: description.trim(),
      });
      toast.success(t.admin.departments.updatedSuccess);
      setEditOpen(false);
      setEditDept(null);
      setName("");
      setDescription("");
      await fetchDepartments();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (deptId: string) => {
    setReallocLoading(true);
    setReallocDeptId(deptId);
    setReallocResources(null);
    setReallocTargetDeptId("");

    try {
      const data = await getDepartmentResources(deptId);
      setReallocResources(data.resources);
      setReallocDeptName(data.department_name);

      if (data.resources.length === 0) {
        // No resources, proceed with direct delete
        if (!confirm(t.admin.departments.deleteConfirm)) {
          setReallocLoading(false);
          return;
        }
        setDeletingId(deptId);
        try {
          await deleteDepartment(deptId);
          toast.success(t.admin.departments.deletedSuccess);
          await fetchDepartments();
        } catch (err) {
          toast.error(err instanceof Error ? err.message : String(err));
        } finally {
          setDeletingId(null);
        }
      } else {
        // Has resources, show reallocation dialog
        setReallocDialogOpen(true);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setReallocLoading(false);
    }
  };

  const handleReallocDelete = async () => {
    if (!reallocDeptId) return;

    setReallocSubmitting(true);
    try {
      await deleteDepartment(reallocDeptId, reallocTargetDeptId || undefined);
      toast.success(t.admin.departments.deletedSuccess);
      setReallocDialogOpen(false);
      setReallocDeptId(null);
      setReallocResources(null);
      await fetchDepartments();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setReallocSubmitting(false);
    }
  };

  const openEditDialog = (dept: Department) => {
    setEditDept(dept);
    setName(dept.name);
    setDescription(dept.description);
    setEditOpen(true);
  };

  return (
    <div className="flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Link href="/workspace/admin">
            <Button variant="ghost" size="icon-sm">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="type-page-title font-semibold">
              {t.admin.departments.pageTitle}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {t.admin.departments.pageDescription}
            </p>
          </div>
        </div>
        {user?.system_role === "super_admin" && (
          <Button
            onClick={() => {
              setName("");
              setDescription("");
              setCreateOpen(true);
            }}
          >
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.admin.departments.createDepartment}
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.departments.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error}
          </div>
        ) : departments.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <Building2Icon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground type-body">
              {t.admin.departments.noDepartments}
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setName("");
                setDescription("");
                setCreateOpen(true);
              }}
            >
              <PlusIcon className="mr-1.5 h-4 w-4" />
              {t.admin.departments.createDepartment}
            </Button>
          </div>
        ) : (
          <div
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="department-list"
          >
            {departments.map((dept) => (
              <Card
                key={dept.id}
                className="transition-shadow hover:shadow-md"
                data-testid="department-card"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className="bg-primary/10 flex h-9 w-9 items-center justify-center rounded-lg">
                        <Building2Icon className="text-primary h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="type-body">{dept.name}</CardTitle>
                        <CardDescription className="line-clamp-1">
                          {dept.description ||
                            t.admin.departments.noDescription}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {user?.system_role === "super_admin" && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => openEditDialog(dept)}
                          title={t.admin.departments.edit}
                          data-testid="department-edit-button"
                        >
                          <EditIcon className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {user?.system_role === "super_admin" && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDelete(dept.id)}
                          disabled={deletingId === dept.id}
                          title={t.admin.departments.delete}
                          data-testid="department-delete-button"
                        >
                          <Trash2Icon className="text-destructive h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="type-body flex items-center gap-4">
                    <div className="flex items-center gap-1">
                      <UsersIcon className="text-muted-foreground h-4 w-4" />
                      <span>
                        {t.admin.departments.memberCount(dept.member_count)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Building2Icon className="text-muted-foreground h-4 w-4" />
                      <span>
                        {t.admin.departments.agentCount(dept.agent_count)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <WrenchIcon className="text-muted-foreground h-4 w-4" />
                      <span>
                        {t.admin.departments.skillCount(dept.skill_count)}
                      </span>
                    </div>
                  </div>
                  <div className="text-muted-foreground type-body mt-2">
                    {t.admin.departments.createdAt(
                      new Date(dept.created_at).toLocaleDateString(),
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.admin.departments.createDepartment}</DialogTitle>
            <DialogDescription>
              {t.admin.departments.createDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="type-body font-medium">
                {t.admin.departments.nameLabel}
              </label>
              <Input
                placeholder={t.admin.departments.enterDepartmentName}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="type-body font-medium">
                {t.admin.departments.descriptionLabel}
              </label>
              <Textarea
                placeholder={t.admin.departments.descriptionPlaceholder}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              {t.admin.departments.cancel}
            </Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting
                ? t.admin.departments.creating
                : t.admin.departments.create}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.admin.departments.editDepartment}</DialogTitle>
            <DialogDescription>
              {t.admin.departments.editDescription}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="type-body font-medium">
                {t.admin.departments.nameLabel}
              </label>
              <Input
                placeholder={t.admin.departments.enterDepartmentName}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="type-body font-medium">
                {t.admin.departments.descriptionLabel}
              </label>
              <Textarea
                placeholder={t.admin.departments.descriptionPlaceholder}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              {t.admin.departments.cancel}
            </Button>
            <Button onClick={handleEdit} disabled={submitting}>
              {submitting
                ? t.admin.departments.saving
                : t.admin.departments.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resource Reallocation Dialog */}
      <Dialog open={reallocDialogOpen} onOpenChange={setReallocDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t.admin.departments.reallocTitle}</DialogTitle>
            <DialogDescription>
              {t.admin.departments.reallocDescription(
                reallocDeptName,
                reallocResources?.length ?? 0,
              )}
            </DialogDescription>
          </DialogHeader>

          {reallocLoading ? (
            <div className="text-muted-foreground type-body py-8 text-center">
              {t.admin.departments.loadingResources}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Resource List */}
              <div className="space-y-2">
                <label className="type-body font-medium">
                  {t.admin.departments.affectedResources}
                </label>
                <div className="max-h-60 overflow-y-auto rounded-md border p-2">
                  {reallocResources && reallocResources.length > 0 ? (
                    <div className="space-y-2">
                      {reallocResources.map((resource) => (
                        <div
                          key={resource.id}
                          className="bg-muted/50 type-body flex items-center justify-between rounded-md px-3 py-2"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              {resource.resource_id}
                            </span>
                            <span className="text-muted-foreground">
                              ({resource.resource_type})
                            </span>
                          </div>
                          <span className="text-muted-foreground type-body">
                            {resource.visibility === "department"
                              ? t.admin.departments.visibilityDepartment
                              : t.admin.departments.visibilityPrivate}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-muted-foreground type-body py-4 text-center">
                      {t.admin.departments.noResources}
                    </div>
                  )}
                </div>
              </div>

              {/* Target Department Selection */}
              <div className="space-y-2">
                <label className="type-body font-medium">
                  {t.admin.departments.reallocMethodLabel}
                </label>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      id="realloc-dept"
                      name="realloc-method"
                      checked={reallocTargetDeptId !== ""}
                      onChange={() => {
                        if (departments.length > 0) {
                          const firstOtherDept = departments.find(
                            (d) => d.id !== reallocDeptId,
                          );
                          if (firstOtherDept) {
                            setReallocTargetDeptId(firstOtherDept.id);
                          }
                        }
                      }}
                      className="h-4 w-4"
                    />
                    <label htmlFor="realloc-dept" className="type-body">
                      {t.admin.departments.reassignToDept}
                    </label>
                  </div>

                  {reallocTargetDeptId && (
                    <select
                      value={reallocTargetDeptId}
                      onChange={(e) => setReallocTargetDeptId(e.target.value)}
                      className="type-body ml-6 h-9 w-full max-w-xs rounded-md border bg-transparent px-3"
                    >
                      <option value="">
                        {t.admin.departments.selectTargetDept}
                      </option>
                      {departments
                        .filter((d) => d.id !== reallocDeptId)
                        .map((dept) => (
                          <option key={dept.id} value={dept.id}>
                            {dept.name}
                          </option>
                        ))}
                    </select>
                  )}

                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      id="realloc-private"
                      name="realloc-method"
                      checked={reallocTargetDeptId === ""}
                      onChange={() => setReallocTargetDeptId("")}
                      className="h-4 w-4"
                    />
                    <label htmlFor="realloc-private" className="type-body">
                      {t.admin.departments.downgradeToPrivate}
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setReallocDialogOpen(false);
                setReallocDeptId(null);
                setReallocResources(null);
              }}
            >
              {t.admin.departments.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleReallocDelete}
              disabled={reallocLoading || reallocSubmitting}
            >
              {reallocSubmitting
                ? t.admin.departments.deleting
                : t.admin.departments.confirmDelete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
