# 02: 发布不可变 Knowledge Revision

**What to build:** owner 发布 Revision 候选，平台在独立 Published Dataset 完成构建和验证后切换当前发布版本；用户能看到发布进度和可恢复失败，历史已发布知识保持不变。

**Blocked by:** 01: 创建与查看 Knowledge Revision 候选.

**Status:** ready-for-agent

- [ ] 发布经 canonical API 发起并在版本页显示真实状态；独立 Published Dataset 与可编辑草稿隔离，构建输入来自候选冻结内容。
- [ ] 索引完成且 manifest 校验通过后才推进当前 Published Revision；失败、取消或重复请求不会提前切换指针或产生多个成功版本。
- [ ] 发布失败保留可恢复状态与已创建 provider 资产的关联；重试行为有界，跨数据库／provider 操作不伪装成原子事务。
- [ ] 已发布文档和配置不可原地修改；草稿修改、删除和后续发布不破坏旧 Published Dataset 及其内容引用。
- [ ] 发布门禁包含授权与完整性检查；`eval_required` 默认关闭，开启时缺少与候选匹配的合格评测证据则拒绝发布。仅提供门禁契约，不实现 M6 Eval 引擎。
- [ ] API、版本页和审计记录区分候选、发布中、失败与成功；错误不泄漏 provider 内部信息。
- [ ] 聚焦测试证明门禁、并发／重复发布安全、失败恢复和旧版本不变；真实 provider 发布契约纳入最终 Gate 验收。
