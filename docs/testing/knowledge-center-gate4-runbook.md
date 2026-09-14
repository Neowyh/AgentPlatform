# Knowledge Center Gate4 验收运行说明

Gate4 的真实验收由两个互补测试组成：

1. `backend/tests/test_knowledge_gate4_live.py` 直接调用真实 RAGFlow，验证上传、解析、索引可搜索、删除以及删除后的无命中。
2. `frontend/tests/e2e/real/knowledge-center-gate4.spec.ts` 使用真实登录会话和浏览器 UI，验证创建并绑定 KB、上传文件、看到 `ready`、删除文件以及 UI/API 最终无文档。

## 运行

先启动真实网关和 RAGFlow，并准备一个仅供本次验收使用的 dataset。不要使用共享生产 dataset。

后端 provider 验收：

```bash
cd backend
DEER_FLOW_RUN_LIVE_TESTS=1 RAGFLOW_GATE4_DATASET_ID=<isolated-dataset-id> \
  uv run pytest tests/test_knowledge_gate4_live.py -q -s
```

浏览器验收由真实 E2E harness 提供 `E2E_STATE_DIR`、`E2E_RUN_ID`、`IDEER_INTERNAL_GATEWAY_BASE_URL` 和 `PLAYWRIGHT_BASE_URL`，并额外设置：

```bash
E2E_KNOWLEDGE_DATASET_ID=<isolated-dataset-id> \
bash scripts/run-test-lane.sh frontend-real
```

也可以在真实 harness 已启动时只运行该 spec：

```bash
cd frontend
PLAYWRIGHT_SKIP_WEB_SERVER=1 E2E_KNOWLEDGE_DATASET_ID=<isolated-dataset-id> \
  pnpm exec playwright test tests/e2e/real/knowledge-center-gate4.spec.ts
```

## 结果分类

- `passed`：对应真实 provider 或真实浏览器测试实际执行并通过。
- `skipped/unexecuted`：缺少真实服务、harness、凭据或隔离 dataset；不能计入 Gate4 通过证据。
- `failed`：真实路径执行后失败；必须保留测试输出和 trace，不能用 mock lane 结果替代。

默认单元测试、mock E2E 和 `pr-standard` 只证明替身/本地契约，不证明 Gate4 的真实 provider 或浏览器验收。
