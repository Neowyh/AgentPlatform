# M3 下一阶段计划：文档管理与 Knowledge Center

> 制定日期：2026-09-13
> 状态：**待用户确认**
> 前置报告：[M3 开工基线收口报告](../testing/2026-09-13-m3-readiness-closeout-report.md)
> 当前结论：M3 **UNVERIFIED**，本计划在解除硬前置前不进入实现。

## 目标

在 M2 canonical KnowledgeBase Resource Governance 已可用的基础上，补齐文档管理和 Knowledge Center。所有写操作经过 AgentPlatform Knowledge Service；Agent Runtime 继续只读检索。前端通过平台 API 获取知识库和文档状态，不读取 provider 内部数据模型。

## 解除阻塞后实施顺序

1. 固定 Knowledge Center 的 canonical API 子资源：KB 列表/详情、文档列表/详情、上传、删除草稿、重试解析和重建索引；所有响应按当前用户权限过滤。
2. 在管理侧接入 provider 适配层，完成文件名和 MIME 校验、大小/数量限制、hash、隔离存储、上传以及解析/索引状态机。provider 不可达时保留可恢复失败状态，不泄漏 endpoint、凭据或 raw dataset ID。
3. 将文档和状态接入前端 Knowledge Center，展示真实列表和详情、解析/索引失败原因的脱敏摘要，并通过 `/api/features` 控制能力可见性。
4. 将检索预算、结果上限和超时接入当前 run scope；检索继续复用 M2 的 caller/resource/provider 交集，禁止客户端注入 raw dataset ID。
5. 完成验收闭环：创建 KB → 上传 → 解析 → 索引 → 授权检索 → 删除草稿文档；覆盖越权、非法文件、超限、provider 不可达、失败恢复和脱敏。

## 主要接缝和约束

- 企业模型和服务位于 `backend/app/agentplatform/knowledge/`；provider/runtime 适配位于 `backend/packages/agentplatform-extension/agentplatform_extension/knowledge/`。
- 复用 `ResourceService`、现有 Resource API 的可见性/owner/caller 规则、现有 storage/publisher 的安全校验以及 run evidence 接缝。
- 文档内容、provider dataset ID 和内部 URL 不进入 Agent prompt、普通用户错误响应或前端日志。
- M4 Revision/Publish/Run Snapshot、M5 Retrieval Receipt/Evidence UI、M6 Eval 依次后置；不在 M3 偷渡不可变 Revision 或评测能力。
- M9 Local MCP/Secrets/Tray 作为并行取舍待确认，不提前执行。

## 测试要求

- 后端：Knowledge Service/API 单元与契约测试，隔离 provider 集成测试，权限与跨用户测试，失败恢复和存储安全测试。
- 前端：Knowledge Center API/types/hooks/component 测试、TypeScript/ESLint；需要浏览器验收时单独执行 frontend visual/a11y lane。
- 真实验收：隔离 dev RAGFlow、两 KB×两用户、至少一个合法文档和一个非法/超限文件；记录 provider 调用、授权拒绝、状态变化和脱敏扫描。
- 交付前运行 backend standard 与 `bash scripts/run-test-lane.sh pr-standard`；只有明确交付请求才运行 `core-full`。

## 开始条件与用户确认项

开始 M3 实现前需要确认：

1. 接受当前收口结论为 UNVERIFIED，并先补齐报告列出的 M0/M1/M2 证据；
2. 确认文档上传的 provider 存储配额、单文件/单 KB 限制和允许的文件类型；
3. 确认 M9 是否继续作为独立并行取舍，不纳入 M3；
4. 确认真实 RAGFlow 测试环境和测试用户/KB 的隔离范围。
