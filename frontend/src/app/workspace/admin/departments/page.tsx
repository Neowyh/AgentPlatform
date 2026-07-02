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
    if (!confirm("确定要删除该部门吗？此操作不可撤销。")) return;
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
    </div>
  );
}
