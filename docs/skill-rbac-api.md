# Skill RBAC API 文档

本文档描述了 Skill RBAC（基于角色的访问控制）相关的 API 接口。

## 目录

1. [用户 Skill 偏好 API](#用户-skill-偏好-api)
2. [Skill 开放申请 API](#skill-开放申请-api)
3. [管理员审批 API](#管理员审批-api)
4. [管理员默认配置 API](#管理员默认配置-api)
5. [Skill 可见性管理 API](#skill-可见性管理-api)

---

## 用户 Skill 偏好 API

### 获取当前用户的 Skill 偏好

**请求**

```
GET /api/user/skill-preferences
```

**响应**

```json
{
  "preferences": [
    {
      "skill_name": "fault-zeroing",
      "enabled": true
    },
    {
      "skill_name": "deep-research",
      "enabled": false
    }
  ]
}
```

### 更新当前用户的 Skill 偏好

**请求**

```
PUT /api/user/skill-preferences
```

**请求体**

```json
{
  "preferences": [
    {
      "skill_name": "fault-zeroing",
      "enabled": true
    },
    {
      "skill_name": "deep-research",
      "enabled": false
    }
  ]
}
```

**响应**

```json
{
  "message": "Skill preferences updated successfully"
}
```

---

## Skill 开放申请 API

### 提交开放申请

**请求**

```
POST /api/skills/{skill_id}/apply
```

**请求体**

```json
{
  "request_level": "department",
  "reason": "这个 skill 对排故很有帮助，建议全员使用"
}
```

**响应**

```json
{
  "id": "app-123",
  "skill_id": "fault-zeroing",
  "skill_name": "fault-zeroing",
  "applicant_id": "user-123",
  "request_level": "department",
  "reason": "这个 skill 对排故很有帮助，建议全员使用",
  "status": "pending",
  "submitted_at": "2024-01-01T00:00:00"
}
```

### 查看申请状态

**请求**

```
GET /api/skills/{skill_id}/application
```

**响应**

```json
{
  "id": "app-123",
  "skill_id": "fault-zeroing",
  "skill_name": "fault-zeroing",
  "applicant_id": "user-123",
  "request_level": "department",
  "reason": "这个 skill 对排故很有帮助，建议全员使用",
  "status": "pending",
  "submitted_at": "2024-01-01T00:00:00"
}
```

### 撤回申请

**请求**

```
DELETE /api/skills/{skill_id}/application
```

**响应**

```json
{
  "message": "Application withdrawn successfully"
}
```

---

## 管理员审批 API

### 获取待审批列表

**请求**

```
GET /api/admin/skill-applications?status=pending
```

**响应**

```json
{
  "applications": [
    {
      "id": "app-123",
      "skill_id": "fault-zeroing",
      "skill_name": "fault-zeroing",
      "applicant_id": "user-123",
      "request_level": "department",
      "reason": "这个 skill 对排故很有帮助，建议全员使用",
      "status": "pending",
      "submitted_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### 审批申请

**请求**

```
PUT /api/admin/skill-applications/{application_id}
```

**请求体**

```json
{
  "action": "approved",
  "comment": "同意开放给部门使用"
}
```

**响应**

```json
{
  "message": "Application approved successfully"
}
```

---

## 管理员默认配置 API

### 获取默认配置列表

**请求**

```
GET /api/admin/skill-defaults?scope=global
```

**响应**

```json
{
  "configs": [
    {
      "id": "config-123",
      "scope": "global",
      "skill_name": "fault-zeroing",
      "enabled": true,
      "user_override_allowed": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### 创建默认配置

**请求**

```
POST /api/admin/skill-defaults
```

**请求体**

```json
{
  "scope": "global",
  "skill_name": "fault-zeroing",
  "enabled": true,
  "user_override_allowed": true
}
```

**响应**

```json
{
  "id": "config-123",
  "scope": "global",
  "skill_name": "fault-zeroing",
  "enabled": true,
  "user_override_allowed": true,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### 更新默认配置

**请求**

```
PUT /api/admin/skill-defaults/{config_id}
```

**请求体**

```json
{
  "enabled": false,
  "user_override_allowed": false
}
```

**响应**

```json
{
  "id": "config-123",
  "scope": "global",
  "skill_name": "fault-zeroing",
  "enabled": false,
  "user_override_allowed": false,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

### 删除默认配置

**请求**

```
DELETE /api/admin/skill-defaults/{config_id}
```

**响应**

```json
{
  "message": "Config deleted successfully"
}
```

---

## Skill 可见性管理 API

### 降低 Skill 可见性

**请求**

```
PUT /api/skills/{skill_name}/visibility
```

**请求体**

```json
{
  "visibility": "private",
  "reason": "这个 skill 还在测试阶段，暂时只在部门内使用"
}
```

**响应**

```json
{
  "name": "fault-zeroing",
  "description": "基于文件资料完成归零排故、故障树构建、底事件评估和归零报告生成",
  "category": "custom",
  "enabled": true,
  "visibility": "private"
}
```

---

## 权限说明

| API | 所需角色 | 说明 |
|-----|---------|------|
| GET /api/user/skill-preferences | 认证用户 | 获取当前用户的 skill 偏好 |
| PUT /api/user/skill-preferences | 认证用户 | 更新当前用户的 skill 偏好 |
| POST /api/skills/{id}/apply | Skill 所有者 | 提交开放申请 |
| GET /api/skills/{id}/application | Skill 所有者 | 查看申请状态 |
| DELETE /api/skills/{id}/application | Skill 所有者 | 撤回申请 |
| GET /api/admin/skill-applications | 部门管理员/超级管理员 | 获取待审批列表 |
| PUT /api/admin/skill-applications/{id} | 部门管理员/超级管理员 | 审批申请 |
| GET /api/admin/skill-defaults | 部门管理员/超级管理员 | 获取默认配置列表 |
| POST /api/admin/skill-defaults | 部门管理员/超级管理员 | 创建默认配置 |
| PUT /api/admin/skill-defaults/{id} | 部门管理员/超级管理员 | 更新默认配置 |
| DELETE /api/admin/skill-defaults/{id} | 部门管理员/超级管理员 | 删除默认配置 |
| PUT /api/skills/{name}/visibility | 所有者/管理员 | 降低可见性 |

---

## 错误响应

所有 API 在出错时返回以下格式：

```json
{
  "detail": "Error message"
}
```

常见错误码：

- `400` - 请求参数错误
- `401` - 未认证
- `403` - 权限不足
- `404` - 资源不存在
- `500` - 服务器内部错误