# Task Plan: 离线 Docker 部署整改执行

## Goal

按 `docs/deployment/离线Docker部署整改方案.md` 实施离线 Docker 部署修复，并用回归测试验证 runtime 配置、compose 合同、打包排除和文档一致性。

## Current Phase

Complete

## Phases

### Phase 1: Requirements & Discovery

- [x] 读取用户请求，确认目标是生成修改方案而非直接改代码
- [x] 读取审查报告，提取问题清单和优先级
- [x] 初始化 `task_plan.md`、`findings.md`、`progress.md`
- **Status:** complete

### Phase 2: Planning & Structure

- [x] 将审查问题映射为可执行修改项
- [x] 明确 P0/P1/P2 修复顺序
- [x] 明确每项修改涉及文件、验收标准和回归测试
- **Status:** complete

### Phase 3: Plan Artifact Creation

- [x] 在 `docs/deployment/` 下创建正式修改方案 Markdown
- [x] 保持方案聚焦离线 Docker 部署，不展开无关重构
- **Status:** complete

### Phase 4: Verification

- [x] 检查方案文件存在
- [x] 检查方案包含问题、修改项、验收标准和执行顺序
- [x] 更新 `progress.md`
- **Status:** complete

### Phase 5: Delivery

- [x] 汇总交付文件路径
- [x] 说明未执行代码修改
- **Status:** complete

### Phase 6: Failing Regression Tests

- [x] 新增离线部署脚本回归测试
- [x] 运行测试并确认当前实现失败
- **Status:** complete

### Phase 7: Implement Fixes

- [x] 修复 `deploy-intranet.sh`
- [x] 修复 `package-intranet-offline.sh`
- [x] 修复 `docker-compose.intranet.yaml`
- [x] 更新离线部署作业指导书
- **Status:** complete

### Phase 8: Verification

- [x] 运行新增 pytest
- [x] 运行 shell 语法检查
- [x] 运行 compose config 静态校验
- [x] 更新 progress
- **Status:** complete

### Phase 9: Deployment Docs Refresh

- [x] 按当前脚本和 compose 行为重写离线部署方案
- [x] 按电脑小白操作需求重写作业指导书
- [x] 将示例部署目录统一为 `/home/deploy/deer-flow`
- [x] 补充每一步操作的原理说明和常见故障排查
- [x] 运行文档关键字核对、脚本语法检查和离线部署回归测试
- **Status:** complete

### Phase 10: Existing Env Upgrade Backfill

- [x] 核实 review 提出的旧 `env.intranet` 升级路径问题
- [x] 新增失败回归测试覆盖已有 env 缺失内部 token
- [x] 修改 `deploy-intranet.sh`，对已有 env 追加缺失认证变量
- [x] 验证重复 `prepare` 不重复追加 key，且不覆盖已有配置
- [x] 运行相关 pytest 和 shell 语法检查
- **Status:** complete

### Phase 11: Frontend Health Review Loop

- [x] 核实 review 提出的“只检查 gateway 会误报部署健康”问题
- [x] 新增失败回归测试覆盖 frontend 路由不可用但 gateway 可用的场景
- [x] 修改 `deploy-intranet.sh`，启动后额外检查 nginx 首页 `/`
- [x] 同步更新部署方案和作业指导书的健康检查说明
- [x] 运行相关 pytest、shell 语法检查、compose config 和未提交变更审查
- **Status:** complete

## Key Questions

1. 哪些问题必须作为 P0 阻断离线部署成功？
2. 哪些问题属于稳定性、可维护性或安全加固，可放入 P1/P2？
3. 每个修改项的最小验证命令是什么？

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 本次只生成修改方案，不直接改部署代码 | 用户明确要求“生成修改方案”，不是“按方案修复” |
| 方案放在 `docs/deployment/` 下 | 与审查报告和离线部署文档同目录，便于后续执行 |
| 按 P0/P1/P2 分阶段 | 离线部署问题有启动阻断、运行稳定性和清理加固之分 |
| 用户已批准执行整改方案 | “按该方案执行”明确进入实施阶段 |
| 采用 TDD | 新增回归测试先失败，再改脚本实现 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 无 | 1 | 无需处理 |

## Notes

- 已按用户要求完成脚本、compose、测试和部署文档更新。
- 离线部署文档示例目录统一为 `/home/deploy/deer-flow`，实际路径仍可通过脚本参数或环境变量配置。
