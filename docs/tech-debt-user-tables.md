# 技术债务：用户表合并

## 问题描述

系统中存在两个独立的用户表，需要手动保持同步，增加了维护成本和出错风险。

## 表结构

| 表名 | 用途 | 角色字段 | 创建时间 |
|------|------|----------|----------|
| `users` | 认证系统（登录、密码、OAuth） | `system_role` | 2026-04 (Phase 1) |
| `users_ext` | RBAC 权限系统（部门管理） | `role` | 2026-06 (Phase 3) |

## 历史原因

1. **Phase 1**：先实现了基础认证系统（`users` 表），只有 `admin` 和 `user` 两种角色
2. **Phase 3**：后来添加了企业级 RBAC 权限系统（`users_ext` 表），需要更复杂的角色（`super_admin`, `department_admin`, `user`, `viewer`）
3. **技术债务**：为了不破坏现有认证系统，选择了"新增表"而不是"修改现有表"

## 当前解决方案

在 `update_user_role` 函数中同步更新两个表：

```python
# 更新 users_ext 表（原有逻辑）
user.role = UserRole(body.role)

# 同步更新 users 表
from ideer.persistence.user.model import UserRow
user_row = await session.get(UserRow, user_id)
if user_row is not None:
    user_row.system_role = body.role
```

## 长期方案

编写 Alembic 迁移脚本合并两个表：

1. 将 `users_ext` 表的数据迁移到 `users` 表
2. 删除 `users_ext` 表
3. 修改所有引用 `users_ext` 表的代码
4. 更新相关测试用例

## 风险评估

| 因素 | 说明 |
|------|------|
| **数据库迁移** | 需要写 Alembic 迁移脚本，合并两个表 |
| **代码改动** | 需要修改所有引用 `users` 表的代码（约 20+ 个文件） |
| **OAuth 兼容** | `users` 表有 OAuth 字段，合并后需要保留 |
| **测试覆盖** | 需要更新所有测试用例 |
| **部署风险** | 需要停机迁移，可能影响生产环境 |

## 优先级

**P2**（当前方案可接受，但增加维护成本）

## 相关文件

- `backend/packages/harness/ideer/persistence/user/model.py` (users 表)
- `backend/packages/harness/ideer/persistence/models/user.py` (users_ext 表)
- `backend/app/gateway/routers/admin.py` (角色更新逻辑)
- `backend/app/gateway/auth/repositories/sqlite.py` (用户仓储)

## 影响范围

- 用户角色更新逻辑
- 用户信息获取逻辑
- RBAC 权限检查
- 前端用户管理页面
