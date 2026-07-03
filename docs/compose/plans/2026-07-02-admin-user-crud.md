# Admin User CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add create, update, and delete user functionality to the admin user management interface, with department-scoped access for `department_admin` and full access for `super_admin`.

**Architecture:** The system uses two user tables: legacy `users` (auth credentials) and `users_ext` (RBAC with department). Both share the same UUID. New endpoints create/update records in both tables. Frontend adds dialog components for create/edit flows.

**Tech Stack:** Python FastAPI, SQLAlchemy async, Next.js, TypeScript, Shadcn UI (Dialog, Input, Select, Button)

---

### Task 1: Backend — Add Create User Endpoint

**Covers:** 新增用户功能

**Files:**
- Modify: `backend/app/gateway/routers/admin.py:60-126`

- [ ] **Step 1: Add request model and endpoint**

Add after `UpdateRoleRequest` (line 48):

```python
class CreateUserRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=6, max_length=128)
    username: str = Field(..., max_length=100)
    role: str = Field(default=UserRole.USER)
    department_id: str | None = Field(None)
```

Add new endpoint after `list_users` (after line 126):

```python
@router.post("/users", status_code=201)
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def create_user(
    body: CreateUserRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Create a new user.

    super_admin can create any user in any department.
    department_admin can only create regular users in their own department.
    """
    if body.role not in tuple(UserRole):
        raise HTTPException(status_code=400, detail="Invalid role")

    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # department_admin restrictions
    if current_user.role == UserRole.DEPARTMENT_ADMIN:
        if body.role in (UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN):
            raise HTTPException(status_code=403, detail="Cannot create admin users")
        if not current_user.department_id:
            raise HTTPException(status_code=400, detail="No department assigned")
        body.department_id = current_user.department_id

    # Validate department exists if specified
    if body.department_id:
        async with sf() as session:
            dept = await session.get(DepartmentModel, body.department_id)
            if dept is None:
                raise HTTPException(status_code=400, detail="Department not found")

    # Create in legacy users table
    from app.gateway.auth.local_provider import get_local_provider

    provider = get_local_provider()
    try:
        legacy_user = await provider.create_user(
            email=body.email, password=body.password, system_role=body.role
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Create in users_ext table
    async with sf() as session:
        rbac_user = UserModel(
            id=str(legacy_user.id),
            username=body.username,
            role=body.role,
            department_id=body.department_id,
        )
        session.add(rbac_user)
        await session.commit()

    return {
        "id": str(legacy_user.id),
        "email": body.email,
        "username": body.username,
        "role": body.role,
        "department_id": body.department_id,
    }
```

- [ ] **Step 2: Test backend endpoint manually**

```bash
cd backend && python -m pytest tests/ -k "admin" -x --no-header -q 2>/dev/null || echo "No admin tests yet"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/gateway/routers/admin.py
git commit -m "feat(admin): add POST /api/admin/users endpoint for creating users"
```

---

### Task 2: Backend — Add Update User Endpoint

**Covers:** 修改用户信息

**Files:**
- Modify: `backend/app/gateway/routers/admin.py:129-200`

- [ ] **Step 1: Add request model and endpoint**

Add after `CreateUserRequest`:

```python
class UpdateUserRequest(BaseModel):
    username: str | None = Field(None, max_length=100)
    department_id: str | None = Field(None)
```

Add new endpoint after `create_user`:

```python
@router.put("/users/{user_id}")
@require_role(UserRole.SUPER_ADMIN, UserRole.DEPARTMENT_ADMIN)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: UserModel = Depends(get_current_rbac_user),
):
    """Update user details (username, department).

    super_admin can update any user.
    department_admin can only update regular users in their own department.
    """
    sf = get_session_factory()
    if sf is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with sf() as session:
        stmt = select(UserModel).where(UserModel.id == user_id)
        try:
            stmt = stmt.with_for_update()
        except Exception:
            pass
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # department_admin restrictions
        if current_user.role == UserRole.DEPARTMENT_ADMIN:
            if user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify super_admin")
            if user.role == UserRole.DEPARTMENT_ADMIN:
                raise HTTPException(status_code=403, detail="Cannot modify another department_admin")
            if user.department_id != current_user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users outside your department")
            if not user.department_id:
                raise HTTPException(status_code=403, detail="Cannot modify users without a department")
            # Force department to own
            body.department_id = current_user.department_id

        if body.username is not None:
            if not body.username.strip():
                raise HTTPException(status_code=400, detail="Username cannot be empty")
            # Check username uniqueness
            existing = await session.execute(
                select(UserModel).where(UserModel.username == body.username, UserModel.id != user_id)
            )
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="Username already exists")
            user.username = body.username.strip()

        if body.department_id is not None:
            if body.department_id:
                dept = await session.get(DepartmentModel, body.department_id)
                if dept is None:
                    raise HTTPException(status_code=400, detail="Department not found")
            user.department_id = body.department_id or None

        await session.commit()

    return {"success": True, "user_id": user_id}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/gateway/routers/admin.py
git commit -m "feat(admin): add PUT /api/admin/users/{id} endpoint for updating user details"
```

