# case_01_wind_tunnel_heat_flux_drift 底事件评估

## 评估口径

依据“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”进行倾向判断。未见统计频次、行业数据库或专家打分表，因此不使用数值概率，只使用高/中/低倾向；证据不足项标记“待验证”。

## 底事件逐项评估

### BE-01 喷流整体热环境异常

- 倾向：低
- Confidence：medium
- Status：rejected
- 事实证据：第4工况异常时段总压波动小于1.1%，总温波动小于9 K；CSV记录中 96 s 至 164 s 总压约 518.9–521.0 kPa、总温约 1476–1483 K，未见与HF-07同步的整体环境跃升。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-001~A-C1-007。
- 机理一致性：若为喷流整体异常，通常应伴随多测点或总压/总温协同变化；本案未观察到该模式。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。
- 反证情况：HF-06、HF-08同期保持在 1.01–1.06 MW/m2，构成反证。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-003~A-C1-007。
- 复现实验情况：资料中无复现实验记录，不能据此完全排除更局部流场异常。
- 结论：该方向当前不作为优先根因路径，但严格说仅能否定“整体热环境异常”这一解释，不能完全覆盖所有局部流动异常可能。

### BE-02 HF-07附近局部真实热流异常

- 倾向：低
- Confidence：low
- Status：to_verify
- 事实证据：仅有HF-07单点上升，缺少相邻测点同步变化；试后表面检查未见烧蚀、剥落或异常变色。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 异常现象、初步排查。
- 机理一致性：局部热点理论上可能只影响单点，但若持续至超限并维持较长时间，通常更希望看到相邻测点趋势变化或表面热痕迹；现有资料未提供此类支持。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。
- 反证情况：总压、总温稳定，相邻点不变，表面检查未见异常，均为反证。
- 复现实验情况：无。
- 结论：保留为待验证分支，但现有支持不足，不能作为主根因。

### BE-03 HF-07传感器本体零点/灵敏度漂移

- 倾向：高
- Confidence：medium
- Status：to_verify
- 事实证据：关车后HF-07零点回读偏移 +8.4%FS；停机记录中HF-07仍为0.09 MW/m2，而其他热流通道约0.01 MW/m2，且CH07状态为 zero_offset。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-008。
- 机理一致性：薄膜热流计在高温保持后发生零点或灵敏度漂移，与本次“缓慢上升+关车后零偏”的现象一致。历史上存在相似案例，但只能作为相似性支持。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 相似问题。
- 反证情况：当前尚无直接反证，但由于复标未完成，尚不能将“通道异常”与“传感器本体漂移”彻底区分。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查、未关闭问题。
- 复现实验情况：无本次复标结果，无复现实验记录。
- 结论：这是当前最强的可疑底事件之一，但必须以HF-07复标结果闭环，现阶段只能给出高倾向、未关闭判断。

### BE-04 CH-07采集通道噪声/接地屏蔽异常

- 倾向：中
- Confidence：medium
- Status：to_verify
- 事实证据：154 s 与 164 s 出现 `ch07_noise_flag`；停机后 CH07 状态为 `zero_offset`；总结报告明确记载 CH-07 屏蔽层接地状态尚未拆检。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-006、A-C1-007、A-C1-008；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 未关闭问题。
- 机理一致性：通道噪声、接地不良或屏蔽异常可导致单通道输出漂移或叠加噪声，与“单点异常”“后段噪声标志”“停机零偏”相符。
- 反证情况：异常起始于 118 s，而噪声标志直到 154 s 才出现，因此资料尚不足以证明起始根因就是通道噪声；更可能说明后段通道状态进一步恶化或被系统识别。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`，evidence_id: A-C1-003~A-C1-007。
- 复现实验情况：无拆检、无复现。
- 结论：该事件具有中等倾向，是与BE-03并列的重要验证方向。

### BE-05 HF-07贴装/热接触异常

- 倾向：无法判断
- Confidence：low
- Status：to_verify
- 事实证据：现有资料中唯一直接提及为“不能排除局部贴装热接触异常”。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 当前判断。
- 机理一致性：贴装热阻异常理论上可引起单点读数偏移，但本案缺少拆检、复装、显微检查或冷态/热态对比证据。
- 反证情况：试后表面检查未见明显烧蚀、剥落或异常变色；专家复核认为当前资料更支持测量链路异常。证据来源：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-bounded-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`，章节: 专家复核记录。
- 复现实验情况：无。
- 结论：仅能保留，不宜上升为主要怀疑方向。

## 综合排序

1. BE-03 HF-07传感器本体零点/灵敏度漂移：高倾向，待验证。
2. BE-04 CH-07采集通道噪声/接地屏蔽异常：中倾向，待验证。
3. BE-05 HF-07贴装/热接触异常：无法判断，待验证。
4. BE-02 HF-07附近局部真实热流异常：低倾向，待验证。
5. BE-01 喷流整体热环境异常：低倾向，当前基本被反证。

## 现阶段主判断

现有资料最支持“HF-07测量链路异常”这一中间事件，其下至少包含两条未关闭路径：一是HF-07传感器本体漂移，二是CH-07通道噪声/接地屏蔽异常。两者均有A类数据支持，但尚缺最终区分证据，因此根因结论必须保留“待验证”。

## 建议验证项

1. 对HF-07执行复标，确认零点偏移与灵敏度漂移量，并与试前记录比对。
2. 拆检CH-07屏蔽层、接地、连接器和采集板卡，复现或排除噪声耦合与零偏问题。
3. 若条件允许，进行同型号热流计替换复测或冷/热态链路注入试验，区分传感器本体与通道问题。
4. 结合评审要求，剔除HF-07后重新计算第4工况腹部热流裕度，明确试验判据影响范围。
