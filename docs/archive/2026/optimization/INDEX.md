# iDeer 企业内网平台优化方案文档索引

> audience: maintainers, auditors<br>
> status: archived<br>
> owner: repository maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/archive/2026/optimization/INDEX.md`

> 最后更新：2026-06-10
> 基准数据：211 个后端测试文件 / 30 个前端测试文件 / 37 个已知遗留 Bug

## 文档列表

### 1. [优化方案概述](README.md)
- 优化目标和优先级矩阵（Bug 修复优先）
- 总体工作量估算
- 预期收益总结

### 2. [Bug 修复与功能完善](01-bug-fix-and-feature-completion.md)
- 后端 37 项遗留 Bug 分级修复（CRITICAL/HIGH/MEDIUM）
- 前端功能缺陷修复（Skill 保存、Admin 权限、API 错误处理）
- 已有 Bug 追踪：参见 `docs/bug-list.md`

### 3. [测试完善方案](02-testing-improvement.md)
- Phase 3-5 新增功能的测试补充（Admin API / 工作流 / 工具）
- 前端 E2E 测试扩展（Admin / Workflow / Settings 页面）
- 测试覆盖率目标：新增功能模块 80%+

### 4. [文档建设方案](03-documentation.md)
- API 文档（Swagger/OpenAPI）
- 用户使用手册
- 部署运维文档（内网环境适配）

### 5. [性能优化方案](04-performance-optimization.md)
- 数据库索引优化（避免与已有迁移重复）
- 连接池调优（区分 SQLite / PostgreSQL）
- 前端加载性能优化（适配 Nextra 框架）

### 6. [安全加固方案](05-security-hardening.md)
- 基于已发现真实漏洞的针对性修复
- 输入验证增强（SafeString / SafePath / WorkflowYAML）
- 审计日志（异步写入 + 结构化存储）

### 7. [实施路线图](implementation-roadmap.md)
- 4 阶段 12 周实施计划（Bug 修复 → 测试 → 安全 → 文档/性能）
- 里程碑和交付物
- 单人/小团队裁剪方案

---

## 快速导航

### 按优先级

#### 🔴 P0 — 必须立即修复（阻塞 PR 合并）
- [工作流 goto 跳转失效](01-bug-fix-and-feature-completion.md#bug-c01)
- [Auth bypass 检查逻辑缺陷](01-bug-fix-and-feature-completion.md#bug-c02)
- [RBAC 数据库故障时权限升级](01-bug-fix-and-feature-completion.md#bug-h01)
- [前端 Admin 页面无角色校验](01-bug-fix-and-feature-completion.md#bug-f01)

#### 🟡 P1 — 本迭代必须完成
- [前端 API 缺少错误处理](01-bug-fix-and-feature-completion.md#bug-f02)
- [Skill 保存功能未实现](01-bug-fix-and-feature-completion.md#bug-f03)
- [MCP 缓存竞态条件](01-bug-fix-and-feature-completion.md#bug-h02)
- [工作流表达式运算符匹配缺陷](01-bug-fix-and-feature-completion.md#bug-h03)

#### 🟢 P2 — 建议完成
- [测试覆盖补充](02-testing-improvement.md)
- [安全加固](05-security-hardening.md)
- [文档建设](03-documentation.md)
- [性能优化](04-performance-optimization.md)

### 按阶段

#### 第一阶段：Bug 修复与功能完善（第 1-3 周）
- [后端 CRITICAL/HIGH Bug 修复](01-bug-fix-and-feature-completion.md#一后端-bug-修复)
- [前端功能缺陷修复](01-bug-fix-and-feature-completion.md#二前端-bug-修复)
- [已有 Bug 清单](../../../bug-list.md)

#### 第二阶段：测试补充（第 4-6 周）
- [Admin API 测试](02-testing-improvement.md#1-admin-api-测试)
- [工作流集成测试](02-testing-improvement.md#2-工作流执行器集成测试)
- [前端 E2E 测试扩展](02-testing-improvement.md#3-前端-e2e-测试扩展)

#### 第三阶段：安全与文档（第 7-10 周）
- [安全加固](05-security-hardening.md)
- [API 文档](03-documentation.md#1-api-文档swaggeropenapi)
- [用户手册](03-documentation.md#2-用户使用手册)

#### 第四阶段：性能与验收（第 11-12 周）
- [性能优化](04-performance-optimization.md)
- [集成测试与验收](implementation-roadmap.md#第-11-周集成测试与验收)

---

## 工作量汇总

| 优化项 | 预计工作量 | 优先级 | 文档 |
|--------|------------|--------|------|
| Bug 修复（后端 CRITICAL+HIGH） | 5-8 天 | 🔴 P0 | [Bug 修复](01-bug-fix-and-feature-completion.md#一后端-bug-修复) |
| Bug 修复（前端功能缺陷） | 3-5 天 | 🔴 P0 | [Bug 修复](01-bug-fix-and-feature-completion.md#二前端-bug-修复) |
| 测试补充（Admin/Workflow/Tools） | 5-7 天 | 🟡 P1 | [测试完善](02-testing-improvement.md) |
| 安全加固 | 4-6 天 | 🟡 P1 | [安全加固](05-security-hardening.md) |
| API 文档 | 2-3 天 | 🟢 P2 | [文档建设](03-documentation.md) |
| 用户手册 | 4-5 天 | 🟢 P2 | [文档建设](03-documentation.md) |
| 部署文档 | 2-3 天 | 🟢 P2 | [文档建设](03-documentation.md) |
| 性能优化 | 3-4 天 | 🟢 P2 | [性能优化](04-performance-optimization.md) |
| **总计** | **28-41 天** | | |

---

## 相关文档

- [平台开发总结](../../../platform-dev-summary.md)
- [已知问题清单](../../../bug-list.md)
- [Bug 修复追踪](../../../bug-list.md)
- [验证日志](../testing/validation-log.md)

---

**文档维护**: iDeer 开发团队