---

### Task 3: Frontend — Add API Client Functions

**Covers:** Frontend API layer for create/update

**Files:**
- Modify: `frontend/src/core/admin/api.ts:56-63`

- [ ] **Step 1: Add createUser and updateUser functions**

Add after `disableUser` (line 63):

```typescript
export async function createUser(data: {
  email: string;
  password: string;
  username: string;
  role: string;
  department_id?: string;
}): Promise<{
  id: string;
  email: string;
  username: string;
  role: string;
  department_id: string | null;
}> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to create user");
  return res.json() as Promise<{
    id: string;
    email: string;
    username: string;
    role: string;
    department_id: string | null;
  }>;
}

export async function updateUser(
  userId: string,
  data: { username?: string; department_id?: string },
): Promise<{ success: boolean; user_id: string }> {
  const baseURL = getBackendBaseURL();
  const res = await fetch(`${baseURL}/api/admin/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) return extractError(res, "Failed to update user");
  return res.json() as Promise<{ success: boolean; user_id: string }>;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/core/admin/api.ts
git commit -m "feat(admin): add createUser and updateUser API client functions"
```

---

### Task 4: Frontend — Add Create User Dialog

**Covers:** 新增用户界面

**Files:**
- Modify: `frontend/src/app/workspace/admin/users/page.tsx`

- [ ] **Step 1: Add imports and dialog state**

Add imports at top:

```typescript
import { PlusIcon } from "lucide-react";
import { useState } from "react";  // already imported, just ensure Dialog ones are added
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createUser } from "@/core/admin/api";
```

Add state variables after existing state (around line 56):

```typescript
const [createDialogOpen, setCreateDialogOpen] = useState(false);
const [createForm, setCreateForm] = useState({
  email: "",
  password: "",
  username: "",
  role: "user" as UserRole,
  department_id: "" as string,
});
const [creating, setCreating] = useState(false);
```

- [ ] **Step 2: Add create handler**

Add after `handleDisable` function:

```typescript
const handleCreate = async () => {
  if (!createForm.email || !createForm.password || !createForm.username) {
    toast.error("请填写所有必填字段");
    return;
  }
  setCreating(true);
  try {
    await createUser({
      email: createForm.email,
      password: createForm.password,
      username: createForm.username,
      role: createForm.role,
      department_id: createForm.department_id || undefined,
    });
    toast.success("用户创建成功");
    setCreateDialogOpen(false);
    setCreateForm({ email: "", password: "", username: "", role: "user", department_id: "" });
    await fetchUsers();
  } catch (err) {
    toast.error(err instanceof Error ? err.message : String(err));
  } finally {
    setCreating(false);
  }
};
```

- [ ] **Step 3: Add "Create User" button in header**

Replace the filter bar section (around line 164-194) to include a create button:

```tsx
<div className="flex items-center justify-between border-b px-6 py-3">
  <div className="flex items-center gap-3">
    {currentUser?.system_role === "super_admin" && (
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
    )}
    <Select value={filterRole} onValueChange={setFilterRole}>
      <SelectTrigger className="w-40">
        <SelectValue placeholder="筛选角色" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">全部角色</SelectItem>
        <SelectItem value="user">普通用户</SelectItem>
        <SelectItem value="department_admin">部门管理员</SelectItem>
        {currentUser?.system_role === "super_admin" && (
          <SelectItem value="super_admin">超级管理员</SelectItem>
        )}
      </SelectContent>
    </Select>
  </div>
  <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
    <DialogTrigger asChild>
      <Button size="sm">
        <PlusIcon className="mr-1 h-4 w-4" />
        新增用户
      </Button>
    </DialogTrigger>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>新增用户</DialogTitle>
        <DialogDescription>创建一个新的用户账号</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4">
        <div className="grid gap-2">
          <Label htmlFor="email">邮箱 *</Label>
          <Input
            id="email"
            type="email"
            value={createForm.email}
            onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
            placeholder="user@example.com"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">密码 *</Label>
          <Input
            id="password"
            type="password"
            value={createForm.password}
            onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
            placeholder="至少6位"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="username">用户名 *</Label>
          <Input
            id="username"
            value={createForm.username}
            onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
            placeholder="显示名称"
          />
        </div>
        <div className="grid gap-2">
          <Label>角色</Label>
          <Select
            value={createForm.role}
            onValueChange={(value) => setCreateForm({ ...createForm, role: value as UserRole })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="user">普通用户</SelectItem>
              <SelectItem value="department_admin">部门管理员</SelectItem>
              {currentUser?.system_role === "super_admin" && (
                <SelectItem value="super_admin">超级管理员</SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>
        {currentUser?.system_role === "super_admin" && (
          <div className="grid gap-2">
            <Label>部门</Label>
            <Select
              value={createForm.department_id}
              onValueChange={(value) => setCreateForm({ ...createForm, department_id: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择部门" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">未分配</SelectItem>
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
        <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
          取消
        </Button>
        <Button onClick={handleCreate} disabled={creating}>
          {creating ? "创建中..." : "创建"}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/workspace/admin/users/page.tsx
git commit -m "feat(admin): add create user dialog to user management page"
```

---

### Task 5: Frontend — Add Edit User Dialog

**Covers:** 修改用户信息界面

**Files:**
- Modify: `frontend/src/app/workspace/admin/users/page.tsx`

- [ ] **Step 1: Add edit state and handler**

Add state variables:

```typescript
const [editDialogOpen, setEditDialogOpen] = useState(false);
const [editingUser, setEditingUser] = useState<User | null>(null);
const [editForm, setEditForm] = useState({ username: "", department_id: "" });
const [saving, setSaving] = useState(false);
```

Add handler:

```typescript
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
    toast.error("用户名不能为空");
    return;
  }
  setSaving(true);
  try {
    await updateUser(editingUser.id, {
      username: editForm.username.trim(),
      department_id: editForm.department_id || undefined,
    });
    toast.success("用户信息已更新");
    setEditDialogOpen(false);
    await fetchUsers();
  } catch (err) {
    toast.error(err instanceof Error ? err.message : String(err));
  } finally {
    setSaving(false);
  }
};
```

- [ ] **Step 2: Add Edit button and Dialog**

Add import for Edit icon:

```typescript
import { ArrowLeftIcon, ShieldOffIcon, UserIcon, PencilIcon } from "lucide-react";
```

Add Edit button next to disable button (around line 283-292):

```tsx
<Button
  variant="ghost"
  size="icon-sm"
  onClick={() => handleEdit(user)}
  disabled={isSelf}
  title={isSelf ? "不能修改自己的信息" : "编辑用户"}
  data-testid="user-edit-button"
>
  <PencilIcon className="h-4 w-4" />
</Button>
```

Add Edit Dialog before closing `</div>` of the page:

```tsx
<Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>编辑用户</DialogTitle>
      <DialogDescription>
        修改用户 "{editingUser?.username}" 的信息
      </DialogDescription>
    </DialogHeader>
    <div className="grid gap-4 py-4">
      <div className="grid gap-2">
        <Label htmlFor="edit-username">用户名</Label>
        <Input
          id="edit-username"
          value={editForm.username}
          onChange={(e) => setEditForm({ ...editForm, username: e.target.value })}
        />
      </div>
      {currentUser?.system_role === "super_admin" && (
        <div className="grid gap-2">
          <Label>部门</Label>
          <Select
            value={editForm.department_id}
            onValueChange={(value) => setEditForm({ ...editForm, department_id: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择部门" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">未分配</SelectItem>
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
      <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
        取消
      </Button>
      <Button onClick={handleSaveEdit} disabled={saving}>
        {saving ? "保存中..." : "保存"}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/workspace/admin/users/page.tsx
git commit -m "feat(admin): add edit user dialog to user management page"
```

---

### Task 6: Verify — Run Lint and Type Check

**Covers:** Quality gate

**Files:** (none — verification only)

- [ ] **Step 1: Run backend lint**

```bash
cd backend && make lint
```

- [ ] **Step 2: Run frontend type check and lint**

```bash
cd frontend && pnpm check
```

- [ ] **Step 3: Run backend tests**

```bash
cd backend && make test
```

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && pnpm test
```

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: lint and type errors after admin user CRUD"
```
