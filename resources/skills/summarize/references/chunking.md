# 分块策略（复用 translate 的阈值设计）

- **触发分块**：输入 ≥4000 字（`chunk_threshold`）时分块；单块上限 5000 字（`chunk_max_words`），与 `translate:240` 一致
- **切分优先级**：Markdown 块边界（标题/段落/列表/代码块/表格）> 行边界 > 词边界
- **共享上下文**：`standard/refined` 档先生成 `analysis.md`（领域/受众/术语/难点），注入各 chunk 的 prompt，再合并
- **合并**：LLM 各 chunk 摘要按序拼接，去重后按 `length` 档重写为最终 `summary.md`；启发式则按含数字/关键词句优先（`legacy-cli.py:48-54`）

单文件 <4000 字直通 `quick`，多文件合并后再评估是否分块。
