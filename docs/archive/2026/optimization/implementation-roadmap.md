# 实施路线图

## 概述

本路线图基于 `offline_feature` 分支的实际状态制定，**Bug 修复优先**，测试和安全加固次之，文档和性能优化最后。

> 当前状态：211 个后端测试文件 / 30 个前端测试文件 / 37 项遗留 Bug / 本轮新发现 20+ 项

---

## 总体时间规划

```
总工期：8-12 周（约 2-3 个月）

第一阶段：Bug 修复（第 1-3 周）
├── 第 1 周：CRITICAL Bug（goto、auth bypass、权限升级）
├── 第 2 周：HIGH Bug（MCP 竞态、表达式、前端 API）
└── 第 3 周：MEDIUM Bug + 遗留问题

第二阶段：测试补充（第 4-6 周）
├── 第 4 周：Admin API 测试
├── 第 5 周：工作流集成测试
└── 第 6 周：前端 E2E 测试

第三阶段：安全加固（第 7-9 周）
├── 第 7 周：API 限流 + 输入验证
├── 第 8 周：审计日志
└── 第 9 周：安全头 + CORS + 安全测试

第四阶段：文档与性能（第 10-12 周）
├── 第 10 周：API 文档 + 部署文档
├── 第 11 周：性能优化
└── 第 12 周：集成验收
```

---

## 第一阶段：Bug 修复（第 1-3 周）

### 目标

- 清零所有 CRITICAL 和 HIGH 级别 Bug
- 修复前端功能缺陷
- 确保 PR 合并前代码质量

### 第 1 周：CRITICAL Bug

#### 任务清单

| 天数 | 任务 | 文件 | 说明 |
|------|------|------|------|
| Day 1-2 | 修复工作流 goto 跳转 | `workflows/executor.py` | 改用 while 循环 + 手动索引 |
| Day 3 | 修复 Auth bypass 逻辑 | `gateway/authz.py` | 对真实 Request 拒绝 bypass |
| Day 4 | 修复 RBAC 权限升级 | `gateway/authz.py` | DB 故障返回最小权限 |
| Day 5 | 修复 Admin 页面角色校验 | `frontend/src/app/workspace/admin/` | 添加角色检查 |

#### 验收标准

- [ ] 工作流条件分支 goto 正常跳转
- [ ] Auth bypass 对真实 Request 不生效
- [ ] RBAC DB 故障时不授予全部权限
- [ ] 非 admin 角色无法访问 `/workspace/admin`

### 第 2 周：HIGH Bug

#### 任务清单

| 天数 | 任务 | 文件 | 说明 |
|------|------|------|------|
| Day 1 | 修复 MCP 缓存竞态 | `mcp/cache.py` | 使用 threading.Lock |
| Day 2 | 修复表达式运算符匹配 | `workflows/executor.py` | 正则词边界匹配 |
| Day 3 | 修复角色修正未持久化 | `gateway/authz.py` | 添加 session.commit |
| Day 4 | 修复前端 API 错误处理 | `frontend/src/core/*/api.ts` | 统一 extractError |
| Day 5 | 实现 Skill 保存功能 | `frontend/src/components/workspace/settings/` | 调用 PUT API |

#### 验收标准

- [ ] MCP 初始化无竞态
- [ ] 表达式 `">="` 不被误判为 `">"`
- [ ] 前端 API 错误统一处理
- [ ] Skill 编辑后保存成功

### 第 3 周：MEDIUM Bug + 遗留问题

#### 任务清单

| 天数 | 任务 | 说明 |
|------|------|------|
| Day 1 | 后端 MEDIUM Bug（M01-M09） | session pool、条件重试、日志格式等 |
| Day 2 | 前端 MEDIUM Bug（F05-F13） | console.log、i18n、XSS、验证等 |
| Day 3-4 | 遗留 HIGH 问题 | ToolRegistry.update_config、retry 覆盖、submit_review TOCTOU |
| Day 5 | 回归测试 | 确保所有修复有测试覆盖 |

#### 验收标准

- [ ] 所有 CRITICAL/HIGH Bug 清零
- [ ] 前端 console.log 移除
- [ ] Admin 页面 i18n 化
- [ ] 遗留 HIGH 问题处理完毕

---

## 第二阶段：测试补充（第 4-6 周）

### 目标

- Admin API 测试覆盖 80%+
- 工作流集成测试覆盖 85%+
- 前端 E2E 覆盖主要流程

### 第 4 周：Admin API 测试

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| 测试文件 | `backend/tests/test_admin_api.py` |
| 测试 Fixtures | `backend/tests/conftest.py` |

#### 验收标准

- [ ] 测试用例 30+
- [ ] RBAC 权限测试覆盖
- [ ] 用户/部门 CRUD 测试

### 第 5 周：工作流集成测试

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| 测试文件 | `backend/tests/test_workflow_executor_integration.py` |
| Mock 工具 | `backend/tests/mocks/` |

#### 验收标准

- [ ] 测试用例 24+
- [ ] 6 种步骤类型覆盖
- [ ] 错误处理测试

### 第 6 周：前端 E2E 测试

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| Admin 测试 | `frontend/tests/e2e/admin.spec.ts` |
| Workflow 测试 | `frontend/tests/e2e/workflows.spec.ts` |
| Settings 测试 | `frontend/tests/e2e/settings.spec.ts` |

#### 验收标准

- [ ] 测试用例 18+
- [ ] Admin 页面流程覆盖
- [ ] 工作流创建/运行覆盖

---

