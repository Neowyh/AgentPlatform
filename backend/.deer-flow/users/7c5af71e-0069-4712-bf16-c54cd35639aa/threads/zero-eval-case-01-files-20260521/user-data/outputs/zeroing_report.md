# 归零报告：case_01_wind_tunnel_heat_flux_drift

## 1. 问题概述

本案例顶事件为：高焓风洞第4工况保持阶段，试验件腹部测点HF-07热流读数连续上升并超过设计判据12%，但邻近测点和喷流总压未同步变化。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 顶事件`。

发生条件为：试验日期2026-04-18；异常位于第4工况，目标马赫数6.2，目标总温1480 K；异常时间窗为T+118 s至T+164 s；影响范围为HF-07测点对应防热瓦热流裕度判断被中断，试验未提前关车。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 发生条件`。

当前状态为：试验后未发现试验件表面烧蚀异常；HF-07已拆下封存，尚未完成复标。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 当前状态`。

## 2. 输入资料

本次分析使用资料如下：

1. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md`
2. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`
3. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md`
4. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`
5. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`
6. `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`

说明：`06_expected_analysis.md`为人工验收参考，不作为本报告证据来源。

## 3. 故障现象

设计方案规定，第4工况用于覆盖峰值热流环境，判据为任一腹部热流测点5 s滑动均值不得超过1.12 MW/m2。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 设计目标`。

试验大纲规定，每个工况稳定保持180 s，采样频率20 Hz；若单点超限且持续超过10 s，记录异常时间段，保持工况至安全边界内完成数据闭环。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md，章节: 试验流程, 异常处置`。

试验总结表明：第4工况T+118 s起，HF-07由1.03 MW/m2缓慢上升至1.25 MW/m2，超过设计判据12%；HF-06和HF-08同期保持在1.01至1.06 MW/m2；总压、总温未出现同步跃升。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象`。

CSV关键数据进一步支持该现象：118 s时HF-07=1.12，130 s时HF-07=1.18，142 s时HF-07=1.23，154 s时HF-07=1.25，164 s时HF-07=1.24；同期HF-06维持在1.03-1.05，HF-08维持在1.02-1.05，总温1476-1483 K，总压518.9-521.0 kPa。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-8`。

关车后，HF-07零点回读偏移+8.4%FS，且190 s时HF-07=0.09、CH-07状态为`zero_offset`，而HF-06/HF-08约为0.01。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:9`。

## 4. 故障树分析

本案故障树顶事件定义为：**第4工况HF-07热流读数持续上升并超判据且与邻近测点不同步**。故障树主分支包括三类：

1. **真实热环境异常**：包括HF-07位置局部真实热流升高、风洞主流工况异常导致热流整体抬升。
2. **测量链路异常**：包括HF-07传感器本体零点/灵敏度漂移、CH-07通道接地/屏蔽异常导致噪声或偏置漂移、后处理/换算链路异常。
3. **贴装或热接触异常**：包括贴装层、背衬或局部热接触异常导致读数失真。

设计方案明确规定：若单点热流异常但邻近测点、总压、总温无同步变化，应优先排查测量链路。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`。因此，现有故障树中“测量链路异常”是主分析分支。

结构化故障树见输出文件 `fault_tree.json`。

## 5. 底事件评估

### 5.1 HF-07传感器本体零点/灵敏度漂移

这是当前优先级最高的底事件。支持证据包括：HF-07单点持续上升、邻近测点和主流参数稳定、关车后零点偏移+8.4%FS、历史相似案例中存在高温保持后薄膜热流计灵敏度漂移。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象, 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:2-9`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 相似问题`。

限制在于：HF-07复标尚未完成，因此该结论只能定为高倾向、待验证。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查, 未关闭问题`。

### 5.2 CH-07通道接地/屏蔽异常导致噪声或偏置漂移

该底事件的支持证据为：154 s和164 s出现`ch07_noise_flag`，关车后出现`zero_offset`，且总结报告明确CH-07屏蔽层接地状态尚未拆检。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:7-9`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。

其限制在于：HF-07在118 s已开始漂移，而噪声标志到154 s才出现，因此该方向更像下位细分原因之一，而非已被确认的唯一根因。状态为中倾向、待验证。

### 5.3 HF-07贴装或热接触异常

该底事件仅被总结报告作为保留项提出，缺乏直接检查证据。虽然HF-07测点设计关注峰值热流和局部分离，理论上存在局部贴装/热接触异常的可能，但表面检查未见烧蚀、剥落或异常变色，且专家意见认为当前资料更支持测量链路异常。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 测点布置`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 当前判断, 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`。

因此该方向维持低倾向、待验证。

### 5.4 真实热环境异常方向

该方向包含“HF-07位置真实局部热流升高”和“风洞主流工况异常导致热流整体抬升”。现有反证较强：HF-06和HF-08未同步升高；T+100 s至T+170 s总压波动小于1.1%，总温波动小于9 K；CSV数据表明118-164 s主流条件稳定；试后表面未见热痕迹；专家复核认为若真实局部热流升高，应至少伴随相邻测点趋势、表面热痕迹或喷流参数变化。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象, 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-8`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`。

因此该分支为低倾向，其中“风洞主流工况异常”可视为被反证。

更完整底事件评估见输出文件 `bottom_event_assessment.md`。

## 6. 根因归因

### 6.1 事实基础

