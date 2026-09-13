# 01: 创建与查看 Knowledge Revision 候选

**What to build:** KnowledgeBase owner 可从已就绪资料生成一个固定文档集合及相关配置的 Revision 候选，并在版本页查看其内容，使后续发布有明确、可核验的依据。

**Blocked by:** M3 完成并通过 Gate 4（外部里程碑前置，执行前核实当前候选证据）。

**Status:** done

- [x] owner 可经 canonical KnowledgeBase 子资源 API 创建候选，并在知识库版本列表／详情查看候选状态、逻辑文档与内容 hash；未就绪文档不能被误计为可发布内容。
- [x] 候选固定文档集合、内容引用及影响索引／检索的相关配置，manifest hash 按确定性规则计算；相同 manifest 得到相同 hash。
- [x] 后续草稿编辑或删除不改变已有候选，也不移除候选所需的内容；候选跨请求、页面刷新和服务重启保持可读取。
- [x] Knowledge Revision 与 Resource 内容版本明确区分，KB UUID 保持 canonical identity；provider 标识、地址及凭据不暴露给模型或普通用户。
- [x] 创建、列表、详情沿用 Resource Governance；覆盖 owner、非 owner、隐藏 KB、跨 KB 标识和无权操作无副作用的 API 测试。
- [x] 聚焦测试覆盖确定性 manifest、草稿变化不污染候选，以及版本页真实加载、空列表和错误状态。

本票不发布 dataset、不冻结 Run，也不建设评测功能。
