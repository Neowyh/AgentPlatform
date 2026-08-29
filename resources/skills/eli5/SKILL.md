---
name: eli5
description: Explain any topic like I'm 5 — generate a dead-simple HTML picture explainer with big visuals and few words. Use when the user types /eli5 <topic> or asks for a beginner-friendly explainer.
description_zh: 用“给 5 岁孩子讲明白”的方式解释任意主题，产出大图少字的单文件 HTML 图文科普。触发词：/eli5 <主题>、给我讲明白、通俗解释、小白也能懂。
description_en: Explain any topic like I'm 5 via a dead-simple single-file HTML artifact with big visuals and few words.
version: 1.0.0
category: Creative
author: Thariq Shihipar
homepage: https://github.com/anthropics/claude-plugins-community/tree/main/eli5
license: MIT
display_name: 五岁也能懂
display_name_en: Explain Like I'm 5
visibility: public
---

# eli5 — 五岁也能懂

把任意复杂主题，用**大图 + 少字 + 单文件 HTML**的方式讲到“零基础也能懂”。

> 上游来源：`anthropics/claude-plugins-community/eli5` · MIT · 纯 LLM · 完全离线可用

触发方式：`/eli5 <topic>` 或自然语言“用最简单的方式解释 … / 给小白讲讲 … / ELI5 …”。

主题：`$ARGUMENTS`

## 何时使用

- 用户输入 `/eli5 ...` 显式触发
- 用户说“解释一下…但我完全不懂”、“像给孩子讲”、“零基础通俗版”、“一张图讲明白”
- 需要把专业概念（DNS、区块链、量子纠缠、期权定价等）压缩为直觉模型

## 产出要求

1. **单文件 HTML**（`eli5-<slug>.html`），离线可直接用浏览器打开，无外链 CDN、无网络请求。
2. **大图少字**：每屏 1 个核心比喻 + 1 张大号示意图（可用 inline SVG / CSS 图形 / Emoji 大图标，避免外链图片），文字控制在 3–5 行短句内。
3. **结构**（建议 4–6 屏）：
   - 标题：主题 + 一句话钩子
   - 比喻：生活化类比（快递/乐高/水管等）
   - 过程：3 步以内的流程图（箭头 + 大图标）
   - 为什么重要 / 常见误解（1 屏）
   - 一句话总结 + “如果只记住一件事”
4. **风格**：圆角卡片、超大字号、鲜明配色、留白充足；避免专业术语，必要术语用括号白话翻译。
5. **可打印**：`@media print` 友好，背景可省墨。

## 写作约束（离线友好）

- 不依赖联网搜索、API 或外部图片
- 不使用外链字体/图标 CDN；图标用 Emoji 或 inline SVG
- 语言跟随用户输入语言；中英混排时保持术语一致

## 最小示例

用户：`/eli5 how does DNS work`

产出：`eli5-dns.html` — 封面“DNS 是互联网的电话簿”，随后“你喊名字 → 电话簿查号码 → 拨号连接”三步大图，每步配 1 句白话 + 1 个 Emoji/简笔画。

## 与其他技能区分

- 要做“精美演讲级 PPT”用 `guizang-ppt-skill`
- 要做“生产级前端页面”用 `frontend-design`
- 本技能只做“极简科普解释”，不追求交互复杂度和数据可视化
