---
name: chip-software-development-package
description: 从同型号同封装的原厂芯片资料集中提取可追溯的嵌入式软件开发知识包
allowed-tools:
  - glob
  - grep
  - read_file
  - read_document
  - write_file
  - present_files
  - ask_clarification
---

# 芯片软件开发包提取

## 目标

把用户提供的同一芯片型号、同一封装的原厂 Chip software source set 整理成两份可下载工件：

1. `embedded-software-knowledge-brief.md`
2. `chip-software-table.json`

这是资料核验与开发前知识整理能力，不生成可直接上板的初始化代码、驱动、链接脚本或业务固件。

## 输入边界

- 只接受原生文本 PDF 的 datasheet、Reference Manual 或 Programming Manual，以及适用 errata。
- 先让用户明确目标型号和封装，再盘点上传目录；不从文件名猜测身份。
- 混合型号、混合封装、扫描件/OCR、非原厂网页和无法确认的资料不得合并。
- 使用 `read_document` 分段读取文档，保留文档名、章节或页码；遇到转换失败或扫描件时如实记录，不猜测内容。

## 证据与状态门禁

每项结论必须包含来源定位，并标记为且只能标记为 `confirmed` 或 `review_required`：

- `confirmed`：一致的原厂资料直接支持，且没有适用 errata 冲突。
- `review_required`：跨页合并、复杂表格、身份不确定、资料缺口、文档冲突或 errata 影响无法消解。简报中必须显示“需人工复核”。

缺少 datasheet、Reference/Programming Manual 或适用 errata 时，在简报“资料缺口”中列出。资料缺口和 `review_required` 只能保留供人工核验，不能作为下游自动化事实。

## 覆盖范围

按以下主题组织简报：启动/复位、时钟、存储器、指定封装引脚复用、外设、寄存器查阅入口、中断、DMA 和勘误影响。结构化附表至少包含：`pin`、`signal`、`alternate_function`、`peripheral`、`interrupt`、`source`、`confidence`，并附封装信息。

不得用同系列其他型号或封装内容填空；无法从资料得出的板级晶振、供电、连线、SDK/HAL 版本必须写入资料缺口。

## 输出与自检

将两份文件写入 `/mnt/user-data/outputs/`，完成后调用 `present_files`。自检：目标型号/封装一致；两份工件条目和状态一致；每个关键结论有来源；冲突和不确定项均为 `review_required`；下游消费只读取 `confirmed` 条目。
