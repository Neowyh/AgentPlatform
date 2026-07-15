# iDeer 离线产品线治理执行计划

基于 [治理方案](./offline-product-line-governance-plan.md) 与当前项目现状制定的四阶段执行计划。

---

## 项目当前状态

| 项目 | 状态 |
|------|------|
| 当前分支 | `offline_feature`（本地领先 agentplatform 72 个提交） |
| 72 个本地提交 | 完整的测试体系收口工作（Phase 0-5，全部通过） |
| `fix/test-issues` | 已合并入 `offline_feature`，生命周期结束 ✅ |
| `product/offline-1.x` | **尚未创建** |
| agentplatform 远程 | 仅 `main` 和 `offline_feature` 两个分支 |
| 上游 origin | 已发布 `v2.0.0` 正式标签 |
| 治理方案文档 | 已完成；`docs/offline-product-line-governance-plan.md` |

---

## 阶段一：建立 `product/offline-1.x` 产品主线（立即）

**目标**：将测试收口成果固化为受保护的产品基线。

1. 将 72 个测试提交推送至 `agentplatform/offline_feature`
2. 从当前已验证的 HEAD 创建 `product/offline-1.x` 分支
3. 推送到 `agentplatform` 并配置分支保护（禁止 force-push、需 code review）
4. 提交治理方案文档到 `product/offline-1.x`

**验证**：`agentplatform` 上存在 `product/offline-1.x` 分支，且包含最新测试收口提交。

---

## 阶段二：切换至新分支模型（阶段一完成后）

**目标**：`offline_feature` 退役，日常开发迁移至新主线。

1. 在 `offline_feature` 上打 `archive/offline_feature-final` 标签
2. 通知团队：后续所有 `feature/*`、`fix/*`、`test/*` 从 `product/offline-1.x` 创建
3. 清理本地过期的远程引用

**验证**：日常提交均基于 `product/offline-1.x` 创建的分支。

---

## 阶段三：首次上游分诊（可并行于阶段二）

**目标**：识别 v2.0.0 发布以来与当前离线产品线的差异。

1. 拉取 `origin` 的最新标签和主线
2. 对比 `v2.0.0` 与 `product/offline-1.x` 之间的差异
3. 按以下三类分类变更：
   - 🚨 **安全 / 数据损坏** → 走独立 hotfix
   - ⏳ **部署与依赖修复** → 评估后决定
   - 📦 **功能与重构** → 等待下个稳定版
4. 如有安全修复，创建 `hotfix/*` 分支走紧急流程
5. 记录分诊结果到 `docs/upstream-triage/`

**验证**：分诊清单记录在案，安全修复已完成回流。

---

## 阶段四：v2.0.0 升级准备（中期）

**目标**：启动大版本升级的隔离工作线。

1. 从 `product/offline-1.x` 创建 `integration/upstream-v2.0.0`
2. 按五类冲突逐项解决：
   - 离线部署
   - 认证 / RBAC
   - 存储与数据迁移
   - 工具 / 技能网络隔离
   - 前端契约
3. 每项冲突记录"采用上游 / 保留本地 / 重新实现"决策和验证命令
4. 验收通过后创建 `product/offline-2.x` 并归档整合线

**验证**：`integration/upstream-v2.0.0` 上完成所有冲突解决与验收，`product/offline-2.x` 发布。
