# 归零排故报告

## 1. 问题概述
本案顶事件为：热真空试验升温平台切换至保温阶段后，试验件内部测点 TC-12 温度超过目标上限 9.6C，持续 7 分 30 秒。发生条件为 2026-04-26、真空度 3.2e-3 Pa、升温至 85C 后切换保温；影响范围为电子舱热平衡数据有效性存疑，但未造成硬件损伤。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`，章节: 顶事件、发生条件。

## 2. 输入资料
本次分析直接读取以下资料：
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`

未读取 `06_expected_analysis.md`，符合用户限定范围。

## 3. 事实归纳
### 3.1 判据与设计约束
保温阶段目标温度为 85C，内部测点短时超调不得超过 4C 且持续不超过 180 s；切换至保温阶段后，占空比应在 60 s 内降至 35% 以下。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 设计目标、控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据。

### 3.2 实际异常表现
试验总结显示，参数组由 A 切换至 B 后，外壁测点 TC-09、TC-10 维持在 84.6C 至 86.2C，而内部测点 TC-12 上升至 94.6C。CSV 数据进一步显示：138 min 切换到 B，TC-12 为 84.1C；142 min 达到 91.2C 并超限；144 min 达峰值 94.6C；148 min 人工切换至 C 后，152 min 恢复至 87.2C。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。

### 3.3 已完成排查结果
- 真空度异常期间为 3.0e-3 Pa 至 3.5e-3 Pa，满足试验要求。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
- 外壁反馈未超判据。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录、异常现象。
- 切保温后 120 s 内加热占空比仍保持 58% 以上，违反控制约束。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
- TC-12 未脱落，但胶层偏厚，需要复测。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录。
- 参数组 B 在试验前一日由 2026B-2 改为 2026B-3。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录。

## 4. 故障树分析结论
故障树见输出文件 `fault_tree.json`。文字化结论如下：
1. 顶事件成立，且明显超过设计与试验判据。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`，章节: 顶事件；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 设计目标；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据。
2. 主传播链为“保温切换后加热输入未及时下降 → 内部热量继续积累 → TC-12 持续超调”。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
3. 次传播链为“测量/热惯性因素放大内部超调表征”，其中 TC-12 胶层偏厚和热惯性模型失配仅具备辅助嫌疑，证据尚不闭环。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步判断；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 复核意见。

## 5. 底事件评估
详细评估见 `bottom_event_assessment.md`。归纳如下：
- BE-02“保温切换逻辑使占空比下降过慢”为当前最强嫌疑项，倾向高，置信度高。
- BE-01“参数组B积分限幅或相关控制参数误配置”为最强上游触发嫌疑，倾向高，置信度中，但仍待参数文件复核确认。
- BE-03“TC-12导热胶层偏厚导致动态响应失真”为低倾向、待验证项。
- BE-04“热惯性模型与实际响应不一致”为中倾向、低置信度待验证项。

## 6. 根因归因
### 6.1 当前最支持的根因判断
当前证据最支持的结论是：保温参数组 B 切换后控制输出下降过慢，是造成内部测点持续超调的直接原因；其更深层诱因很可能是参数组 B 新版本配置异常，尤其是积分限幅或同类控制参数误配置。证据链包括：
- 设计/试验要求切换后 60 s 内占空比降至 35% 以下。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据。
- 实测切换后 120 s 内占空比仍高于 58%，且 TC-12 持续升高。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
- 参数组 B 在试验前一日改版。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录。
- 历史案例表明，积分限幅未同步更新可导致相同模式超调。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 历史相似案例。

### 6.2 结论边界
由于尚未完成参数组 B 配置逐项复核，也未完成参数组 C 对比复现实验，故“参数误配置”目前只能定性为待验证根因，不能宣告完全闭环。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。

## 7. 验证计划
### 7.1 软件配置复核
- 对比 2026B-2 与 2026B-3 的全部控制参数，重点检查积分限幅、切换条件、抗积分饱和、保温阶段输出上限。
- 预期：若发现关键参数偏离设计基线，可直接支撑 BE-01。
- 证据需求：参数导出文件、变更记录、审核记录。
- 当前状态：待验证。

### 7.2 短时复现实验
- 按未关闭问题建议，使用参数组 C 进行一次短时复现实验，并增加对比：B 原版、B 修正版、C 保守版三组回放/试验。
- 观察项：切换后 0~10 min 的占空比变化、TC-09/10/12 温度轨迹。
- 判定逻辑：若修正参数组 B 后占空比按要求在 60 s 内下降且不再出现超调，则可强支撑根因闭环。
- 当前状态：待验证。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。

### 7.3 测点安装复核
- 对 TC-12 导热胶厚度进行复测，必要时重贴并复标定。
- 目的：排除 BE-03 作为次要干扰项。
- 当前状态：待验证。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`，章节: 当前状态；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。

### 7.4 热惯性模型复核
- 复查内部支架与外壁的热耦合模型、控制参数整定依据与仿真工况。
- 仅在软件配置复核不能完全解释异常时继续深入。
- 当前状态：待验证。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束。

## 8. 纠正措施建议
1. 冻结参数组 B 变更，完成版本差异审计前不得再次用于正式试验。
2. 建立保温参数组切换前后自动核查项：60 s 占空比门限、内部测点 10 min 监视窗、超限自动告警。
3. 将参数文件变更纳入双人复核和试验前签署流程。
4. 对内部关键测点安装工艺增加胶层厚度验收记录，避免仅凭目视复查。

以上措施为工程建议，尚需结合后续验证结果固化。

## 9. 遗留风险
- 若不完成参数复核与复现实验，后续同类热真空试验仍可能重复出现内部超调。
- 若 TC-12 安装工艺问题未排除，则未来数据解释仍存在偏差风险。
- 当前仅能确认“电子舱热平衡数据有效性存疑”，不能据此外推其他工况均失效。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`，章节: 发生条件。

## 10. 归零结论
本次归零分析认为：顶事件已被充分证实；直接致因是保温切换后加热占空比下降过慢；最可疑根因是参数组 B 新版本控制参数误配置，尤其是积分限幅相关项，但该根因尚未通过配置比对和复现实验最终关闭。TC-12 胶层偏厚和热惯性模型失配属于待验证次级因素，不宜单独定为根因。

## 11. 证据附录
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`
