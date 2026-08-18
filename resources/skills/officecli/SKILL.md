---
name: officecli
description: Use this skill when the user asks to create, read, edit, or render previews of Office documents — Word (.docx), Excel (.xlsx), or PowerPoint (.pptx) — using the OfficeCLI command-line tool. Covers generating reports, editing contracts, producing slides, merging templates, formula evaluation in Excel, and rendering documents to HTML/PNG for visual verification. Prefer this over python-docx/openpyxl/python-pptx when the operation involves styling, layout, formulas, or rendering.
allowed-tools:
  - bash
  - read_file
  - ls
  - glob
  - grep
  - list_dir
---

# OfficeCLI 使用技能

本技能教你用 `officecli` 命令在沙箱内创建、读取、修改 Word / Excel / PowerPoint 文档，
并将文档渲染为 HTML / PNG 供视觉检查。OfficeCLI 是单文件自包含二进制，无需安装 Office。

## 前提

- 二进制已由平台通过只读挂载注入沙箱：`/usr/local/bin/officecli`（`which officecli` 应能看到）。
- 自动更新已通过环境变量 `OFFICECLI_SKIP_UPDATE=1` 关闭，离线环境不会卡在联网检查。
- 文档读写都在沙箱工作区进行，例如 `/mnt/user-data/workspace/`。

## 使用策略（三层渐进，先理解再修改）

1. **L1 读取层（view）**：先看文档的语义视图，理解结构再动手。
   - `officecli view <file> text` — 纯文本内容（xlsx 输出每个单元格 `A1=值`）。
   - `officecli view <file> outline` — 大纲/结构。
   - `officecli view <file> issues --json` — 布局/样式/结构问题诊断。
   - `officecli view <file> html -o out.html` — 高保真 HTML 渲染，Agent 可读图检查布局。
   - `officecli view <file> screenshot --page 1 -o out.png` — 逐页 PNG 截图，供多模态检查。
2. **L2 DOM 层（get/set/add/remove/move/swap）**：按路径寻址操作元素（`/slide[1]/shape[2]`）。
   - `officecli get <file> /... --json` — 读取任意元素的确定性 JSON。
   - `officecli set <file> /... --prop size=24` — 修改属性。
   - `officecli add <file> / --type slide --prop title='本周汇报'` — 新增元素。
   - `officecli remove <file> /slide[2]` — 删除元素。
3. **L3 原始层（raw/raw-set/validate）**：L2 不够用时直接操作底层 XML。

始终优先从 L1 开始理解文档，L2 做修改，L2 不够才降级到 L3。

## 常见命令示例

```bash
# PPT：创建并添加带标题的幻灯片
officecli create /mnt/user-data/workspace/deck.pptx
officecli add /mnt/user-data/workspace/deck.pptx / --type slide --prop title='Q4 汇报'

# Word：查看纯文本后再改标题字号
officecli view /mnt/user-data/workspace/report.docx text
officecli set /mnt/user-data/workspace/report.docx /body/h1[1] --prop size=24

# Excel：读取单元格并检查公式求值
officecli view /mnt/user-data/workspace/budget.xlsx text
officecli get /mnt/user-data/workspace/budget.xlsx '/sheet1/A1' --json

# 模板合并：{{key}} 占位符批量生成
officecli merge /mnt/user-data/workspace/tmpl.docx /mnt/user-data/workspace/data.json -o /mnt/user-data/workspace/out.docx

# 渲染做完务必自检：HTML 或截图 + issues
officecli view /mnt/user-data/workspace/deck.pptx html -o /mnt/user-data/workspace/deck.html
officecli view /mnt/user-data/workspace/deck.pptx issues --json
```

## 关键约定

- **文件路径必须用绝对路径**，优先基于沙箱工作区 `/mnt/user-data/workspace/`。
- **结构化输出**：给 Agent 读的结构信息一律加 `--json`，schema 确定，避免正则解析。
- **路径寻址**：元素用稳定路径（如 `/slide[1]/shape[2]`），1-based 索引。
- **修改后自愈式复查**：操作返回结构化错误（带建议修正和有效范围）时，先用 `officecli query <file> ...` 查询可行范围再重试。
- **格式独立**：单条命令即可创建 docx/xlsx/pptx，无需分别维护整套 Python 库。
- **不要启用自动更新**：环境里已设 `OFFICECLI_SKIP_UPDATE=1`，不要尝试 `officecli install`/网络操作。