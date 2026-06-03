# case_01_wind_tunnel_heat_flux_drift 归零报告

## 1. 问题概述

本案例顶事件为：高焓风洞第4工况保持阶段，试验件腹部测点HF-07热流读数连续上升并超过设计判据12%，但邻近测点和喷流总压未同步变化。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md`，章节: 顶事件。

异常发生于 2026-04-18 第4工况，目标马赫数 6.2、目标总温 1480 K，异常时段为 T+118 s 至 T+164 s。影响范围为 HF-07 对应防热瓦热流裕度判断中断，但试验未提前关车。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md`，章节: 发生条件。

## 2. 输入资料

本次分析已读取案例目录 00–06 全部文件：

- `00_problem_statement.md`
- `01_design方案.md`
- `02_test_outline试验大纲.md`
- `03_test_summary试验总结报告.md`
- `04_test_data.csv`
- `05_historical_or_review_notes.md`
- `06_expected_analysis.md`

其中 `06_expected_analysis.md` 明示“该文件只供人工验收使用，不建议上传给归零智能体”，因此本报告不将其作为根因结论依据，仅作为验收约束参考，不纳入证据链闭环。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/06_expected_analysis.md`，章节: Case 01 人工期望分析。

## 3. 故障现象与事实整理

第4工况期间，HF-07 从 1.03 MW/m2 逐步升高至 1.25 MW/m2，T+118 s 起进入异常上升阶段，至 T+142 s 后已明显超过判据 1.12 MW/m2。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-003~A-C1-007。

同期 HF-06 和 HF-08 基本保持在 1.01–1.06 MW/m2，HF-05 亦未见同步抬升。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-003~A-C1-007。

总压在异常时段波动小于 1.1%，总温波动小于 9 K；CSV记录与总结一致，说明风洞主工况总体稳定。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-001~A-C1-007。

关车后 HF-07 零点回读偏移 +8.4%FS，停机记录中HF-07仍有 0.09 MW/m2 残余，而其他热流通道约为 0.01 MW/m2；同时 CH07 状态为 `zero_offset`。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-008。

异常后段 154 s 与 164 s 出现 `ch07_noise_flag`，提示通道侧存在噪声/状态异常迹象。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-006、A-C1-007。

试后表面检查未见HF-07对应区域烧蚀、剥落或异常变色；问题描述亦指出试验后未发现试验件表面烧蚀异常。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md`，章节: 当前状态。

## 4. 设计约束与排故判据

设计文件明确规定：若单点热流异常但邻近测点、总压、总温无同步变化，应优先排查测量链路；若热流计复标偏差超过 ±6%，该测点试验数据不得作为定量判据。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据。

