"use client";

import { ArrowLeftIcon, ShieldOffIcon, UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  disableUser,
  listDepartments,
  listUsers,
  updateUserRole,
} from "@/core/admin/api";
import type { Department, User, UserRole } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";

const ROLE_LABELS: Record<UserRole, string> = {
  user: "普通用户",
  department_admin: "部门管理员",
  super_admin: "超级管理员",
};

const ROLE_VARIANTS: Record<UserRole, "default" | "secondary" | "destructive"> =
  {
    user: "secondary",
    department_admin: "default",
    super_admin: "destructive",
  };

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDept, setFilterDept] = useState<string>("all");
  const [filterRole, setFilterRole] = useState<string>("all");
  const [disablingId, setDisablingId] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const params: { department_id?: string; role?: string } = {};
      if (filterDept !== "all") params.department_id = filterDept;
      if (filterRole !== "all") params.role = filterRole;
      const data = await listUsers(params);
      setUsers(data.users);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [filterDept, filterRole]);

  useEffect(() => {
    // Only fetch data for authorized users
    if (currentUser?.system_role !== "super_admin") return;

    Promise.all([
      fetchUsers(),
      listDepartments().then((data) => setDepartments(data.departments)),
    ])
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [fetchUsers, currentUser]);

  // Role check: only super_admin can access admin pages
  if (currentUser?.system_role !== "super_admin") {
    router.replace("/workspace");
    return null;
  }

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (userId === currentUser?.id) {
      toast.error("不能修改自己的角色");
      return;
    }
    const user = users.find((u) => u.id === userId);
    if (!user) return;
    const currentLabel = ROLE_LABELS[user.role] ?? user.role;
    const newLabel = ROLE_LABELS[newRole as UserRole] ?? newRole;
    // Confirm sensitive role changes (promoting to super_admin or demoting from super_admin)
    if (newRole === "super_admin" || user.role === "super_admin") {
      if (
        !confirm(
          `确定要将用户 "${user.username}" 的角色从 ${currentLabel} 变更为 ${newLabel} 吗？`,
        )
      )
        return;
    }
    try {
      await updateUserRole(userId, newRole);
      toast.success("用户角色已更新");
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDisable = async (userId: string) => {
    if (userId === currentUser?.id) {
      toast.error("不能禁用自己的账号");
      return;
    }
    if (!confirm("确定要禁用该用户吗？")) return;
    setDisablingId(userId);
    try {
      await disableUser(userId);
      toast.success("用户已禁用");
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setDisablingId(null);
    }
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
            <h1 className="text-xl font-semibold">用户管理</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              管理系统用户和角色权限
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 border-b px-6 py-3">
        <Select value={filterDept} onValueChange={setFilterDept}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="筛选部门" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部部门</SelectItem>
            {departments.map((dept) => (
              <SelectItem key={dept.id} value={dept.id}>
                {dept.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterRole} onValueChange={setFilterRole}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="筛选角色" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部角色</SelectItem>
            <SelectItem value="user">普通用户</SelectItem>
            <SelectItem value="department_admin">部门管理员</SelectItem>
            <SelectItem value="super_admin">超级管理员</SelectItem>
          </SelectContent>
        </Select>
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
        ) : users.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <UserIcon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground text-sm">暂无用户</p>
          </div>
        ) : (
          <div className="grid gap-4" data-testid="user-list">
            {users.map((user) => {
              const isSelf = user.id === currentUser?.id;
              return (
                <Card key={user.id} data-testid="user-card">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="bg-primary/10 flex h-10 w-10 items-center justify-center rounded-full">
                          <UserIcon className="text-primary h-5 w-5" />
                        </div>
                        <div>
                          <CardTitle className="text-base">
                            {user.username}
                          </CardTitle>
                          <CardDescription>
                            {departments.find(
                              (d) => d.id === user.department_id,
                            )?.name ?? "未分配部门"}
                          </CardDescription>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isSelf && <Badge variant="outline">当前用户</Badge>}
                        <Badge variant={ROLE_VARIANTS[user.role]}>
                          {ROLE_LABELS[user.role]}
                        </Badge>
                        {user.disabled && (
                          <Badge variant="destructive">已禁用</Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="text-muted-foreground text-xs">
                        <span>
                          创建于{" "}
                          {new Date(user.created_at).toLocaleDateString()}
                        </span>
                        {user.last_login && (
                          <span className="ml-4">
                            最后登录{" "}
                            {new Date(user.last_login).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Select
                          value={user.role}
                          onValueChange={(value) =>
                            handleRoleChange(user.id, value)
                          }
                          disabled={isSelf}
                          data-testid="user-role-select"
                        >
                          <SelectTrigger className="w-36">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="user">普通用户</SelectItem>
                            <SelectItem value="department_admin">
                              部门管理员
                            </SelectItem>
                            <SelectItem value="super_admin">
                              超级管理员
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDisable(user.id)}
                          disabled={isSelf || disablingId === user.id}
                          title={isSelf ? "不能禁用自己的账号" : "禁用用户"}
                          data-testid="user-disable-button"
                        >
                          <ShieldOffIcon className="text-destructive h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
