# 多角色权限测试指南

## 概述

系统支持 4 种用户角色，每种角色有不同的权限：

| 角色 | 权限级别 | 说明 |
|------|----------|------|
| super_admin | 最高 | 超级管理员，拥有所有权限 |
| department_admin | 高 | 部门管理员，管理本部门 |
| user | 中 | 普通用户，基本功能权限 |
| viewer | 低 | 只读用户，只能查看 |

## 测试覆盖范围

### 1. 管理员权限测试

测试管理员专属功能：
- 访问管理统计 (`/api/admin/stats`)
- 列出所有用户 (`/api/admin/users`)
- 管理部门 (`/api/admin/departments`)
- 管理工具 (`/api/admin/tools`)

### 2. 普通用户权限测试

测试普通用户可用功能：
- 列出 agents (`/api/agents`)
- 列出 workflows (`/api/workflows`)
- 列出 skills (`/api/skills`)
- 列出 tools (`/api/tools`)
- 搜索 threads (`/api/threads/search`)
- 加载记忆 (`/api/memory`)

### 3. 权限边界测试

测试普通用户尝试访问管理员功能（应该被拒绝）：
- 普通用户访问管理统计 → 403 Forbidden
- 普通用户列出所有用户 → 403 Forbidden
- 普通用户管理部门 → 403 Forbidden

### 4. 资源隔离测试

测试用户只能访问自己的资源：
- 用户只能看到自己的 threads
- 用户不能访问其他用户的 threads

## 运行测试

### 前提条件

1. 后端服务运行中
2. 数据库中有测试用户

### 运行所有 QA 测试

```bash
cd backend

# 运行所有 QA 测试
.venv/bin/python -m pytest tests/qa/ -v

# 只运行多角色权限测试
.venv/bin/python -m pytest tests/qa/test_api_qa_multitole.py -v

# 只运行基础 QA 测试
.venv/bin/python -m pytest tests/qa/test_api_qa.py -v
```

### 使用自定义凭据

如果系统中的用户凭据不是默认值，可以使用环境变量：

```bash
cd backend

# 设置管理员凭据
export QA_ADMIN_EMAIL="admin@example.com"
export QA_ADMIN_PASSWORD="your-admin-password"

# 设置普通用户凭据
export QA_USER_EMAIL="user@example.com"
export QA_USER_PASSWORD="your-user-password"

# 运行测试
.venv/bin/python -m pytest tests/qa/ -v
```

### 测试环境准备

如果需要重新初始化测试环境：

```bash
# 1. 删除数据库
rm -f .ideer/data/ideer.db

# 2. 重启后端服务
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 &

# 3. 运行测试（会自动初始化管理员）
.venv/bin/python -m pytest tests/qa/ -v
```

## 测试文件说明

| 文件 | 说明 |
|------|------|
| `test_api_qa.py` | 基础 QA 测试（只测试管理员） |
| `test_api_qa_multitole.py` | 多角色权限测试（推荐） |

## 测试类说明

### test_api_qa_multitole.py

| 测试类 | 说明 |
|--------|------|
| `TestAdminPermissions` | 管理员权限测试 |
| `TestUserPermissions` | 普通用户权限测试 |
| `TestPermissionBoundaries` | 权限边界测试 |
| `TestUnauthenticatedAccess` | 未认证访问测试 |
| `TestResourceIsolation` | 资源隔离测试 |

## 预期结果

### 成功情况

```
tests/qa/test_api_qa_multitole.py::TestAdminPermissions::test_admin_can_access_admin_stats PASSED
tests/qa/test_api_qa_multitole.py::TestAdminPermissions::test_admin_can_list_users PASSED
tests/qa/test_api_qa_multitole.py::TestUserPermissions::test_user_can_list_agents PASSED
tests/qa/test_api_qa_multitole.py::TestPermissionBoundaries::test_user_cannot_access_admin_stats PASSED
tests/qa/test_api_qa_multitole.py::TestUnauthenticatedAccess::test_unauthenticated_cannot_access_admin PASSED
tests/qa/test_api_qa_multitole.py::TestResourceIsolation::test_user_can_only_see_own_threads PASSED
```

### 失败情况

如果测试失败，可能的原因：

1. **凭据错误**: 检查环境变量中的用户名和密码
2. **权限配置错误**: 检查 RBAC 配置
3. **API 端点变更**: 检查 API 路由是否正确
4. **数据库问题**: 检查用户数据是否正确

## 集成到 CI/CD

### GitHub Actions 示例

```yaml
name: Backend QA Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt

    - name: Start backend service
      run: |
        cd backend
        PYTHONPATH=. uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 &
        sleep 10

    - name: Run QA tests
      env:
        QA_ADMIN_EMAIL: admin@test.com
        QA_ADMIN_PASSWORD: Test1234!
        QA_USER_EMAIL: user@test.com
        QA_USER_PASSWORD: Test1234!
      run: |
        cd backend
        .venv/bin/python -m pytest tests/qa/ -v
```

## 最佳实践

1. **测试前准备**:
   - 确保后端服务运行中
   - 确保数据库中有测试用户
   - 设置正确的环境变量

2. **测试覆盖**:
   - 运行所有 QA 测试，包括多角色测试
   - 确保覆盖所有权限场景

3. **测试结果**:
   - 检查所有测试是否通过
   - 分析失败原因并修复

4. **持续集成**:
   - 将 QA 测试集成到 CI/CD 流程
   - 每次提交都运行测试

## 故障排除

### 问题 1: 登录失败

```
SKIPPED [1] Login failed: invalid_credentials
```

**解决方案**:
- 检查用户名和密码是否正确
- 使用环境变量指定正确的凭据
- 或者删除数据库重新初始化

### 问题 2: 权限被拒绝

```
FAILED test_user_cannot_access_admin_stats - assert 403 in (401, 403)
```

**解决方案**:
- 检查 RBAC 配置是否正确
- 检查用户角色是否正确设置
- 检查 API 端点的权限配置

### 问题 3: 服务未运行

```
ERROR test_list_agents - httpx.ConnectError
```

**解决方案**:
- 启动后端服务
- 检查端口是否被占用
- 检查服务日志

## 相关文档

- [RBAC 配置文档](./rbac-configuration.md)
- [API 权限配置](./api-permissions.md)
- [测试框架文档](./testing-framework.md)
