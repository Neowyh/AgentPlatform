# 底事件评估：case_01_wind_tunnel_heat_flux_drift

## 评估说明

本评估基于以下资料：
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md`

概率字段仅使用 high / medium / low / null，不给出精确数值。凡缺少直接验证的项目，状态标记为 `to_verify`。

## 顶事件

第4工况保持阶段，HF-07热流读数连续上升并超过设计判据12%，但邻近测点和喷流总压未同步变化。证据见：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/00_problem_statement.md，章节: 顶事件`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象`。

## 底事件逐项评估

### 1. HF-07传感器本体零点/灵敏度漂移

**事实**

- 第4工况T+118 s起，HF-07由1.03 MW/m2缓慢上升至1.25 MW/m2；HF-06和HF-08同期保持在1.01至1.06 MW/m2。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象`。
- 关键数据点显示HF-07单点上升，而HF-06/HF-08、总温、总压基本稳定。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:2-8`。
- 关车后HF-07零点回读偏移+8.4%FS。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 190 s关车后，HF-07=0.09，而HF-06/HF-08约0.01，CH-07状态为`zero_offset`。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:9`。

**推断**

现有资料与“单测点热流计零点或灵敏度漂移”机理一致；该方向得到设计文件“单点异常且邻近测点、总压、总温无同步变化时优先排查测量链路”的直接支持。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`。

**反证/限制**

- HF-07复标尚未完成，不能最终证明是传感器本体问题。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 历史案例仅具相似性，不能直接证明本案。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 相似问题`。

**评估结果**

- probability: **high**
- confidence: **medium**
- status: **to_verify**

**评估依据**

证据强度高，机理一致性高，反证弱；但缺少复标闭环，故不能写成已确认根因。

---

### 2. CH-07通道接地/屏蔽异常导致噪声或偏置漂移

**事实**

- 154 s和164 s记录出现`ch07_noise_flag`。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:7-8`。
- 190 s关车后CH-07状态为`zero_offset`。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:9`。
- 报告明确指出“采集通道CH-07屏蔽层接地状态尚未拆检”。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。

**推断**

该方向与后段噪声标志、关车后零偏现象一致，可解释为通道或接地状态劣化导致偏置漂移。

**反证/限制**

- HF-07在118 s已开始漂移，而`ch07_noise_flag`到154 s才出现。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-7`。
- 无接地连续性、屏蔽完整性、标准信号注入或通道互换结果，不能最终确认。待验证。

**评估结果**

- probability: **medium**
- confidence: **medium**
- status: **to_verify**

**评估依据**

现象支持度中等，机理一致性中等；存在时间先后不完全一致的限制，且直接拆检证据缺失。

---

### 3. HF-07贴装或热接触异常

**事实**

- 现场总结明确写明：由于复标未完成，不能排除局部贴装热接触异常。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 当前判断`。
- HF-07设计关注为“峰值热流和局部分离”。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 测点布置`。

**推断**

若贴装层、背衬或局部热接触异常，可能引入测点读数失真。

**反证/限制**

- HF-07对应区域未见烧蚀、剥落或异常变色。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 专家意见认为，若真实局部热流升高，应至少伴随相邻测点趋势变化、表面热痕迹或喷流参数变化；当前资料更支持测量链路异常。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`。
- 无拆解检查、显微检查或热态复现实验记录。待验证。

**评估结果**

- probability: **low**
- confidence: **low**
- status: **to_verify**

**评估依据**

该方向有保留性提示，但直接证据弱，且被零点偏移现象部分削弱。

---

### 4. HF-07位置真实局部热流升高

**事实**

- HF-07读数确实从1.03升至1.25 MW/m2。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:2-8`。

**推断**

若HF-07位置发生局部流动变化，理论上可能引起局部真实热流升高。

**反证/限制**

- HF-06和HF-08同期保持在1.01至1.06 MW/m2，无同步上升。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象`。
- T+100 s至T+170 s总压波动小于1.1%，总温波动小于9 K。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 118 s至164 s数据中总温1476-1483 K，总压518.9-521.0 kPa，主流条件稳定。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-8`。
- 试验后表面未见异常热痕迹。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- 专家复核认为当前资料更支持测量链路异常。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`。

**评估结果**

- probability: **low**
- confidence: **medium**
- status: **contradicted**

**评估依据**

该方向虽由表观读数升高触发，但被邻近测点、总压总温、表面检查和专家意见共同反证。

---

### 5. 风洞主流工况异常导致热流整体抬升

**事实**

- 工况4目标总温1480 K，总压520 kPa，保持180 s。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/02_test_outline试验大纲.md，章节: 工况矩阵`。

**反证/限制**

- T+100 s至T+170 s总压波动小于1.1%，总温波动小于9 K。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
- CSV中118-164 s总压、总温稳定，且并未出现多点同步超限。证据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:4-8`。

**评估结果**

- probability: **low**
- confidence: **high**
- status: **contradicted**

**评估依据**

该方向被主流参数稳定性直接反证，可作为低优先级排除项。

---

### 6. 后处理或换算链路异常

**事实**

现有资料中没有提供单独的数据换算核查记录、时间同步检查记录或后处理脚本复核结果。

**推断**

理论上该方向存在，但当前没有足够正反证。

**反证/限制**

- 缺乏直接证据，不能建立概率判断。待验证。

**评估结果**

- probability: **null**
- confidence: **low**
- status: **to_verify**

**评估依据**

资料不足，只能保留为待验证分支。

## 综合判断

当前资料更支持“HF-07测量链路异常”而非“真实热环境异常”。在测量链路异常内部，优先顺序为：

1. **HF-07传感器本体零点/灵敏度漂移**
2. **CH-07通道接地/屏蔽异常导致噪声或偏置漂移**
3. **HF-07贴装或热接触异常**

上述综合判断依据：
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 异常现象, 初步排查, 当前判断, 未关闭问题`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/04_test_data.csv:2-9`
- `文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/05_historical_or_review_notes.md，章节: 专家复核记录`

## 待验证项

1. **HF-07复标结果**：用于确认传感器本体是否存在零点/灵敏度漂移，并判定是否超过`±6%`复标偏差限值。证据依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/01_design方案.md，章节: 约束和判据`；`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 初步排查`。
2. **CH-07接地/屏蔽拆检**：用于确认通道噪声和零偏是否来自接地/屏蔽异常。证据依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。
3. **剔除HF-07后的判据复算**：用于界定本次异常对工况4热流裕度结论的影响范围。证据依据：`文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-files-20260521/user-data/workspace/cases/case_01_wind_tunnel_heat_flux_drift/03_test_summary试验总结报告.md，章节: 未关闭问题`。
