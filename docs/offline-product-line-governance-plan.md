# iDeer 离线产品线长期治理方案

> audience: maintainers, release owners, operators<br>
> status: current<br>
> owner: product-line maintainers<br>
> last-verified: 2026-10-01<br>
> canonical-path: `docs/offline-product-line-governance-plan.md`

## 一句话核心思想

项目有两个远程仓库（`origin` 是团队自有仓库，`deerflow` 是字节官方上游）。本方案定下一套规矩，让团队在 origin 上独立开发离线功能，不受上游日常改动干扰，同时定期从上游吸收稳定标签的安全与功能更新，并行不悖。

---

## 两个仓库的角色

| 远程 | 角色 | 说明 |
|------|------|------|
| `origin` (AgentPlatform，本仓库) | 唯一正式工作仓库 | 所有开发、发布都在此进行；开发主线 `develop` |
| `deerflow` (bytedance/deer-flow) | 只读上游"水库" | 只看不写，按双轨制从中吸收更新 |

> 2026-10-01 修正：本文档早期版本把 `origin` 写成 bytedance 上游、团队仓库写作
> `agentplatform`。当前实际 remote 配置以 `git remote -v` 为准：`origin` = 团队
> AgentPlatform 仓库，`deerflow` = bytedance 上游。下文所有 remote 名均按此口径。

---

## 分支与发布模型

| 分支 | 职责与来源 |
| --- | --- |
| `main` | 与 DeerFlow main 同提交的纯上游镜像，仅指定镜像流程快进更新，不同步团队规则 |
| `develop` | 团队默认开发分支，承接开发、规则、CI 与治理配置 |
| `feature/<topic>` / `fix/<topic>` | 从对应的 develop 或产品维护分支创建，合回原维护线 |
| `integration/upstream-*` | 吸收选定上游版本，逐项处理语义冲突和兼容验收 |
| `product/offline-*` | 独立产品维护与发布，既有分支和独立提交完整保留 |

`hotfix/<issue>` 从已发布的 `ideer-*` 标签创建，回流对应产品线，再评估是否回流 develop。
团队发布使用不可变 `ideer-*` 标签，核实产品分支、版本记录和当前验证证据。

发布流程采用 `ideer-*` 标签，经 `scripts/check_product_release.sh` 检查产品分支来源、已提交版本记录和版本一致性。版本记录要求见 [release records](releases/README.md)。

镜像流程位于 develop 的 `.github/workflows/upstream-mirror.yml`，仅提供手动入口。
默认只验证，显式选择 apply 后才更新 main。首次建立 main 还需显式选择 bootstrap。非快进更新立即停止，不强推，不批量同步标签。
main 更新、产品合入、兼容验证分别登记状态，镜像更新不代表产品完成升级。

当前兼容基线仍为 `0f7d8709d3bbf0be26460b6277fbad9329302243`。
v2.1.0 升级继续由 `docs/upgrades/deerflow-v2.1.0/` 的独立任务处理。

---

## 上游更新处理（双轨制，2026-10-01 修订）

上游跟进分两条轨道（收敛轨为主、修复轨为例外）：

### 收敛轨（tag 收敛）

1. **锚点**：上游 minor tag（v2.0.0→2026-06、v2.1.0→2026-09，约季度节奏）。
   不按 `deerflow/main` 提交数量做合并决策；功能与架构升级只锚定正式标签。
2. **流程**：每轮收敛独立建档 `docs/upgrades/deerflow-vX.Y.0/`（UPSTREAM_LOCK /
   PATH_POLICY / CONFLICT_LEDGER / DoD_CHECKLIST，方法论沿用
   `deerflow-main-0f7d8709` 与 `deerflow-v2.1.0` 两轮先例）。
3. **ref 约定**（每轮固定）：
   - 快照 tag `deerflow-vX.Y.0` 打在合并前的 develop HEAD（本地回滚锚点）；
     ⚠ 与上游锚点 tag `vX.Y.0`（deerflow 的上游代码树）名字相近、含义相反，
     回滚只用快照 tag；
   - 收敛分支 `integration/upstream-vX.Y.0` 仅存本地（独立 worktree），
     `--no-ff` 合入 develop 后删除；
   - probe 预探测分支仅在冲突面未知时使用（有试合并数据则省略）；
   - 合并落地后在升级锁定记录中登记上游 SHA 与 tag；团队发布仅使用 `ideer-*` 标签，
     不依赖批量推送上游标签来表示产品兼容状态。
4. **判定原则**（按顺序漏斗）：默认整 tag 吸收 → 冲突按路径所有权解
   （harness runtime 上游优先 / 资源治理·Workflow·内网交付本地优先 /
   gateway·config·前端·部署语义合并）→ 企业治理语义不让步（上游认证类功能
   必须并入本地 RBAC/审计，不得形成旁路）→ harness 补丁有上游等价 seam 即
   退役 → 内网不激活的能力收代码不配置、部署敏感默认值由 intranet overlay
   显式覆盖 → 前端按 P1-P6 超集原则 → 最终由验收 lane 与内网 bundle 裁决。
