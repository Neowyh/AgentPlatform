# Case 04 混合证据 + 静态扫描披露（代码证据包）

> **状态：真实模型验收待跑。** 本案例当前只交付素材与评测设计骨架；
> 真实模型验收（上传→扫描→披露→报告全链路）尚未执行，跑通前不作为通过依据。

## 场景

风机电机监测系统热试验后出现"超限告警与原始数据不一致"。用户提供文档资料
（问题描述）和一个 Code Evidence Package（C 源码 + GB18030 编码文件 + 固件表
二进制），要求完成归零分析。

本案例验收的**不是**故障树结论本身（case_01~03 已覆盖），而是工单 T1/T2/T3/T4
建立的代码证据链路：

1. `analyze_code_evidence` 能对代码证据包运行只读静态扫描并落盘
   `analysis/`（inventory.json、findings.json、scanner_status.json）。
2. 静态告警作为证据时 confidence 只能是 `high_risk_candidate`，不得
   直接升级为 confirmed。
3. GB18030 编码的 `gb_log_parse.c` 能被 `read_file`/`grep` 正常读取
   （输出带 `[encoding: GB18030]` 前缀），中文注释与字符串不丢失。
4. `firmware_table.bin` 在白名单内被接受，`read_binary_hex` 可给出
   hex + 可打印字符串视图。
5. evidence_collection 节点把 `analysis/scanner_status.json` 复制为
   outputs 侧 `artifacts/evidence/scan_summary.json`；Result Contract
   披露门生效：代码侧 Run 缺扫描记录不得完成。
6. 扫描器二进制不可用（未装 cppcheck/clang-tidy 的环境）时，Run 仍可
   完成，但报告"遗留风险"必须原样包含"静态扫描器不可用"——
   「未扫描」不得表述成「扫描无告警」。

## 使用方式

1. 将 `code_package/` 目录打包为 ZIP（保持 `source/` 一级目录结构），
   与 `02_problem_statement.md` 一起作为混合证据发起归零 Run。
2. 推荐（在 case_01 提示词基础上追加）：

```text
代码证据包请先运行静态扫描（analyze_code_evidence），静态告警单独只能作为
high_risk_candidate；如扫描器不可用，请在报告遗留风险中如实披露"静态扫描器不可用"。
二进制文件请用 read_binary_hex 检查文件头。
```

3. `01_设计方案骨架.md` 是评测设计与预期结果对照表（预期扫描 finding、
   预期披露措辞、判定标准），仅供人工评测对照，建议不要上传。

## 素材清单

| 文件 | 说明 |
| --- | --- |
| `02_problem_statement.md` | 文档侧最小顶事件描述 |
| `code_package/source/motor_monitor.c` | UTF-8；含 cppcheck 可检的已知越界缺陷 |
| `code_package/source/gb_log_parse.c` | **GB18030 编码**；中文注释与字符串字面量 |
| `code_package/source/firmware_table.bin` | 52 字节白名单内二进制（`.bin`） |
| `01_设计方案骨架.md` | 评测设计骨架与预期披露说明（人工对照，不上传） |

全部资料均为脱敏伪数据，不对应真实型号、真实设备编号或真实人员。
