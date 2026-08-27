---
name: summarize
description: |
  离线长文本与文档智能摘要。基于上传文件或粘贴文本（禁公网 URL 抓取），走 LLM 分级摘要，输出结构化摘要+核心要点+关键词，支持 short/medium/long 三档与 text/markdown/json 输出。日常办公→智能摘要 Pill 一键触发。
description_zh: "离线长文本/本地文档摘要（LLM 分级，禁公网），含文档摘要/会议纪要/要点提炼三模版，输出摘要+要点+关键词，支持 short/medium/long 与 text/markdown/json。"
requires-internet: false
user-invocable: true
argument-hint: '[粘贴长文或上传 .txt/.md/.pdf/.docx]'
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
metadata:
  author: ideer-bundled
  title: 智能摘要
  version: 2.0.0
  category: productivity
  scenes:
    - daily
  pills:
    - summarize
  capabilities:
    - 离线长文本智能摘要，保留关键信息（时间/人物/数据/结论）
    - 本地文档摘要（.txt/.md/.pdf/.docx， via officecli/anthropic-pdf/docx）
    - 会议记录→纪要（决议/待办/责任人/截止日期）
    - 关键词与关键短语提取（按重要度排序）
    - 三档长度与三档输出格式，可溯源（页码/段落标注）
  offline_notes: 禁公网，网页 URL 抓取已移除；仅基于用户上传的本地文件或粘贴文本
---

# Summarize 智能摘要（离线内网版）

> 本版为 **离线内网定制版（v2.0.0）**，基于初始 `clawhub_paudyyin/summarize:1.0.0` 的 CLI 工具改造：**移除所有公网能力**（`requests`/`BeautifulSoup` 网页抓取），摘要主路径改为平台 LLM（`runtime/config.yaml: models`），保留启发式为离线 LLM 不可用时的 fallback。符合 `bundled-skills.txt:8-10` 的“无联网触发词/无外网请求/无 CDN”预装要求。

## When to Use

- 用户说“总结/摘要/提炼要点/生成摘要/提取关键词/帮我总结这篇文档/会议纪要”
- 用户上传了本地文档（`.txt/.md/.pdf/.docx/.py/.html`）并希望得到摘要
- 用户粘贴了长文（报告/论文/会议记录/长邮件）并希望压缩
- 用户在工作台 **日常办公 → 智能摘要** Pill 选择了“文档摘要/会议纪要/要点提炼”

## When NOT to Use

- 用户明确要求抓取公网 URL 并摘要 → 拒绝，引导改为“请上传该网页的本地导出（PDF/Markdown）或粘贴正文”
- 仅需翻译/校对/排版 → 走 `translate`/`wps-proofread`/`wps-gongwen`
- 数据表的统计/透视 → 走 `data-analysis`（DuckDB）

## Hard Constraints（输出前必检，违一即失败）

| # | 约束 | 违规示例 |
|---|------|---------|
| C1 | **禁公网**：不得以任何方式请求公网 URL（`requests.get`/`fetch`/`curl https://`），仅允许 `Read` 本地文件或处理用户粘贴文本 | 调用 `requests.get("https://example.com")`；`curl -s https://...` |
| C2 | **长度守恒**：`short ≤300字 / medium ≤600字 / long ≤1500字`（与 `references/length-presets.md` 一致），超长必须截断并加 `…` | `short` 输 800 字 |
| C3 | **要点不丢**：输出必须含 `## 摘要` + `### 核心要点（3-6条）` + `### 关键词（5-8个）`，且要点覆盖时间/人物/数据/结论四类关键信息（无则显式标注“原文未提及”） | 只给摘要段落，无要点/关键词 |
| C4 | **可溯源**：长文档（>2000字或多文件）摘要要点需标注来源（如 `【P3】`/`【§2】`），便于核验 | 长报告要点无来源标注 |
| C5 | **格式守恒**：按用户要求的 `--output` 输出（`text`/`markdown`/`json`），`json` 必须含 `summary/keywords/source/word_count/length` 五字段 | `json` 缺 `keywords` |

触发词含 `http://`/`https://`/`--url` 时，先输出拒绝引导语：“离线内网不支持公网抓取，请上传本地文件或粘贴正文”，再继续本地摘要流程。

## 三档工作流

