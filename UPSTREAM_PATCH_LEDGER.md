# Upstream Patch Ledger

对 `backend/packages/harness/`（上游 DeerFlow harness）的每一处修改必须在此登记，
含测试证据、原因、Owner 与移除条件（架构基线 §"架构不变量"上游修改纪律）。
仅改 `backend/app/`（AgentPlatform 控制面）或 `backend/packages/agentplatform-extension/`
（扩展包）不属上游修改，无需登记。

## 巡检记录

| 日期 | 候选 | 结果 |
| --- | --- | --- |
| 2026-09-13 | feature/m4-knowledge-revisions（M4 票 06 Gate 5/6 巡检） | 本轮涉及 `community/ragflow/client.py`（PATCH-001）；未发现未登记的上游修改。GitNexus 在本工作区不可用（无索引、npx 无法引导，见 dev-log），以人工调用方分析替代。 |

## 登记项

### PATCH-001: RAGFlow 管理端 client 兼容 v0.27+ 批量文档端点

- **文件**: `backend/packages/harness/deerflow/community/ragflow/client.py`
- **修改**: `parse_document` 改用批量解析端点
  `POST /datasets/{id}/documents/parse`（body `{"document_ids": [...]}`）；
  `get_document_status` 改经列表端点解析单文档状态（单文档 GET 返回非 JSON）；
  `delete_document` 改为 JSON body `{"ids": [...]}`（旧 query 参数形式被拒绝）；
  新增 `create_dataset`、`list_dataset_documents`（M4 发布/对账所需）。
- **原因**: 真实 RAGFlow v0.27.1 隔离栈验收（M4 票 06）发现单文档 parse 404、
  单文档 GET 非 JSON、DELETE query 形式被拒——既有单元测试的假 client 无法暴露。
- **测试**: `tests/test_ragflow_client.py`（批量 parse、列表化状态、JSON body 删除、
  create/list 端点、分页与响应形）；真实 provider 验收脚本全链路通过（dev-log）。
- **Owner**: knowledge 域维护者
- **移除条件**: 上游 RAGFlow 社区 client 提供等价能力（批量 parse/状态/删除/建库）
  并被本仓库采纳时，可整体移除。
