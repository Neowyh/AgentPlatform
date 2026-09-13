# 04: PINNED 依赖选择与固定版本运行

**What to build:** 用户为 Agent／Workflow 选择一个已发布 Knowledge Revision 作为 PINNED 依赖，新 Run 使用指定版本，并可查看依赖配置与本次运行实际版本。

**Blocked by:** 03: LIVE 依赖在 Run 启动时冻结.

**Status:** done

- [x] 复用既有依赖声明，API 与依赖编辑界面支持选择有权使用的已发布 Revision，清晰区分 LIVE 与 PINNED。
- [x] 发布 Rev2 后 PINNED Rev1 的新 Run 仍使用 Rev1；运行中修改依赖声明不改变已启动 Run 的快照。
- [x] 非存在版本、其他 KB 的版本、未发布／不可用版本和调用者无权版本被明确拒绝，执行副作用前完成校验。
- [x] 依赖保存与实际启动均遵循现有治理授权，shared Agent 不借用 owner 权限，Workflow／Sub-Agent 不能扩大知识范围。
- [x] 运行详情展示实际冻结版本；provider dataset ID 不进入选择器、常规响应或模型工具参数。
- [x] 聚焦测试覆盖 PINNED 固定、LIVE/PINNED 配置切换、越权拒绝和界面交互，证明实际检索仍指向被选版本。