| 档位 | 适用输入 | 步骤 | 输出 |
|------|---------|------|------|
| `quick` | ≤2000字短文 | LLM 单轮直出 | `summary.md` |
| `standard`（默认） | 2000-10000字 | 分析(领域/受众)→分块(4000字阈值，见 `references/chunking.md`)→LLM 并行摘要→合并去重 | `analysis.md` + `summary.md` |
| `refined` | 重要文档/报告 | `standard` + 审校(对照原文查遗漏/幻觉)→润色 | `draft.md` + `review.md` + `summary.md` |

`4000字` 分块阈值与 `5000字` 单块上限参考 `translate:244` 的 `chunk_threshold` 设计，块边界按 Markdown 块（标题/段落/列表/代码块）切分，超限回退到按行/按词。

## Step-by-Step

### Step 1 — 物化输入

- **粘贴文本**：直接作为 `text` 输入，记录 `source: 粘贴文本` 与 `word_count`
- **本地文件**：通过 `Read`/`Glob` 定位，`officecli` 或 `Read` 读取；`*.docx` 经 `python-docx`、`*.pdf` 经 `anthropic-pdf`/`PyPDF2` 兜底（离线无需 `requests`）。多文件按文件名排序合并，保留 `source: 文件名列表`
- **拒绝分支**：输入含 URL → 输出引导语后，要求用户改用上述两种方式

### Step 2 — 选档

- 显式 `--length short/medium/long` 优先；未指定时按输入长度自动选档（≤2000→quick，2000-6000→medium，>6000→long）
- 记录 `length` 供 `C2` 校验

### Step 3 — LLM 摘要（主路径）

使用平台已配置的 `models`（`runtime/config.yaml: models: []` 为空时 fail-closed，提示“请先在 内网部署作业指导书 §11 配置模型”），prompt 见 `references/prompt-template.md`：

```
你是离线文档摘要助手，禁公网，仅基于用户提供的本地文本。
任务：按 {length} 档输出 摘要+要点+关键词，保留时间/人物/数据/结论，标注来源页码。
输入：{chunk}
约束：C2/C3/C4 必须满足，超长截断加 …
```

- `standard/refined` 需将全文 `analysis.md`（领域/语气/术语）作为共享上下文注入各 chunk 的 prompt，再合并
- 无 LLM 时 fallback：调用 `references/legacy-cli.py` 的启发式（正则分句+词频，`short/medium/long` 取 2-3/3-6/6-12 句，截断 300/600/1500），并在输出头部标注“（启发式离线兜底，质量低于 LLM）”

### Step 4 — 关键词

`extract_keywords` 按 `word_count` 的 `Counter` 排序，停用词表与 `legacy-cli.py:22` 一致，`--keywords-count` 默认 8（与 `summarize.py:134` 的新默认对齐），`json` 输出 `keywords: string[]`

### Step 5 — 输出与自检

- `text`：`【摘要】…\n【关键词】…\n【来源】…\n【原文字数】…`
- `markdown`：`## 📄 摘要\n…\n### 🔑 核心要点\n- …\n### 关键词\n- …\n### ℹ️ 元信息`（含 `include_meta` 时）
- `json`：`{summary, keywords, source, word_count, length}`（`C5`）
- 自检：`python3 {baseDir}/scripts/verify_summary.py --target output/summary.md --length medium`，`pass:false` 时改写直至通过

## 与工作台 Pill 的联动

- 入口：**日常办公 → 智能摘要**（`SCENARIOS: daily:5` 的第 5 个 `AgentPill`，`agentSlug: summarize`），三 Chip 分别注入三档 promptTemplate（见 `frontend/src/core/scenarios/config.ts:8`）
- Chip 注入后走 `lead_agent`，`summarize` 作为其 `config.skills` 白名单之一自动加载，无需新建独立 Agent；如需独立人格，可另建 `resources/agents/summarize-agent`（可选）

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/verify_summary.py` | 确定性自检：长度/要点条数/关键词数/外链检测，`--target/--length`，无第三方依赖 |
| `references/legacy-cli.py` | 原 CLI 存档（`summarize.py:1`），含启发式 `generate_summary:28` 与 `extract_keywords:15`，仅作 fallback 参考 |

## 参考

- 长度档位：`references/length-presets.md`
- 分块策略：`references/chunking.md`
- Prompt 模板：`references/prompt-template.md`
- 原始实现：`references/legacy-cli.py`（已移除网络分支）