- 顶事件是HF-07单点热流读数在第4工况保持阶段持续上升并超判据。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 顶事件`。
- 邻近测点HF-06/HF-08未同步变化，总压总温稳定。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象, 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-8`。
- 关车后HF-07零点回读偏移+8.4%FS，且CH-07后段出现噪声标志、关车后出现`zero_offset`。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:7-9`。

### 6.2 归因判断

基于现有资料，**当前最可能的归因是HF-07测量链路异常，而非真实热环境异常**。在测量链路异常内部，优先顺序为：

1. **HF-07传感器本体零点/灵敏度漂移**
2. **CH-07通道接地/屏蔽异常导致噪声或偏置漂移**
3. **HF-07贴装或热接触异常**

该判断的直接依据为：设计文件规定本类“单点异常且邻近测点、总压、总温不同步”的情形应优先排查测量链路。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`。

### 6.3 归因状态

由于HF-07复标和CH-07接地拆检尚未完成，本案**尚不能归零到唯一底事件**。因此本报告对根因的正式状态为：

- **主归因方向**：测量链路异常
- **最终唯一根因**：待验证

证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 当前判断, 未关闭问题`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`。

## 7. 验证计划

### 7.1 HF-07复标

目的：确认传感器本体是否存在零点或灵敏度漂移，并判断是否超过设计允许范围。设计文件规定，热流计复标偏差超过±6%时，该测点试验数据不得作为定量判据。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`。

预期：
- 若复标异常超过±6%，则HF-07数据应标记为不宜作为定量判据；
- 若复标正常，则需提高对通道链路和贴装异常方向的关注。

### 7.2 CH-07接地/屏蔽拆检与标准信号注入

目的：确认噪声标志和零偏是否来自通道接地、屏蔽、连接器或采集板卡异常。当前该项尚未拆检。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。

建议内容：
- 接地连续性检查；
- 屏蔽完整性检查；
- 连接器与板卡状态检查；
- 标准信号注入和通道互换试验。

### 7.3 HF-07拆解与贴装/热接触检查

目的：确认是否存在贴装层脱粘、背衬异常、焊点或引线损伤等导致读数失真的问题。当前资料中无直接检查记录，属于待验证项。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 当前判断`。

### 7.4 剔除HF-07后的判据复算

目的：评估本次异常对工况4热流裕度结论的影响边界。该问题已被总结报告列为未关闭问题。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。

## 8. 纠正措施

### 8.1 临时处置

- 在复标结果出来前，将HF-07标记为“可疑/待验证数据”，不得直接作为真实热流超限的定量判废依据。依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 保全HF-07相关原始数据和通道状态记录，禁止覆盖后处理版本。依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:7-9`。
- 在后续试验前，不建议继续将CH-07作为关键判据通道，除非拆检和注入试验完成。该项为基于未关闭问题形成的工程建议，状态为待验证。

### 8.2 短期纠正措施

- 完成HF-07正式复标；
- 完成CH-07接地、屏蔽、连接器、板卡拆检；
- 建立HF-07与健康通道之间的交叉互换试验。

### 8.3 中长期纠正措施

- 修订试验流程，在高温保持段中增加单点偏离邻点阈值报警和噪声标志在线监测；
- 对关键腹部热流测点增加冗余或邻域一致性判别；
- 建立薄膜热流计高焓保持后的漂移案例库，用于预防性筛查。

其中，试验流程当前已要求零点检查、绝缘检查和工况结束后的零点回读；建议是在现有流程上增强在线监测。现有流程依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md，章节: 试验流程`。

## 9. 遗留风险

1. **HF-07是否为传感器本体失效仍未关闭**。原因是复标未完成。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查, 未关闭问题`。
2. **CH-07是否存在接地/屏蔽共因风险仍未关闭**。原因是接地状态尚未拆检。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。
3. **若HF-07最终被判无效数据，则工况4对腹部右侧局部峰值热流的定量覆盖能力下降**。该项需通过剔除HF-07后的判据复算进一步确认。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。
4. **后处理或换算链路异常尚未被直接复核**，因此仍保留为低置信待验证分支。该项资料不足，待验证。

## 10. 结论

本案现有资料形成的闭环结论是：**HF-07异常更符合测量链路异常特征，而非真实热环境异常**。在测量链路异常内部，当前优先候选为HF-07传感器本体零点/灵敏度漂移，其次为CH-07通道接地/屏蔽异常，贴装或热接触异常仍需保留但证据较弱。由于HF-07复标和CH-07接地拆检尚未完成，本案暂不能归零到唯一底事件，最终结论状态应标记为**待验证**。

## 11. 证据附录

### 11.1 关键事实证据

- 顶事件与发生条件：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 顶事件, 发生条件, 当前状态`
- 设计判据与排查规则：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 设计目标, 测点布置, 约束和判据`
- 试验流程与异常处置规则：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md，章节: 试验流程, 工况矩阵, 异常处置`
- 异常现象、初步排查、未关闭问题：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象, 初步排查, 当前判断, 未关闭问题`
- 关键时间点数据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:2-9`
- 历史复核与专家意见：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 相似问题, 专家复核记录`

### 11.2 事实、推断、待验证区分

- **事实**：HF-07单点上升、邻近测点稳定、总压总温稳定、关车后零点偏移、CH-07后段出现噪声标志。
- **推断**：异常更偏向测量链路异常而非真实热环境异常。
- **待验证**：HF-07是否为传感器本体漂移、CH-07接地/屏蔽是否异常、贴装/热接触异常是否存在、HF-07剔除后的判据复算结果。
