# 归零工作流缺口收口计划（简化测试版）

## 目标

在不触碰 validator 的前提下，收口归零工作流的文件隔离、文档一致性、真实 Worker 路径与三个案例验收，并把所有自动化测试合并为实现完成后的一个独立全量测试阶段。

## 实施范围

1. 清理 Workflow V2 Agent Adapter 中的 DEBUG 输出及临时诊断文件。
2. 修正 SOUL、Skill 和进展文档中“先生成证据再建树”的串行表述；不修改 validator 及其测试。
3. 为 Workflow V2 Agent Action 增加可选接口：

   ```yaml
   file_access:
     read:
       - "{{inputs.upload_dir}}"
     write:
       - "{{inputs.output_base_dir}}/artifacts/evidence"
   ```

   `file_access` 仅允许用于 Agent Action；未声明时保持现有行为。
4. 在 Agent 工具调用层增加文件访问中间件：
   - `read_file`、`ls`、`glob`、`grep`、`view_image` 受 `read` 根目录约束；
   - `write_file`、`str_replace` 受 `write` 根目录约束；
   - 拒绝相对路径、`..`、反斜杠穿越和相似前缀绕过；
   - 不修改高风险的全局 `validate_local_tool_path()`。
5. 为九个归零节点配置最小读写权限，重点保证 `deductive_tree` 无法读取证据目录。
6. 抽取生产 Worker 的单任务执行函数，使用真实 Store、Worker、Compiler、Checkpointer 和事件链完成集成覆盖。
7. 使用三个现有案例执行真实工作流：
   - 不向工作流提供 `06_expected_analysis.md`；
   - 检查运行成功、九个节点完成、产物存在且非空、`fault_tree.json` 可解析；
   - validator 不运行、不修复，也不作为完成门槛；
   - 将运行 ID、版本、耗时、事件数、产物路径和人工检查结果写入验证记录。
8. 根据实际结果同步设计方案、建设进展和验证记录；只有三个案例完成且全量测试通过后才标记重构完成。

## 测试约束

实现过程中补充必要的单元和集成用例，但不设置任务级聚焦测试命令，不执行红绿测试步骤，也不新增或运行 validator 测试。

所有实现和案例验收完成后，只执行一次独立全量测试：

```bash
cd backend
UV_CACHE_DIR=/tmp/deer-flow-uv-cache make test
```

```bash
cd frontend
pnpm test
pnpm check
```

三条命令必须全部以退出码 0 结束。任何失败均视为未完成，不通过跳过、放宽断言或修改门槛获得通过。

GitNexus 影响分析和提交前变更检测仍按仓库规则执行，但不列入测试门禁；lint、Alembic 和 validator 不是本计划的测试要求。

## 已锁定假设

- validator 的潜在缺陷属于独立问题，本计划完全不修改、不测试、不运行 validator。
- 三个真实案例是功能验收内容，但不依赖 validator 判定。
- 后端全量测试采用 `backend/Makefile` 默认范围，即 unit、integration、contracts，并沿用默认 marker。
- 前端全量测试采用 `pnpm test`，类型及 ESLint 检查采用 `pnpm check`。
