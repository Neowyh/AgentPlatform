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
import { useRouter } from "next/navigation";
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

export default function DepartmentsPage() {
  const { user } = useAuth();
  const router = useRouter();
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
  if (
    user?.system_role !== "super_admin" &&
    user?.system_role !== "department_admin"
  ) {
    router.replace("/workspace");
    return null;
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error("请输入部门名称");
      return;
    }
    setSubmitting(true);
    try {
      await createDepartment({
        name: name.trim(),
        description: description.trim(),
      });
      toast.success("部门已创建");
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
      toast.error("请输入部门名称");
      return;
    }
    setSubmitting(true);
    try {
      await updateDepartment(editDept.id, {
        name: name.trim(),
        description: description.trim(),
      });
      toast.success("部门已更新");
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
        if (!confirm("确定要删除该部门吗？此操作不可撤销。")) {
          setReallocLoading(false);
          return;
        }
        setDeletingId(deptId);
        try {
          await deleteDepartment(deptId);
          toast.success("部门已删除");
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
      toast.success("部门已删除");
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
            <h1 className="text-xl font-semibold">部门管理</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              管理组织部门和资源分配
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
            新建部门
          </Button>
        )}
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
        ) : departments.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <Building2Icon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground text-sm">暂无部门</p>
            <Button
              variant="outline"
              onClick={() => {
                setName("");
                setDescription("");
                setCreateOpen(true);
              }}
            >
              <PlusIcon className="mr-1.5 h-4 w-4" />
              新建部门
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
                        <CardTitle className="text-base">{dept.name}</CardTitle>
                        <CardDescription className="line-clamp-1">
                          {dept.description || "暂无描述"}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {user?.system_role === "super_admin" && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => openEditDialog(dept)}
                          title="编辑"
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
                          title="删除"
                          data-testid="department-delete-button"
                        >
                          <Trash2Icon className="text-destructive h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1">
                      <UsersIcon className="text-muted-foreground h-4 w-4" />
                      <span>{dept.member_count} 成员</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Building2Icon className="text-muted-foreground h-4 w-4" />
                      <span>{dept.agent_count} 智能体</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <WrenchIcon className="text-muted-foreground h-4 w-4" />
                      <span>{dept.skill_count} 技能</span>
                    </div>
                  </div>
                  <div className="text-muted-foreground mt-2 text-xs">
                    创建于 {new Date(dept.created_at).toLocaleDateString()}
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
            <DialogTitle>新建部门</DialogTitle>
            <DialogDescription>创建一个新的组织部门</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">部门名称</label>
              <Input
                placeholder="请输入部门名称"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">部门描述</label>
              <Textarea
                placeholder="请输入部门描述（可选）"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting ? "创建中..." : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑部门</DialogTitle>
            <DialogDescription>修改部门信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">部门名称</label>
              <Input
                placeholder="请输入部门名称"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">部门描述</label>
              <Textarea
                placeholder="请输入部门描述（可选）"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button onClick={handleEdit} disabled={submitting}>
              {submitting ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resource Reallocation Dialog */}
      <Dialog open={reallocDialogOpen} onOpenChange={setReallocDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>删除部门 - 资源重分配</DialogTitle>
            <DialogDescription>
              部门 &quot;{reallocDeptName}&quot; 包含{" "}
              {reallocResources?.length ?? 0} 个资源，请选择如何处理这些资源。
            </DialogDescription>
          </DialogHeader>

          {reallocLoading ? (
            <div className="text-muted-foreground py-8 text-center text-sm">
              加载资源列表中...
            </div>
          ) : (
            <div className="space-y-4">
              {/* Resource List */}
              <div className="space-y-2">
                <label className="text-sm font-medium">受影响的资源</label>
                <div className="max-h-60 overflow-y-auto rounded-md border p-2">
                  {reallocResources && reallocResources.length > 0 ? (
                    <div className="space-y-2">
                      {reallocResources.map((resource) => (
                        <div
                          key={resource.id}
                          className="bg-muted/50 flex items-center justify-between rounded-md px-3 py-2 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              {resource.resource_id}
                            </span>
                            <span className="text-muted-foreground">
                              ({resource.resource_type})
                            </span>
                          </div>
                          <span className="text-muted-foreground text-xs">
                            {resource.visibility === "department"
                              ? "部门级"
                              : "私有"}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-muted-foreground py-4 text-center text-sm">
                      暂无资源
                    </div>
                  )}
                </div>
              </div>

              {/* Target Department Selection */}
              <div className="space-y-2">
                <label className="text-sm font-medium">资源处理方式</label>
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
                    <label htmlFor="realloc-dept" className="text-sm">
                      重分配到目标部门
                    </label>
                  </div>

                  {reallocTargetDeptId && (
                    <select
                      value={reallocTargetDeptId}
                      onChange={(e) => setReallocTargetDeptId(e.target.value)}
                      className="ml-6 h-9 w-full max-w-xs rounded-md border bg-transparent px-3 text-sm"
                    >
                      <option value="">请选择目标部门</option>
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
                    <label htmlFor="realloc-private" className="text-sm">
                      降级为私有（资源变为私有，部门关联清除）
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
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleReallocDelete}
              disabled={reallocLoading || reallocSubmitting}
            >
              {reallocSubmitting ? "删除中..." : "确认删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