## 第三阶段：安全加固（第 7-9 周）

### 目标

- 建立 API 限流防护
- 输入验证覆盖所有用户输入
- 审计日志记录所有操作

### 第 7 周：API 限流 + 输入验证

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| 限流中间件 | `backend/app/gateway/rate_limit_middleware.py` |
| 验证类库 | `backend/app/gateway/validators.py` |
| 测试 | `backend/tests/test_rate_limit.py` |
| 测试 | `backend/tests/test_validators.py` |

#### 验收标准

- [ ] 限流中间件正常工作
- [ ] 不同角色不同限流策略
- [ ] XSS/路径遍历被阻止
- [ ] 密码强度验证生效

### 第 8 周：审计日志

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| 审计中间件 | `backend/app/gateway/audit_middleware.py` |
| 测试 | `backend/tests/test_audit.py` |

#### 验收标准

- [ ] 所有 API 请求被记录
- [ ] 敏感数据被脱敏
- [ ] 日志格式结构化

### 第 9 周：安全测试 + 配置

#### 交付物

| 交付物 | 说明 |
|--------|------|
| 安全头配置 | 在 app.py 中添加 |
| CORS 配置 | 从环境变量读取 |
| 安全测试 | 验证限流、验证、审计 |

#### 验收标准

- [ ] 安全头正确返回
- [ ] CORS 仅允许信任域名
- [ ] 安全测试通过

---

## 第四阶段：文档与性能（第 10-12 周）

### 目标

- 建立完整文档体系
- 优化关键性能瓶颈
- 集成验收

### 第 10 周：文档建设

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| Swagger 配置 | `backend/app/gateway/app.py` |
| 用户手册 | `docs/user-manual/` |
| 部署文档 | `docs/deployment/` |

#### 验收标准

- [ ] Swagger UI 可访问
- [ ] 用户手册完整
- [ ] 部署文档可操作

### 第 11 周：性能优化

#### 交付物

| 交付物 | 文件路径 |
|--------|----------|
| 数据库迁移 | `persistence/migrations/versions/` |
| 查询优化 | `workflows/store.py` |
| 前端优化 | `frontend/next.config.js` |

#### 验收标准

- [ ] 数据库查询提速 2-5x
- [ ] 前端静态资源缓存生效
- [ ] 无性能回退

### 第 12 周：集成验收

#### 交付物

| 交付物 | 说明 |
|--------|------|
| 全量测试通过 | 后端 + 前端 |
| 安全扫描 | 无高危漏洞 |
| 性能测试 | 指标达标 |
| 验收文档 | 本归档目录未保留独立验收报告 |

#### 验收标准

- [ ] 所有测试通过
- [ ] 安全扫描无高危
- [ ] 性能指标达标
- [ ] 文档完整

---

## 单人/小团队裁剪方案

如果只有 1-2 人开发，建议按以下优先级裁剪：

### 必须完成（不可裁剪）

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| 第一阶段 | CRITICAL Bug 修复 | 3-4 天 |
| 第一阶段 | HIGH Bug 修复 | 3-4 天 |
| 第二阶段 | Admin API 测试（最小集） | 2 天 |
| **小计** | | **8-10 天** |

### 建议完成（可延后）

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| 第一阶段 | MEDIUM Bug | 2-3 天 |
| 第二阶段 | 工作流测试 | 2 天 |
| 第三阶段 | 限流 + 验证 | 3 天 |
| **小计** | | **7-8 天** |

### 可延后（下个迭代）

| 任务 | 工作量 |
|------|--------|
| 前端 E2E 测试 | 3 天 |
| 审计日志 | 2 天 |
| 文档建设 | 5-7 天 |
| 性能优化 | 3-4 天 |
| **小计** | **13-16 天** |

---

## 风险管理

### 技术风险

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 工作流 goto 修复影响现有逻辑 | 高 | 充分测试，保留回滚方案 |
| MCP 竞态修复引入新问题 | 中 | 单元测试覆盖 |
| 数据库迁移失败 | 高 | 备份策略、回滚方案 |

### 进度风险

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Bug 数量超出预期 | 高 | 优先 P0，P2 可延后 |
| 人员不足 | 中 | 裁剪方案 |
| 需求变更 | 中 | 变更控制 |

---

## 交付物清单

### 代码交付物

| 交付物 | 文件路径 | 阶段 |
|--------|----------|------|
| Bug 修复 | 多个文件 | 第一阶段 |
| 限流中间件 | `gateway/rate_limit_middleware.py` | 第三阶段 |
| 验证类库 | `gateway/validators.py` | 第三阶段 |
| 审计中间件 | `gateway/audit_middleware.py` | 第三阶段 |
| 数据库迁移 | `persistence/migrations/versions/` | 第四阶段 |

### 测试交付物

| 交付物 | 文件路径 | 阶段 |
|--------|----------|------|
| Admin API 测试 | `tests/test_admin_api.py` | 第二阶段 |
| 工作流测试 | `tests/test_workflow_executor_integration.py` | 第二阶段 |
| 前端 E2E | `frontend/tests/e2e/*.spec.ts` | 第二阶段 |
| 安全测试 | `tests/test_validators.py` 等 | 第三阶段 |

### 文档交付物

| 交付物 | 文件路径 | 阶段 |
|--------|----------|------|
| 优化方案 | `docs/archive/2026/optimization/` | 已归档 |
| 用户手册 | `docs/user-manual/` | 第四阶段 |
| 部署文档 | `docs/deployment/` | 第四阶段 |
