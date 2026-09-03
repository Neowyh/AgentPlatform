"use client";

import {
  ArrowLeftIcon,
  PencilIcon,
  PlusIcon,
  ShieldOffIcon,
  ShieldCheckIcon,
  Trash2Icon,
  UserIcon,
} from "lucide-react";
import Link from "next/link";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import {
  createUser,
  deleteUser,
  listDepartments,
  listUsers,
  toggleUserStatus,
  updateUser,
  updateUserRole,
} from "@/core/admin/api";
import type { Department, User, UserRole } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";

const ROLE_VARIANTS: Record<UserRole, "default" | "secondary" | "destructive"> =
  {
    user: "secondary",
    department_admin: "default",
    super_admin: "destructive",
  };

export default function UsersPage() {
  const { t } = useI18n();
  const { user: currentUser } = useAuth();
  const roleLabels: Record<UserRole, string> = {
    user: t.admin.users.roleUser,
    department_admin: t.admin.users.roleDepartmentAdmin,
    super_admin: t.admin.users.roleSuperAdmin,
  };
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDept, setFilterDept] = useState<string>("all");
  const [filterRole, setFilterRole] = useState<string>("all");
  const [disablingId, setDisablingId] = useState<string | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    email: "",
    password: "",
    username: "",
    role: "user" as UserRole,
    department_id: "",
  });
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ username: "", department_id: "" });
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [deleteStrategy, setDeleteStrategy] = useState<
    "transfer" | "delete" | "soft_delete"
  >("soft_delete");
  const [deleteTargetUserId, setDeleteTargetUserId] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

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
    if (
      currentUser?.system_role !== "super_admin" &&
      currentUser?.system_role !== "department_admin"
    )
      return;

    Promise.all([
      fetchUsers(),
      listDepartments().then((data) => setDepartments(data.departments)),
    ])
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [fetchUsers, currentUser]);

  const isSuperAdmin = currentUser?.system_role === "super_admin";

  const handleRoleChange = async (userId: string, newRole: string) => {
    if (userId === currentUser?.id) {
      toast.error(t.admin.users.cannotChangeOwnRole);
      return;
    }
    const user = users.find((u) => u.id === userId);
    if (!user) return;
    const currentLabel = roleLabels[user.role] ?? user.role;
    const newLabel = roleLabels[newRole as UserRole] ?? newRole;
    if (newRole === "super_admin" || user.role === "super_admin") {
      if (
        !confirm(
          t.admin.users.roleChangeConfirm(
            user.username,
            currentLabel,
            newLabel,
          ),
        )
      )
        return;
    }
    try {
      await updateUserRole(userId, newRole);
      toast.success(t.admin.users.roleUpdated);
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  };

  const handleToggleStatus = async (
    userId: string,
    currentlyDisabled: boolean,
  ) => {
    if (userId === currentUser?.id) {
      toast.error(t.admin.users.cannotChangeOwnStatus);
      return;
    }
    const enabling = currentlyDisabled;
    if (
      !confirm(
        enabling
          ? t.admin.users.enableUserConfirm
          : t.admin.users.disableUserConfirm,
      )
    )
      return;
    setDisablingId(userId);
    try {
      await toggleUserStatus(userId);
      toast.success(
        enabling ? t.admin.users.userEnabled : t.admin.users.userDisabled,
      );
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setDisablingId(null);
    }
  };

  const handleCreate = async () => {
    if (
      !createForm.email.trim() ||
      !createForm.password.trim() ||
      !createForm.username.trim()
    ) {
      toast.error(t.admin.users.fillRequiredFields);
      return;
    }
    if (createForm.password.length < 6) {
      toast.error(t.admin.users.passwordTooShort);
      return;
    }
    setCreating(true);
    try {
      await createUser({
        email: createForm.email.trim(),
        password: createForm.password,
        username: createForm.username.trim(),
        role: createForm.role,
        department_id: createForm.department_id || undefined,
      });
      toast.success(t.admin.users.userCreated);
      setCreateDialogOpen(false);
      setCreateForm({
        email: "",
        password: "",
        username: "",
        role: "user",
        department_id: "",
      });
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setEditForm({
      username: user.username,
      department_id: user.department_id ?? "",
    });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingUser) return;
    if (!editForm.username.trim()) {
      toast.error(t.admin.users.usernameRequired);
      return;
    }
    setSaving(true);
    try {
      await updateUser(editingUser.id, {
        username: editForm.username.trim(),
        department_id: editForm.department_id || undefined,
      });
      toast.success(t.admin.users.userUpdated);
      setEditDialogOpen(false);
      setEditingUser(null);
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClick = (user: User) => {
    setDeletingUser(user);
    setDeleteStrategy("soft_delete");
    setDeleteTargetUserId("");
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingUser) return;
    setDeleteSubmitting(true);
    try {
      await deleteUser(
        deletingUser.id,
        deleteStrategy,
        deleteStrategy === "transfer"
          ? deleteTargetUserId || undefined
          : undefined,
      );
      toast.success(t.admin.users.userDeleted);
      setDeleteDialogOpen(false);
      setDeletingUser(null);
      await fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleteSubmitting(false);
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
            <h1 className="type-page-title font-semibold">
              {t.admin.users.pageTitle}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {isSuperAdmin
                ? t.admin.users.subtitleSuperAdmin
                : t.admin.users.subtitleDeptAdmin}
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-3">
          {isSuperAdmin && (
            <Select value={filterDept} onValueChange={setFilterDept}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder={t.admin.users.filterDepartment} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {t.admin.users.allDepartments}
                </SelectItem>
                {departments.map((dept) => (
                  <SelectItem key={dept.id} value={dept.id}>
                    {dept.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Select value={filterRole} onValueChange={setFilterRole}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder={t.admin.users.filterRole} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t.admin.users.allRoles}</SelectItem>
              <SelectItem value="user">{t.admin.users.roleUser}</SelectItem>
              <SelectItem value="department_admin">
                {t.admin.users.roleDepartmentAdmin}
              </SelectItem>
              {isSuperAdmin && (
                <SelectItem value="super_admin">
                  {t.admin.users.roleSuperAdmin}
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" onClick={() => setCreateDialogOpen(true)}>
          <PlusIcon className="mr-1 h-4 w-4" />
          {t.admin.users.createUser}
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.users.loading}
          </div>
        ) : error ? (
          <div className="text-destructive type-body flex h-40 items-center justify-center">
            {error}
          </div>
        ) : users.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <UserIcon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground type-body">
              {t.admin.users.noUsers}
            </p>
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
                          <CardTitle className="type-body">
                            {user.username}
                          </CardTitle>
                          <CardDescription>
                            {departments.find(
                              (d) => d.id === user.department_id,
                            )?.name ?? t.admin.users.noDepartment}
                          </CardDescription>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isSelf && (
                          <Badge variant="outline">
                            {t.admin.users.currentUserBadge}
                          </Badge>
                        )}
                        <Badge variant={ROLE_VARIANTS[user.role]}>
                          {roleLabels[user.role]}
                        </Badge>
                        {user.disabled && (
                          <Badge variant="destructive">
                            {t.admin.users.disabledBadge}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="text-muted-foreground type-body">
                        <span>
                          {t.admin.users.createdAt(
                            new Date(user.created_at).toLocaleDateString(),
                          )}
                        </span>
                        {user.last_login && (
                          <span className="ml-4">
                            {t.admin.users.lastLogin(
                              new Date(user.last_login).toLocaleDateString(),
                            )}
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
                            <SelectItem value="user">
                              {t.admin.users.roleUser}
                            </SelectItem>
                            <SelectItem value="department_admin">
                              {t.admin.users.roleDepartmentAdmin}
                            </SelectItem>
                            {isSuperAdmin && (
                              <SelectItem value="super_admin">
                                {t.admin.users.roleSuperAdmin}
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        {!isSelf && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleEdit(user)}
                            title={t.admin.users.editUser}
                            data-testid="user-edit-button"
                          >
                            <PencilIcon className="h-4 w-4" />
                          </Button>
                        )}
                        {isSuperAdmin && !isSelf && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => handleDeleteClick(user)}
                            disabled={!user.disabled}
                            title={
                              user.disabled
                                ? t.admin.users.deleteUser
                                : t.admin.users.disableFirst
                            }
                            data-testid="user-delete-button"
                          >
                            <Trash2Icon className="text-destructive h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() =>
                            handleToggleStatus(user.id, user.disabled ?? false)
                          }
                          disabled={isSelf || disablingId === user.id}
                          title={
                            isSelf
                              ? t.admin.users.cannotChangeOwnStatus
                              : user.disabled
                                ? t.admin.users.enableUser
                                : t.admin.users.disableUser
                          }
                          data-testid="user-toggle-status-button"
                        >
                          {user.disabled ? (
                            <ShieldCheckIcon className="h-4 w-4 text-green-600" />
                          ) : (
                            <ShieldOffIcon className="text-destructive h-4 w-4" />
                          )}
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

      {/* Create User Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t.admin.users.createUser}</DialogTitle>
            <DialogDescription>
              {t.admin.users.createUserDesc}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="create-email">{t.admin.users.emailLabel}</Label>
              <Input
                id="create-email"
                type="email"
                placeholder="user@example.com"
                value={createForm.email}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, email: e.target.value }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="create-password">
                {t.admin.users.passwordLabel}
              </Label>
              <Input
                id="create-password"
                type="password"
                placeholder={t.admin.users.passwordPlaceholder}
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    password: e.target.value,
                  }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="create-username">
                {t.admin.users.usernameLabel}
              </Label>
              <Input
                id="create-username"
                placeholder={t.admin.users.usernamePlaceholder}
                value={createForm.username}
                onChange={(e) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    username: e.target.value,
                  }))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label>{t.admin.users.roleLabel}</Label>
              <Select
                value={createForm.role}
                onValueChange={(value) =>
                  setCreateForm((prev) => ({
                    ...prev,
                    role: value as UserRole,
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">{t.admin.users.roleUser}</SelectItem>
                  {isSuperAdmin && (
                    <>
                      <SelectItem value="department_admin">
                        {t.admin.users.roleDepartmentAdmin}
                      </SelectItem>
                      <SelectItem value="super_admin">
                        {t.admin.users.roleSuperAdmin}
                      </SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>
            {isSuperAdmin && (
              <div className="grid gap-2">
                <Label>{t.admin.users.departmentLabel}</Label>
                <Select
                  value={createForm.department_id}
                  onValueChange={(value) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      department_id: value,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t.admin.users.departmentOptional}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((dept) => (
                      <SelectItem key={dept.id} value={dept.id}>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
              disabled={creating}
            >
              {t.admin.users.cancel}
            </Button>
            <Button onClick={handleCreate} disabled={creating}>
              {creating ? t.admin.users.creating : t.admin.users.create}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t.admin.users.editUser}</DialogTitle>
            <DialogDescription>{t.admin.users.editUserDesc}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-username">
                {t.admin.users.usernameLabel}
              </Label>
              <Input
                id="edit-username"
                placeholder={t.admin.users.usernamePlaceholder}
                value={editForm.username}
                onChange={(e) =>
                  setEditForm((prev) => ({
                    ...prev,
                    username: e.target.value,
                  }))
                }
              />
            </div>
            {isSuperAdmin && (
              <div className="grid gap-2">
                <Label>{t.admin.users.departmentLabel}</Label>
                <Select
                  value={editForm.department_id}
                  onValueChange={(value) =>
                    setEditForm((prev) => ({
                      ...prev,
                      department_id: value,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={t.admin.users.departmentOptional}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((dept) => (
                      <SelectItem key={dept.id} value={dept.id}>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
              disabled={saving}
            >
              {t.admin.users.cancel}
            </Button>
            <Button onClick={handleSaveEdit} disabled={saving}>
              {saving ? t.admin.users.saving : t.admin.users.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete User Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{t.admin.users.deleteUser}</DialogTitle>
            <DialogDescription>
              {t.admin.users.deleteConfirm(deletingUser?.username ?? "")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="type-body font-medium">
              {t.admin.users.resourceStrategy}
            </p>

            <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3">
              <input
                type="radio"
                name="resource-strategy"
                checked={deleteStrategy === "soft_delete"}
                onChange={() => setDeleteStrategy("soft_delete")}
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <p className="type-body font-medium">
                  {t.admin.users.softDelete}
                </p>
                <p className="text-muted-foreground type-body">
                  {t.admin.users.softDeleteDesc}
                </p>
              </div>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3">
              <input
                type="radio"
                name="resource-strategy"
                checked={deleteStrategy === "delete"}
                onChange={() => setDeleteStrategy("delete")}
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <p className="type-body font-medium">
                  {t.admin.users.hardDelete}
                </p>
                <p className="text-muted-foreground type-body">
                  {t.admin.users.hardDeleteDesc}
                </p>
              </div>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3">
              <input
                type="radio"
                name="resource-strategy"
                checked={deleteStrategy === "transfer"}
                onChange={() => {
                  setDeleteStrategy("transfer");
                  setDeleteTargetUserId("");
                }}
                className="mt-0.5"
              />
              <div className="flex-1 space-y-0.5">
                <p className="type-body font-medium">
                  {t.admin.users.transferResources}
                </p>
                <p className="text-muted-foreground type-body">
                  {t.admin.users.transferDesc}
                </p>
                {deleteStrategy === "transfer" && (
                  <select
                    value={deleteTargetUserId}
                    onChange={(e) => setDeleteTargetUserId(e.target.value)}
                    className="type-body mt-2 h-9 w-full max-w-xs rounded-md border bg-transparent px-3"
                  >
                    <option value="">{t.admin.users.selectTargetUser}</option>
                    {users
                      .filter((u) => u.id !== deletingUser?.id)
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.username}
                        </option>
                      ))}
                  </select>
                )}
              </div>
            </label>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteSubmitting}
            >
              {t.admin.users.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteSubmitting}
            >
              {deleteSubmitting
                ? t.admin.users.deleting
                : t.admin.users.confirmDelete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