试验大纲规定：第4工况判据为腹部热流5 s均值不超过 1.12 MW/m2；若单点超限且持续超过10 s，则记录异常时间段并保持工况以完成数据闭环。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md`，章节: 工况矩阵、异常处置。

因此，从规则层面，当前异常首先落入“优先排查测量链路”的规定场景；但是否能最终剔除HF-07数据，仍取决于复标与评审结论。

## 5. 故障树分析

本次故障树已单独输出至 `fault_tree.json`。主干逻辑如下：

- 顶事件：HF-07 在第4工况保持段单点持续升高并超限。
- 中间事件一：真实热环境导致HF-07真实热流升高。
- 中间事件二：HF-07测量链路异常导致读数漂移。
- 中间事件三：HF-07局部安装/热接触异常导致单点响应失真。

### 5.1 真实热环境异常分支

该分支包括“喷流整体热环境异常”和“HF-07附近局部真实热流异常”两类解释。

对“喷流整体热环境异常”，现有资料存在较强反证：总压、总温稳定，相邻测点未同步变化。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 异常现象、初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-001~A-C1-007。

对“HF-07附近局部真实热流异常”，虽然理论上不能被绝对排除，但表面检查未见热痕迹，且专家复核指出若真实局部热流升高，通常应至少伴随相邻测点趋势变化、表面热痕迹或喷流参数变化；当前资料不支持该模式。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。

### 5.2 测量链路异常分支

该分支是当前最强主线。其支持证据包括：

1. 设计方案明确要求对单点异常优先排查测量链路。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据。
2. HF-07关车后零点回读偏移 +8.4%FS，超过设计文件中“复标偏差 ±6% 即不得作为定量判据”的量级门槛参考，但注意这里仍不是正式复标结论。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据。
3. 停机记录中 CH07 为 `zero_offset`，且异常后段出现 `ch07_noise_flag`。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-006、A-C1-007、A-C1-008。
4. 试验总结当前判断明确写到“现场初步认为 HF-07 测量链路漂移可能性较高”。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 当前判断。

但该分支尚未闭合，因为两个关键验证未完成：HF-07复标未完成，CH-07屏蔽层接地状态尚未拆检。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查、未关闭问题。

### 5.3 贴装/热接触异常分支

试验总结指出“不能排除局部贴装热接触异常”。这说明该分支必须保留。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 当前判断。

但目前没有拆检、复装、粘接层检查或热阻复测资料，因此这一方向证据不足，只能列为待验证。

## 6. 根因归因

### 6.1 事实

- HF-07异常是真实记录到的数据现象，且持续时间足够长，超限事实明确。
- 异常具有单点性，不伴随相邻测点或主流参数同步变化。
- 关车后HF-07存在明显零点偏移，且CH-07出现通道异常状态标志。

### 6.2 推断

综合原始数据、设计判据和专家复核，当前最符合证据链的解释是：**HF-07测量链路异常导致第4工况期间读数漂移**。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 当前判断；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。

在该主路径下，最主要的两个候选底事件为：

1. **HF-07传感器本体零点/灵敏度漂移**：高倾向，待验证。
2. **CH-07采集通道噪声/接地屏蔽异常**：中倾向，待验证。

### 6.3 不确定性与边界

- 由于HF-07复标尚未完成，不能把“传感器本体漂移”写成已证实根因。
- 由于CH-07接地屏蔽状态尚未拆检，不能排除采集通道问题是主因或共因。
- 由于没有贴装拆检资料，贴装/热接触异常不能关闭，但当前支持较弱。
- 真实局部热环境异常虽然倾向低，但因缺乏专门流场诊断数据，不能以“确认无异常”表述替代“当前资料未支持”。

### 6.4 当前归零结论

**当前归零结论：本案最可能属于HF-07测量链路异常，表现为单点热流读数漂移；其中HF-07传感器本体漂移和CH-07通道噪声/接地屏蔽异常是两个最主要待验证底事件。正式根因关闭条件尚未满足，结论状态为“有主判断、未完全闭环”。**

## 7. 验证计划

1. **HF-07复标**
   - 目的：确认零点偏移、灵敏度漂移是否超过允许范围。
   - 预期判据：若复标偏差超过 ±6%，则依据设计约束，该测点数据不得作为定量判据。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据。
   - 输出：复标记录、试前后对比表、是否判定HF-07失效。

2. **CH-07接地/屏蔽/连接完整性拆检**
   - 目的：确认是否存在屏蔽层虚接、接地不良、连接器接触不稳、板卡输入异常。
   - 证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 未关闭问题。
   - 输出：拆检记录、绝缘/接地测试结果、必要时链路注入试验结果。

3. **区分传感器本体与通道问题的复现试验**
   - 建议方法：同通道替换传感器、同传感器替换通道，或进行标准信号注入与热态/冷态比对。
   - 目的：把BE-03与BE-04解耦。
   - 当前状态：待验证，现有资料中无此试验记录。

4. **贴装/热接触检查**
   - 目的：关闭贴装异常分支。
   - 方法：拆检贴装界面、检查粘接层完整性、必要时做冷态标定或局部热响应复测。
   - 当前状态：待验证。

5. **剔除HF-07后的判据复算与评审**
   - 目的：明确本次异常对试验结论的影响范围。
   - 证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 未关闭问题。

## 8. 纠正措施建议

在验证结果出来前，建议先采取以下临时纠正措施：

1. 将HF-07本次第4工况数据标记为“待复核，不作为单独定量判据”。依据：零点偏移与链路异常尚未关闭。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查、未关闭问题。
2. 对同批次薄膜热流计增加试前/试后零点回读与复标强制项，缩短漂移发现闭环时间。该项为改进建议，非现有事实结论。
3. 对采集通道增加屏蔽接地状态点检清单，并记录到试验前检查表。依据：CH-07接地状态尚未拆检暴露出过程控制空缺。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 未关闭问题。
4. 对单点超限场景保留实时通道健康监测与异常标志抓取，以便更早区分真实热环境与测量链路问题。该项为流程优化建议。

## 9. 遗留风险

1. 若HF-07复标超差，则第4工况腹部热流裕度需按剔除HF-07后的规则重新评审；该影响尚未关闭。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 未关闭问题。
2. 若CH-07通道存在硬件或接地问题，则同类通道在后续试验中可能复发，需要扩展排查。
3. 若贴装异常未验证关闭，则后续重复试验仍可能出现同类单点失真。

## 10. 证据附录

### 10.1 关键原始数据点

- `A-C1-003`：118 s，HF-07=1.12，异常起始。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`
- `A-C1-005`：142 s，HF-07=1.23，超过判据。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`
- `A-C1-006`：154 s，CH07=`ch07_noise_flag`。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`
- `A-C1-008`：190 s，停机后HF-07=0.09，CH07=`zero_offset`。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`

### 10.2 关键文字证据

- 单点异常优先排查测量链路。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`，章节: 约束和判据。
- 现场初步认为HF-07测量链路漂移可能性较高，但不能排除局部贴装热接触异常。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 当前判断。
- 专家复核认为当前资料更支持测量链路异常，但需要HF-07复标和CH-07接地拆检后才能关闭。文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。