5. **补丁卫生**：每轮收敛强制 reassess 补丁台账（根 `UPSTREAM_PATCH_LEDGER.md`
   为唯一权威登记处）移除条件；harness 原始补丁面为 44 文件，本轮规则副本文档增量及明确预算变更见根账本；代码补丁与文档分别报告；可上游化的
   通用修复提 PR 回上游（候选：P003 文档行、P011 SQLite 异步桥、P014 迁移守卫、
   P032 readability 守卫等）。

### 修复轨（定向 cherry-pick）

- 仅两类提交可越过收敛轨提前吸收：安全修复、阻断性缺陷修复。
- 载体：`fix/upstream-<PR号>-<slug>` 短命分支，从 develop 切出 → cherry-pick →
  根台账登记（来源 SHA、原因、随下轮收敛自然吸收）→ focused suite → 合回
  develop → 删分支。同一变更在下轮 tag 合并时由 git 判重，不留第二长命线。
- 不做特性级 cherry-pick（防止半成品依赖链）。

---

## 产品升级验收

在对应 `integration/upstream-*` 中合并选定上游标签，按以下五类逐项解决冲突：

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

- 后端：标准 lane、相关契约与集成、blocking-I/O、迁移验证
- 前端：单测、类型检查、分层 E2E
- 集成：离线 Docker 打包、断网部署、升级迁移、RBAC 回归

### 发布记录

每次发布记录：iDeer 产品标签、对应上游标签、已吸收/明确拒绝的上游变更、离线兼容性结论、完整验证证据。

---

## 验收标准

- 发布责任归对应 `product/offline-*` 维护线；develop 承接团队开发与治理，main 只承担镜像更新
- 团队可在不接触 `origin/main` 的情况下持续开发和发布离线能力
- 每月分诊能识别安全修复，但不会把未稳定社区功能自动带入产品
- 产品升级可独立暂停、回滚和验收；成功后形成 `product/offline-2.x`，不污染 1.x 维护线

---

## 前提假设

- origin 的团队仓库可配置分支保护、代码评审和发布标签；执行前在线核实权限
- 既有产品分支及独立提交完整保留；本轮治理修改通过当前候选验收后由维护者合入
- 以上游稳定版整合为主、每月安全分诊为辅；高危安全修复不等待稳定版本

---

## 迁移与外部设置状态

1. 核实远端默认分支、main/develop/product 分支保护和发布工作流依赖。
2. 将团队默认分支设为 develop，保留所有产品维护分支及其独立提交。
3. 将 main 限定为镜像流程更新。先运行手动 dry-run，快进失败时停止并调查现有 main 历史。
4. 日常功能从 develop 创建；产品修复从对应 product 分支创建。产品发布核实 `ideer-*` 标签来源。
5. 上游同步记录 SHA；产品合入记录目标维护线；兼容验收记录当前候选及测试结果。

本轮首次通过 GitHub 连接器在线核实，默认分支已为 develop，develop 指向 `9916c5f8`，
当前账号有 admin 权限。首次分页查询只返回 develop，main 及 product 分支尚未建立。
develop 的 branch 元数据为 `protected: false`，rulesets 列表为空。
完整保护接口返回 `Resource not accessible by integration`，连接器不能修改管理设置。
最新 release 接口返回 404。现有发布工作流已改为 `ideer-*` 来源与版本记录检查。
镜像首次建立、分支保护设置及产品维护线建立分别记录执行状态，不代表产品完成升级。

本轮镜像执行状态：指定脚本已通过 GitHub SSH 443 通道完成首次创建，
远端 main 指向上游同一提交 `67db3d883c38264e2a188d9aaad44f7a7b55015d`。
首次 SSH 22、HTTPS 和连接器尝试未完成写入；SSH 443 复用已有 github.com
主机身份验证及认证成功，未修改 remote 或 SSH 配置。
后续更新运行 `UPSTREAM_MIRROR_APPLY=1 bash scripts/sync_upstream_mirror.sh`；
缺失镜像时另需 `UPSTREAM_MIRROR_BOOTSTRAP=1`。该流程不强推、不同步标签。
默认分支仍为 develop；分支保护设置仍待具有管理 API 权限的环境完成。
产品维护线按选定产品版本和发布记录独立建立，镜像创建不代表产品升级。

可配置的合并必需检查为 `PR Standard Gate`、`Real E2E Gate` 和 `Migration Gate`。
后两者在未要求专项验证时明确报告未要求，在要求时拒绝失败、取消或缺失结果。
迁移工作流的 PR 入口不按路径过滤，避免无关 PR 因必需检查没有生成而一直等待。
main 的保护应只允许指定镜像维护流程快进更新，并禁止团队规则合入、强推及删除；
产品发布仍由对应 `product/offline-*` 维护线和 `ideer-*` 版本记录约束。
