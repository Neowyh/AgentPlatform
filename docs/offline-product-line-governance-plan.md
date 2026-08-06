# iDeer 离线产品线长期治理方案

> audience: maintainers, release owners, operators<br>
> status: current<br>
> owner: product-line maintainers<br>
> last-verified: 2026-07-15<br>
> canonical-path: `docs/offline-product-line-governance-plan.md`

## 一句话核心思想

项目有两个远程仓库（`origin` 是字节官方上游，`agentplatform` 是团队自有仓库）。本方案定下一套规矩，让团队在 agentplatform 上独立开发离线功能，不受上游日常改动干扰，同时定期从上游获取安全更新，并行不悖地完成 v2 大版本升级。

---

## 两个仓库的角色

| 仓库 | 角色 | 说明 |
|------|------|------|
| `origin` (bytedance/deer-flow) | 只读上游"水库" | 只看不写，每月从中获取更新 |
| `agentplatform` (团队自有) | 唯一正式工作仓库 | 所有开发、发布都在此进行 |

---

## 分支与发布模型

### 保护主线

**`product/offline-1.x`** — 当前可发布、受保护的离线产品线。先完成并回流 `fix/test-issues` 中已验证的测试体系工作，再从该结果建立。

### 日常开发分支

`feature/<topic>`、`fix/<topic>`、`test/<topic>` 均从 `product/offline-1.x` 创建；合并前 rebase 到最新产品线并 fast-forward 合入，保持历史线性、每个提交对应一个可验证意图。

### 紧急修复

`hotfix/<issue>` 从当前已发布标签创建，修复后同时回流对应产品线。

### 大版本升级

`integration/upstream-v2.0.0` 一次性升级工作线，从 `product/offline-1.x` 创建，仅用于 v2 迁移。验收完成后创建 `product/offline-2.x`，随后删除整合线。

### 发布

以 agentplatform 上的不可变 iDeer 标签为准；禁止 force-push 产品分支和发布标签。`offline_feature` 在完成迁移与确认后归档，不再作为长期主线。

---

## 上游更新处理（每月分诊）

1. 拉取 origin 的标签与主线变化，基于"上一次已吸收的上游标签"生成变更清单。
2. 将变更分为三类：
   - 🚨 **必须快速回流**：安全漏洞、数据损坏修复（走独立 hotfix）
   - ⏳ **需评估**：部署与依赖修复
   - 📦 **等稳定版**：功能与重构
3. 不按 origin/main 的提交数量做合并决策；正式功能和架构升级只锚定上游稳定标签。

---

## v2.0.0 升级方案

作为首个独立升级项目，在 `integration/upstream-v2.0.0` 中合并上游标签，按以下五类逐项解决冲突：

1. 离线部署
2. 认证 / RBAC
3. 存储与数据迁移
4. 工具 / 技能网络隔离
5. 前端契约

每类冲突记录"采用上游 / 保留本地 / 重新实现"的理由与验证命令；不能通过降断言、扩大 skip 或绕开离线约束取得通过。

验收完成后建立 `product/offline-2.x` 并发布新版；在此之前 `product/offline-1.x` 持续承接本地功能和补丁。

---

## 质量门槛

### 日常合并

- 针对改动的单元 / 契约测试
- 类型检查或 lint
- 离线功能不联网的定向验证
- 可审查的提交范围

### v2 升级

- 后端：默认测试、QA、blocking-I/O、迁移验证
- 前端：单测、类型检查、分层 E2E
- 集成：离线 Docker 打包、断网部署、升级迁移、RBAC 回归

### 发布记录

每次发布记录：iDeer 产品标签、对应上游标签、已吸收/明确拒绝的上游变更、离线兼容性结论、完整验证证据。

---

## 验收标准

- 只有 `product/offline-1.x` 承担当前离线发布责任，`fix/test-issues` 回归为短生命周期施工线
- 团队可在不接触 `origin/main` 的情况下持续开发和发布离线能力
- 每月分诊能识别安全修复，但不会把未稳定社区功能自动带入产品
- v2.0.0 升级可独立暂停、回滚和验收；成功后形成 `product/offline-2.x`，不污染 1.x 维护线

---

## 前提假设

- agentplatform 由团队控制，可配置分支保护、代码评审和发布标签
- 当前未提交的测试收口改动会先按既有验收规则完成、提交，再作为 `product/offline-1.x` 的来源
- 以上游稳定版整合为主、每月安全分诊为辅；高危安全修复不等待稳定版本

---

## 执行步骤（简化）

1. 先把 testing 分支上的测试工作合并到 `product/offline-1.x`
2. **日常开发**：从 `product/offline-1.x` 建 `feature/xxx` → 开发 → rebase → fast-forward 合并
3. **每月分诊**：从 origin 拉取更新 → 分类 → 安全修复走 hotfix，其余等下次
4. **v2 升级**：建 `integration/upstream-v2.0.0` → 按 5 类解决冲突 → 验收 → 建 `product/offline-2.x`
5. **发布**：在 agentplatform 上打标签

> **核心原则：把离线产品和上游官方仓库解耦，安全更新不落下，大版本升级不干扰日常。**
